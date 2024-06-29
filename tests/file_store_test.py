from __future__ import annotations

import os
import random
import shutil
import sqlite3
import threading
import time
from collections.abc import Generator

import pytest

from flask_playground import file_store
from flask_playground.file_store import FileStore

TEST_DIRECTORY = "tests/temp_fixture"


@pytest.fixture
def store() -> Generator[FileStore, None, None]:
    """Create a store with an index in a temp location."""
    store = FileStore(TEST_DIRECTORY)
    os.makedirs(TEST_DIRECTORY, exist_ok=True)

    try:
        store.setup()
        yield store

    finally:
        shutil.rmtree(TEST_DIRECTORY)


def test_setup_creates_directory_and_index(store: FileStore) -> None:

    assert os.path.exists(f"{TEST_DIRECTORY}")
    assert os.path.exists(f"{TEST_DIRECTORY}/.index")
    assert os.path.isfile(f"{TEST_DIRECTORY}/.index")


def test_root_defaults_to_cwd() -> None:
    store = FileStore("./foo")

    assert store.root == os.getcwd()
    assert store.file_directory == os.path.join(os.getcwd(), "foo")


def test_root_uses_site_package_path() -> None:
    store = FileStore("./foo", use_site_package_root=True)
    module_path = os.path.split(file_store.__file__)[0]

    assert store.root == module_path
    assert store.file_directory == os.path.join(module_path, "foo")


@pytest.mark.parametrize(
    "directory",
    [os.getcwd(), "foo/../../baz", "../biz", "."],
)
def test_raise_on_invalid_directories(directory: str) -> None:
    with pytest.raises(ValueError):
        FileStore(directory)


@pytest.mark.parametrize(
    "directory",
    ["foo", "baz/biz", "foo/bar/../baz"],
)
def test_accepts_valid_directories(directory: str) -> None:
    store = FileStore(directory)

    assert store


def test_open_places_file_correctly(store: FileStore) -> None:
    with store.open("foobar.txt") as fileout:
        fileout.write("Happy happy")

    assert os.path.exists(f"{TEST_DIRECTORY}/foobar.txt")


def test_assert_filename_is_unique_in_table(store: FileStore) -> None:
    conn = sqlite3.Connection(store._index_file)
    conn.execute("INSERT INTO fileindex (filename, expires_at) VALUES ('f', 0)")

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO fileindex (filename, expires_at) VALUES ('f', 0)")


def test_open_saves_to_index(store: FileStore) -> None:
    conn = sqlite3.Connection(store._index_file)

    with store.open("check_index"):
        ...

    rows = conn.execute("SELECT * FROM fileindex;").fetchall()

    assert len(rows) == 1
    assert rows[0][0] == os.path.join(store.file_directory, "check_index")
    assert rows[0][1] > int(time.time())


def test_open_raises_if_file_already_exists(store: FileStore) -> None:
    conn = sqlite3.Connection(store._index_file)

    with store.open("check_index"):
        ...

    with pytest.raises(FileExistsError):
        with store.open("check_index"):
            ...

    rows = conn.execute("SELECT * FROM fileindex;").fetchall()

    assert len(rows) == 1


def test_healthcheck_passes(store: FileStore) -> None:
    store.health_check()


def test_healthcheck_fails_with_no_database(store: FileStore) -> None:
    os.remove(os.path.join(store.file_directory, ".index"))

    with pytest.raises(sqlite3.OperationalError):
        store.health_check()


def test_removed_expired_handles_missing_files(store: FileStore) -> None:
    store._max_file_age_hours = 0
    with store.open("foo"):
        ...
    with store.open("bar"):
        ...
    with store.open("baz"):
        ...
    os.remove(os.path.join(store.file_directory, "baz"))

    store.removed_expired()

    assert not os.path.exists(os.path.join(store.file_directory, "foo"))
    assert not os.path.exists(os.path.join(store.file_directory, "bar"))
    assert not os.path.exists(os.path.join(store.file_directory, "baz"))


def test_delete_from_index(store: FileStore) -> None:
    now = int(time.time())
    conn = sqlite3.Connection(store._index_file)
    sql = "INSERT INTO fileindex (filename, expires_at) VALUES (?, ?)"
    times = [now - 10, now - 9, now - 8, now + 10]
    values = [(f"mockfile{t}", t) for t in times]
    conn.executemany(sql, values)
    conn.commit()

    store._delete_from_index(
        filepaths=[f"mockfile{now - 10}", f"mockfile{now - 9}", f"mockfile{now - 8}"],
    )

    results = conn.execute("SELECT filename FROM fileindex").fetchall()

    assert results[0] == (f"mockfile{now + 10}",)


def test_connection_exception_raised_when_database_not_exists() -> None:
    shutil.rmtree(TEST_DIRECTORY, ignore_errors=True)
    store = FileStore(TEST_DIRECTORY)

    with pytest.raises(ConnectionError):
        store.removed_expired()


def _writer(store: FileStore, files_to_write: int, flag: threading.Event) -> None:
    flag.wait()
    for _ in range(files_to_write):
        filename = f"mock{random.randrange(0, 100000)}"
        with store.open(filename) as outfile:
            outfile.write("foo")


def test_current_file_saves(store: FileStore) -> None:
    number_of_threads = 50
    files_to_write = 10

    threads = []
    start_flag = threading.Event()

    for _ in range(number_of_threads):
        args = (store, files_to_write, start_flag)
        thread = threading.Thread(target=_writer, args=args)
        threads.append(thread)
        thread.start()

    start_flag.set()

    for thread in threads:
        thread.join()
