from __future__ import annotations

import contextlib
import os
import posixpath
import sqlite3
import time
from collections.abc import Generator
from typing import IO
from typing import Any

_INDEX_FILE = ".index"


class FileStore:
    """Manage local file directory creation and cleanup."""

    def __init__(
        self,
        directory: str,
        max_file_age_hours: int = 1,
        *,
        use_site_package_root: bool = False,
        retain_on_exit: bool = False,
    ) -> None:
        """
        Create a FileStore object to manage local file directory creation and cleanup.

        Args:
            directory: Path of the directory from the project root to create for files
            max_file_age_hours: Files older than this are deleted, zero to disable

        Keyword Args:
            use_site_package_root: When true, root is based on the site-packages install
            retain_on_exit: Do not delete files on exit cleanup call

        NOTE: If retain_on_exit is True, max_file_age_hours will still be applied.
        """
        self._max_file_age_hours = max_file_age_hours
        self._use_site_package_root = use_site_package_root
        self._retain_on_exit = retain_on_exit

        self.root = os.path.split(__file__)[0] if use_site_package_root else os.getcwd()

        self.file_directory = self._assemble_directory(directory)
        self._index_file = os.path.join(self.file_directory, _INDEX_FILE)

    def _assemble_directory(self, directory: str) -> str:
        """Safely assemble directory to use. Raise if path escapes given root path."""
        directory = posixpath.normpath(directory)

        if (
            directory == "."
            or directory == ".."
            or directory.startswith("../")
            or os.path.isabs(directory)
        ):
            raise ValueError(f"Unsafe or invalid directory given: {directory}")

        return posixpath.join(self.root, directory)

    @contextlib.contextmanager
    def open(  # noqa: A003 allow shadow of open keyword
        self,
        filename: str,
        mode: str = "w",
        encoding: str = "utf-8",
    ) -> Generator[IO[Any], None, None]:
        """Open a file handler and track in index. For use with a context manager."""
        file = os.path.join(self.file_directory, filename)
        with open(file, mode, encoding=encoding) as filehandler:
            self._save_to_index(file)
            yield filehandler

    def setup(self) -> None:
        """Run all setup required before use."""
        os.makedirs(self.file_directory, exist_ok=True)
        self._create_index_database()

    def teardown(self) -> None:
        """Perform all teardown required after use."""
        ...

    def health_check(self) -> None:
        """Ensure file system is accessable."""
        connection = self._get_index()
        connection.execute("SELECT 1 from fileindex")
        file = os.path.join(self.file_directory, "healthcheck")
        with open(file, "w", encoding="utf-8") as outfile:
            outfile.write("pass")

    def _get_index(self) -> sqlite3.Connection:
        """Connect to index database."""
        return sqlite3.Connection(self._index_file, check_same_thread=False)

    def _create_index_database(self) -> None:
        """Create an sqlite3 database file for indexing files."""
        connection = self._get_index()

        try:
            sql = """\
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS fileindex
                (
                    filename TEXT UNIQUE,
                    expires_at INTEGER
                );"""

            connection.executescript(sql)
            connection.commit()

        finally:
            connection.close()

    def _save_to_index(self, filepath: str) -> None:
        """Save a filepath to the index."""
        expires = int(time.time()) + (self._max_file_age_hours * 3600)
        sql = "INSERT OR IGNORE INTO fileindex (filename, expires_at) VALUES (?, ?);"

        connection = self._get_index()
        try:
            with contextlib.closing(connection.cursor()) as cursor:
                cursor.execute(sql, (filepath, expires))
                connection.commit()

        finally:
            connection.close()

    def _get_expired(self) -> list[str]:
        """Return filepaths to be deleted."""
        now = int(time.time())
        sql = "SELECT filename FROM fileindex WHERE expires_at < ?;"

        connection = self._get_index()
        try:
            with contextlib.closing(connection.cursor()) as cursor:
                results = cursor.execute(sql, (now,)).fetchall()

        finally:
            connection.close()

        return [r[0] for r in results]
