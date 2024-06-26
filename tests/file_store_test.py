from __future__ import annotations

import os
import shutil
import sqlite3
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


def test_open_ignores_indexing_files_already_indexed(store: FileStore) -> None:
    conn = sqlite3.Connection(store._index_file)

    with store.open("check_index"):
        ...
    with store.open("check_index"):
        ...

    rows = conn.execute("SELECT * FROM fileindex;").fetchall()

    assert len(rows) == 1
