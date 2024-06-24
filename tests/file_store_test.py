from __future__ import annotations

import os

import pytest

from flask_playground import file_store
from flask_playground.file_store import FileStore


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
