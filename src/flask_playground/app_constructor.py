from __future__ import annotations

import os
import secrets
import signal
import threading
from collections.abc import Generator
from typing import Any

import flask
import svcs

from ._constants import DOWNLOAD_DIRECTORY
from ._constants import FILE_CLEAN_RECURRANCE_SECONDS
from ._constants import SECRET_KEY_ENV
from .auth.auth import auth_bp
from .file_store import FileStore
from .pizzastore import PizzaStore
from .reports.reports import reports_bp

timers: dict[str, threading.Timer] = {}


def _database_factory() -> Generator[PizzaStore, None, None]:
    """Generate a PizzaStore object for svcs."""
    store = PizzaStore()
    store.connect()
    store.build_table()
    yield store
    store.disconnect()


def _filestore_factory() -> Generator[FileStore, None, None]:
    """Generate a FileStore ojbect for svcs."""
    store = FileStore(DOWNLOAD_DIRECTORY)
    store.setup()
    yield store
    store.teardown()


def construct_app() -> flask.Flask:
    """Build an app with all the things."""
    app = flask.Flask(__name__)
    app.register_blueprint(auth_bp)
    app.register_blueprint(reports_bp)

    app.secret_key = os.getenv(SECRET_KEY_ENV, secrets.token_hex(32))

    svcs.flask.init_app(app)
    svcs.flask.register_factory(
        app=app,
        svc_type=PizzaStore,
        factory=_database_factory,
        ping=lambda svc: svc.health_check(),
    )
    svcs.flask.register_factory(
        app=app,
        svc_type=FileStore,
        factory=_filestore_factory,
        ping=lambda svc: svc.health_check(),
    )

    _start_timers()

    return app


def _start_timers() -> None:
    """Start any timers for background tasks."""
    if os.getenv("APP_TIMERS_STARTED"):
        return

    timers["files"] = threading.Timer(FILE_CLEAN_RECURRANCE_SECONDS, _file_cleaner)
    timers["files"].start()

    signal.signal(signal.SIGINT, _end_timers)
    os.environ["APP_TIMERS_STARTED"] = "true"


def _end_timers(signal_number: int, _: Any) -> None:
    """Cancel all timers."""
    for timer in timers.values():
        timer.cancel()
        timer.join(5.0)


def _file_cleaner() -> None:
    """Runs FileStore cleaning on a regular cycle"""
    try:
        FileStore(DOWNLOAD_DIRECTORY).removed_expired()

    except ConnectionError:
        ...

    timers["files"] = threading.Timer(FILE_CLEAN_RECURRANCE_SECONDS, _file_cleaner)
    timers["files"].start()
