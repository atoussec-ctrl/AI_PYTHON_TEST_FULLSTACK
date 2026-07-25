"""Tests for the upload orphan-cleanup backstop."""

from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

import pytest

from app.extensions import db
from app.models import Attachment, ChatMessage, ChatSession, utc_now
from app.services.upload_cleanup import UploadCleanupService


def _managed_file(upload_dir: Path, name: str, *, old: bool = True) -> Path:
    path = upload_dir / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"payload")
    if old:
        timestamp = (utc_now() - timedelta(hours=48)).timestamp()
        os.utime(path, (timestamp, timestamp))
    return path


def test_cleanup_removes_old_unlinked_rows_and_unreferenced_managed_files(app):
    upload_dir = Path(app.config["UPLOAD_DIR"])
    old = utc_now() - timedelta(hours=48)
    old_row_path = _managed_file(upload_dir, f"{'1' * 32}.txt")
    linked_path = _managed_file(upload_dir, f"{'2' * 32}.txt")
    young_path = _managed_file(upload_dir, f"{'3' * 32}.txt", old=False)
    disk_orphan = _managed_file(upload_dir, f"{'4' * 32}.txt")
    quarantine = _managed_file(upload_dir, f".{'5' * 32}.uploading")
    unmanaged = _managed_file(upload_dir, "manual-note.txt")

    with app.app_context():
        session = ChatSession(title="Cleanup")
        db.session.add(session)
        db.session.flush()
        message = ChatMessage(session_id=session.id, role="user", content="oi")
        db.session.add(message)
        db.session.flush()
        old_unlinked = Attachment(
            session_id=session.id,
            filename="old.txt",
            mime_type="text/plain",
            size=7,
            kind="document",
            storage_path=str(old_row_path),
            created_at=old,
        )
        linked = Attachment(
            session_id=session.id,
            message_id=message.id,
            filename="linked.txt",
            mime_type="text/plain",
            size=7,
            kind="document",
            storage_path=str(linked_path),
            created_at=old,
        )
        young = Attachment(
            session_id=session.id,
            filename="young.txt",
            mime_type="text/plain",
            size=7,
            kind="document",
            storage_path=str(young_path),
        )
        db.session.add_all([old_unlinked, linked, young])
        db.session.commit()
        old_unlinked_id = old_unlinked.id
        linked_id = linked.id
        young_id = young.id

        result = UploadCleanupService().cleanup(older_than=timedelta(hours=24))

        assert result.orphan_records == 1
        assert result.orphan_files == 3
        assert result.failed_files == 0
        assert db.session.get(Attachment, old_unlinked_id) is None
        assert db.session.get(Attachment, linked_id) is not None
        assert db.session.get(Attachment, young_id) is not None

    assert not old_row_path.exists()
    assert not disk_orphan.exists()
    assert not quarantine.exists()
    assert linked_path.exists()
    assert young_path.exists()
    assert unmanaged.exists()


def test_cleanup_dry_run_reports_without_mutating(app):
    upload_dir = Path(app.config["UPLOAD_DIR"])
    old_path = _managed_file(upload_dir, f"{'a' * 32}.txt")
    old = utc_now() - timedelta(hours=48)

    with app.app_context():
        session = ChatSession(title="Dry run")
        db.session.add(session)
        db.session.flush()
        attachment = Attachment(
            session_id=session.id,
            filename="old.txt",
            mime_type="text/plain",
            size=7,
            kind="document",
            storage_path=str(old_path),
            created_at=old,
        )
        db.session.add(attachment)
        db.session.commit()
        attachment_id = attachment.id

        result = UploadCleanupService().cleanup(older_than=timedelta(hours=24), dry_run=True)

        assert result.orphan_records == 1
        assert result.orphan_files == 1
        assert result.dry_run is True
        assert db.session.get(Attachment, attachment_id) is not None

    assert old_path.exists()


def test_cleanup_never_deletes_a_path_still_referenced_by_a_linked_row(app):
    upload_dir = Path(app.config["UPLOAD_DIR"])
    shared_path = _managed_file(upload_dir, f"{'b' * 32}.txt")
    old = utc_now() - timedelta(hours=48)

    with app.app_context():
        session = ChatSession(title="Shared path")
        db.session.add(session)
        db.session.flush()
        message = ChatMessage(session_id=session.id, role="user", content="oi")
        db.session.add(message)
        db.session.flush()
        db.session.add_all(
            [
                Attachment(
                    session_id=session.id,
                    filename="orphan.txt",
                    mime_type="text/plain",
                    size=7,
                    kind="document",
                    storage_path=str(shared_path),
                    created_at=old,
                ),
                Attachment(
                    session_id=session.id,
                    message_id=message.id,
                    filename="linked.txt",
                    mime_type="text/plain",
                    size=7,
                    kind="document",
                    storage_path=str(shared_path),
                    created_at=old,
                ),
            ]
        )
        db.session.commit()

        result = UploadCleanupService().cleanup(older_than=timedelta(hours=24))

        assert result.orphan_records == 1
        assert result.orphan_files == 0
        assert db.session.query(Attachment).count() == 1

    assert shared_path.exists()


def test_cleanup_cli_uses_configured_age(app):
    result = app.test_cli_runner().invoke(args=["cleanup-uploads", "--dry-run"])

    assert result.exit_code == 0
    assert "dry-run" in result.output
    assert "registros_orfaos=0" in result.output


def test_cleanup_rolls_back_rows_and_preserves_files_when_commit_fails(app, monkeypatch):
    upload_dir = Path(app.config["UPLOAD_DIR"])
    old_path = _managed_file(upload_dir, f"{'c' * 32}.txt")
    old = utc_now() - timedelta(hours=48)

    with app.app_context():
        session = ChatSession(title="Commit failure")
        db.session.add(session)
        db.session.flush()
        attachment = Attachment(
            session_id=session.id,
            filename="old.txt",
            mime_type="text/plain",
            size=7,
            kind="document",
            storage_path=str(old_path),
            created_at=old,
        )
        db.session.add(attachment)
        db.session.commit()
        attachment_id = attachment.id

        monkeypatch.setattr(
            db.session,
            "commit",
            lambda: (_ for _ in ()).throw(RuntimeError("database unavailable")),
        )
        with pytest.raises(RuntimeError, match="database unavailable"):
            UploadCleanupService().cleanup(older_than=timedelta(hours=24))

        assert db.session.get(Attachment, attachment_id) is not None

    assert old_path.exists()


def test_cleanup_removes_row_but_never_touches_a_path_outside_upload_dir(app, tmp_path):
    external_path = tmp_path / "external.txt"
    external_path.write_text("must survive", encoding="utf-8")
    old = utc_now() - timedelta(hours=48)

    with app.app_context():
        session = ChatSession(title="Unsafe path")
        db.session.add(session)
        db.session.flush()
        attachment = Attachment(
            session_id=session.id,
            filename="external.txt",
            mime_type="text/plain",
            size=12,
            kind="document",
            storage_path=str(external_path),
            created_at=old,
        )
        db.session.add(attachment)
        db.session.commit()

        result = UploadCleanupService().cleanup(older_than=timedelta(hours=24))

        assert result.orphan_records == 1
        assert result.orphan_files == 0

    assert external_path.read_text(encoding="utf-8") == "must survive"


def test_cleanup_never_resolves_or_unlinks_a_managed_name_symlink(app, monkeypatch):
    upload_dir = Path(app.config["UPLOAD_DIR"])
    symlink_path = _managed_file(upload_dir, f"{'e' * 32}.txt")
    original_is_symlink = Path.is_symlink
    original_resolve = Path.resolve

    def fake_is_symlink(path: Path) -> bool:
        return path == symlink_path or original_is_symlink(path)

    def reject_symlink_resolution(path: Path, *args, **kwargs):
        if path == symlink_path:
            raise AssertionError("cleanup tentou seguir o alvo do symlink")
        return original_resolve(path, *args, **kwargs)

    monkeypatch.setattr(Path, "is_symlink", fake_is_symlink)
    monkeypatch.setattr(Path, "resolve", reject_symlink_resolution)

    with app.app_context():
        assert UploadCleanupService._managed_path(str(symlink_path), upload_dir) is None
        result = UploadCleanupService().cleanup(older_than=timedelta(hours=24))

    assert result.orphan_files == 0
    assert symlink_path.read_text(encoding="utf-8") == "payload"


def test_cleanup_reports_file_removal_failure_without_restoring_deleted_row(
    app, monkeypatch, caplog
):
    upload_dir = Path(app.config["UPLOAD_DIR"])
    old_path = _managed_file(upload_dir, f"{'d' * 32}.txt")
    old = utc_now() - timedelta(hours=48)

    with app.app_context():
        session = ChatSession(title="Filesystem failure")
        db.session.add(session)
        db.session.flush()
        db.session.add(
            Attachment(
                session_id=session.id,
                filename="old.txt",
                mime_type="text/plain",
                size=7,
                kind="document",
                storage_path=str(old_path),
                created_at=old,
            )
        )
        db.session.commit()
        original_unlink = Path.unlink

        def fail_candidate(path: Path, *args, **kwargs):
            if path.resolve() == old_path.resolve():
                raise OSError("filesystem read-only")
            return original_unlink(path, *args, **kwargs)

        monkeypatch.setattr(Path, "unlink", fail_candidate)
        result = UploadCleanupService().cleanup(older_than=timedelta(hours=24))

        assert result.orphan_records == 1
        assert result.orphan_files == 1
        assert result.failed_files == 1
        assert db.session.query(Attachment).count() == 0
        assert "Não foi possível remover upload órfão" in caplog.text

    assert old_path.exists()


def test_cleanup_rejects_a_non_positive_age(app):
    with app.app_context(), pytest.raises(ValueError, match="maior que zero"):
        UploadCleanupService().cleanup(older_than=timedelta(0))
