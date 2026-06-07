"""Cross-platform advisory file lock using portalocker."""
from __future__ import annotations

import portalocker


class FileLock:
    """Context manager that holds an exclusive non-blocking file lock."""

    def __init__(self, path: str) -> None:
        self._path = path
        self._fh = None

    def __enter__(self) -> "FileLock":
        self._fh = open(self._path, "w")
        portalocker.lock(self._fh, portalocker.LOCK_EX | portalocker.LOCK_NB)
        return self

    def __exit__(self, *_: object) -> None:
        if self._fh is not None:
            portalocker.unlock(self._fh)
            self._fh.close()
            self._fh = None
