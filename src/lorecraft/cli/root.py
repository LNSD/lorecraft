"""Establish the workspace root: the directory whose ``docs/__meta__/`` the checks read.

Two ways in. An explicit ``--root`` is resolved and required to be a directory; without one, the nearest of
the working directory and its parents holding ``docs/__meta__/`` is the root. Either way the result is an
absolute path with symlinks followed, and it is the only ``Path`` a command keeps: everything below reads
root-relative through ``FileSystem``, and the root itself is handed only to ``select_document``.
"""

from pathlib import Path

from lorecraft.core.error import Error
from lorecraft.project.layout import SPECS_DIR
from lorecraft.vfs import disk_location


class RootError(Error):
    """A workspace root cannot be established."""


class RootNotFoundError(RootError):
    """Neither ``start`` nor any of its parents holds ``docs/__meta__/``.

    Attributes:
        start: The directory the search began at, as given.
    """

    start: Path

    def __init__(self, start: Path) -> None:
        self.start = start
        super().__init__('cannot find repository root: no parent contains docs/__meta__/')


class InvalidRootError(RootError):
    """An explicit root is not an existing directory.

    Attributes:
        path: The rejected root, resolved.
    """

    path: Path

    def __init__(self, path: Path) -> None:
        self.path = path
        super().__init__(f'{path} is not an existing directory')


def find_root(start: Path) -> Path:
    """The first of ``start`` and its parents holding ``docs/__meta__/`` as a directory, resolved.

    Raises:
        RootNotFoundError: If no directory from ``start`` upward holds ``docs/__meta__/``.
    """
    # A relative start has parents that stop at `.`, so resolve first to climb the real directory tree.
    resolved = start.resolve()
    for candidate in (resolved, *resolved.parents):
        if disk_location(candidate, SPECS_DIR).is_dir():
            return candidate
    raise RootNotFoundError(start)


def resolve_root(path: Path) -> Path:
    """Resolve an explicit root (symlinks followed) and require it to be a directory.

    Raises:
        InvalidRootError: If the resolved path is not an existing directory.
    """
    resolved = path.resolve()
    if not resolved.is_dir():
        raise InvalidRootError(resolved)
    return resolved
