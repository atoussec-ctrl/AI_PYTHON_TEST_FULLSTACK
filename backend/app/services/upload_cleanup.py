"""Backstop cleanup for uploads abandoned by clients or interrupted processes."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import UTC, timedelta
from pathlib import Path

from flask import current_app
from sqlalchemy import delete

from app.extensions import db
from app.models import Attachment, utc_now
from app.services.file_security import ALLOWED_EXTENSIONS

logger = logging.getLogger(__name__)

_MANAGED_EXTENSIONS = sorted(
    {extension for extensions in ALLOWED_EXTENSIONS.values() for extension in extensions}
)
_MANAGED_FILE_PATTERN = re.compile(
    rf"^(?:\.[0-9a-f]{{32}}\.uploading|[0-9a-f]{{32}}\.(?:{'|'.join(_MANAGED_EXTENSIONS)}))$"
)


@dataclass(frozen=True)
class UploadCleanupResult:
    orphan_records: int
    orphan_files: int
    failed_files: int
    dry_run: bool


class UploadCleanupService:
    """Remove only old, server-named files that no message still references."""

    def cleanup(self, *, older_than: timedelta, dry_run: bool = False) -> UploadCleanupResult:
        if older_than <= timedelta(0):
            raise ValueError("older_than deve ser maior que zero")

        cutoff = utc_now() - older_than
        upload_dir = Path(current_app.config["UPLOAD_DIR"]).resolve()
        upload_dir.mkdir(parents=True, exist_ok=True)

        orphan_filter = (
            Attachment.message_id.is_(None),
            Attachment.created_at <= cutoff,
        )
        orphan_rows = (
            db.session.query(Attachment.id, Attachment.storage_path)
            .filter(*orphan_filter)
            .order_by(Attachment.created_at.asc())
            .all()
        )
        candidates = {
            path
            for _, storage_path in orphan_rows
            if (path := self._managed_path(storage_path, upload_dir)) is not None
        }

        orphan_record_count = len(orphan_rows)
        if not dry_run:
            try:
                # Keep the orphan predicates in the DELETE itself.  If a
                # concurrent request links one of these rows after the SELECT,
                # that row no longer matches and remains intact.
                result = db.session.execute(delete(Attachment).where(*orphan_filter))
                db.session.commit()
                if result.rowcount is not None:
                    orphan_record_count = result.rowcount
            except Exception:
                db.session.rollback()
                raise

        reference_query = db.session.query(Attachment.storage_path)
        if dry_run and orphan_rows:
            reference_query = reference_query.filter(
                Attachment.id.notin_([attachment_id for attachment_id, _ in orphan_rows])
            )
        referenced_paths = {
            path
            for (storage_path,) in reference_query.all()
            if (path := self._managed_path(storage_path, upload_dir)) is not None
        }
        # A corrupted or manually edited database may contain duplicate paths.
        # Never delete a file while any non-orphan row still references it.
        candidates.difference_update(referenced_paths)
        cutoff_epoch = cutoff.replace(tzinfo=UTC).timestamp()
        for path in upload_dir.iterdir():
            if (
                path.is_symlink()
                or not path.is_file()
                or not _MANAGED_FILE_PATTERN.fullmatch(path.name)
                or path.resolve() in referenced_paths
            ):
                continue
            try:
                if path.stat().st_mtime <= cutoff_epoch:
                    candidates.add(path.resolve())
            except OSError:
                logger.warning("Não foi possível inspecionar upload %s", path, exc_info=True)

        failures = 0
        if not dry_run:
            for path in candidates:
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    failures += 1
                    logger.warning("Não foi possível remover upload órfão %s", path, exc_info=True)

        return UploadCleanupResult(
            orphan_records=orphan_record_count,
            orphan_files=len(candidates),
            failed_files=failures,
            dry_run=dry_run,
        )

    @staticmethod
    def _managed_path(value: str, upload_dir: Path) -> Path | None:
        raw_path = Path(value)
        # Never resolve and later unlink a symlink: its target may be outside
        # UPLOAD_DIR even when the link itself has a server-shaped name.
        if raw_path.is_symlink():
            return None
        path = raw_path.resolve()
        try:
            relative = path.relative_to(upload_dir)
        except ValueError:
            return None
        if len(relative.parts) != 1 or not _MANAGED_FILE_PATTERN.fullmatch(relative.name):
            return None
        return path
