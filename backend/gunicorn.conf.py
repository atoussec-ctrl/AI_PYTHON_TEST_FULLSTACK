"""Gunicorn server configuration.

Paired with `--preload` in the Dockerfile CMD: preload imports the WSGI app
(and therefore runs its Alembic migrations, see
app/__init__.py::_apply_migrations) exactly once in the master process
before forking workers. Without this, each worker would import the app
independently after forking and race to apply the same migration
concurrently — one worker's CREATE TABLE fails on top of the other's.

post_fork then disposes the SQLAlchemy connection pool inherited from the
fork, so each worker opens its own DB connections instead of sharing file
descriptors across processes.
"""

from __future__ import annotations


def post_fork(server, worker) -> None:
    from app.extensions import db
    from run import app

    with app.app_context():
        db.engine.dispose()


def child_exit(server, worker) -> None:
    """Tell the Prometheus multiprocess collector a worker has exited."""
    import os

    from prometheus_client import multiprocess

    if os.getenv("PROMETHEUS_MULTIPROC_DIR"):
        multiprocess.mark_process_dead(worker.pid)
