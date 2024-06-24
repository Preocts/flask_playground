from __future__ import annotations

import os
import posixpath


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

    def setup(self) -> None:
        """Run all setup required before use."""
        os.makedirs(self.file_directory, exist_ok=True)

    def teardown(self) -> None:
        """Perform all teardown required after use."""
        ...

    def health_check(self) -> None:
        """Ensure file system is accessable."""
        file = os.path.join(self.file_directory, "healthcheck")
        with open(file, "w", encoding="utf-8") as outfile:
            outfile.write("pass")
