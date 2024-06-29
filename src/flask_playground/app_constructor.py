from __future__ import annotations

import os
import secrets
import threading
import time
from collections.abc import Generator

import flask
import svcs

from ._constants import DOWNLOAD_DIRECTORY
from ._constants import FILE_CLEAN_RECURRANCE_SECONDS
from ._constants import SECRET_KEY_ENV
from .auth.auth import auth_bp
from .file_store import FileStore
from .pizzastore import PizzaStore
from .reports.reports import reports_bp

THREADS_RUNNING = threading.Event()
threads: list[threading.Thread] = []


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

    THREADS_RUNNING.set()
    threads.append(threading.Thread(target=_file_cleaner))
    threads[-1].start()

    return app


def destruct_app() -> None:
    """Cleanup the app."""
    print("shutting app down")
    THREADS_RUNNING.clear()
    for thread in threads:
        thread.join()


def _file_cleaner() -> None:
    """Runs FileStore cleaning on a regular cycle"""
    next_tic = 0
    while THREADS_RUNNING.is_set():
        if next_tic > int(time.time()):
            continue

        next_tic = int(time.time()) + FILE_CLEAN_RECURRANCE_SECONDS

        FileStore(DOWNLOAD_DIRECTORY).removed_expired()
