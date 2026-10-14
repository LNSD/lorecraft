"""Fixtures shared by the integration tests."""

import stat
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest


@pytest.fixture(scope='function')
def lock() -> Iterator[Callable[[Path], None]]:
    """A function that makes a path refuse every access, restoring each path afterwards for pytest's cleanup.

    Paths are restored in the reverse of the order they were locked, so a parent locked after its child is
    searchable again before the child is restored.
    """
    locked: list[tuple[Path, int]] = []

    def lock_path(path: Path) -> None:
        locked.append((path, stat.S_IMODE(path.stat().st_mode)))
        path.chmod(0o000)

    yield lock_path
    for path, mode in reversed(locked):
        path.chmod(mode)
