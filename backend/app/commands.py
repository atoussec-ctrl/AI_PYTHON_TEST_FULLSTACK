"""Operational Flask CLI commands."""

from __future__ import annotations

from datetime import timedelta

import click
from flask import Flask, current_app
from flask.cli import with_appcontext

from app.services.upload_cleanup import UploadCleanupService


@click.command("cleanup-uploads")
@click.option(
    "--older-than-hours",
    type=click.IntRange(min=1),
    default=None,
    help="Remove uploads não vinculados mais antigos que este valor.",
)
@click.option("--dry-run", is_flag=True, help="Somente relata candidatos, sem remover nada.")
@with_appcontext
def cleanup_uploads(older_than_hours: int | None, dry_run: bool) -> None:
    """Remove stale attachment rows, quarantines and unreferenced files."""
    hours = older_than_hours or int(current_app.config["ORPHAN_UPLOAD_MAX_AGE_HOURS"])
    result = UploadCleanupService().cleanup(older_than=timedelta(hours=hours), dry_run=dry_run)
    mode = "dry-run" if dry_run else "executado"
    click.echo(
        f"cleanup_uploads {mode}: registros_orfaos={result.orphan_records} "
        f"arquivos_orfaos={result.orphan_files} falhas={result.failed_files}"
    )


def register_commands(app: Flask) -> None:
    app.cli.add_command(cleanup_uploads)
