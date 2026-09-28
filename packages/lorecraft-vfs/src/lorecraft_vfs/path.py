"""The path value every Lorecraft path is: a path under the workspace root, spelled from it."""

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Final, Self

from lorecraft_core.error import Error


class RootRelativePathError(Error):
    """A path is absolute or holds a ``..`` component, so it could name something outside the root.

    Attributes:
        path: The rejected path, as ``PurePosixPath`` spelled it.
    """

    path: PurePosixPath

    def __init__(self, path: PurePosixPath) -> None:
        self.path = path
        super().__init__(f'{str(path)!r} is not root-relative: it must be neither absolute nor hold a ".." component')


# order=True so a sorted listing, file set or link set sorts by path, as the snapshot's tuples must.
@dataclass(frozen=True, slots=True, order=True)
class RootRelativePath:
    """A path under the workspace root, spelled relative to it with POSIX separators, such as ``docs/code/a.md``.

    A valid path:

    - Is not absolute.
    - Holds no ``..`` component, so no spelling of it climbs out of the root.

    ``.`` is the root itself. Parsing normalizes the way ``PurePosixPath`` does: a repeated or trailing ``/``
    and a ``.`` component are dropped, and the empty string is ``.``. Symlinks are not the type's concern: a
    path that stays under the root lexically may still lead outside it through a link, which only a
    filesystem that follows the link can answer.

    The type is pure: it never touches the disk and holds no ``Path``. There is deliberately no
    ``__fspath__``: a root-relative path is not relative to the working directory, so it must never reach
    ``open`` or ``os`` without its root, and joining it onto one is the filesystem's job.

    Attributes:
        value: The validated path.
    """

    value: PurePosixPath

    @classmethod
    def parse(cls, raw: str) -> Self:
        """Return a validated root-relative path.

        Raises:
            RootRelativePathError: If the path is absolute or holds a ``..`` component.
        """
        return cls(PurePosixPath(raw))

    def __post_init__(self) -> None:
        """Keep direct construction, and every join below, from bypassing the invariant.

        Raises:
            RootRelativePathError: If the path is absolute or holds a ``..`` component.
        """
        if self.value.is_absolute() or '..' in self.value.parts:
            raise RootRelativePathError(self.value)

    def __str__(self) -> str:
        return str(self.value)

    def __truediv__(self, name: str) -> 'RootRelativePath':
        """This path joined with ``name``, checked again: a ``..`` or an absolute ``name`` is rejected.

        Raises:
            RootRelativePathError: If the joined path is absolute or holds a ``..`` component.
        """
        return RootRelativePath(self.value / name)

    @property
    def name(self) -> str:
        """The last component, or ``''`` for the root."""
        return self.value.name

    @property
    def parts(self) -> tuple[str, ...]:
        """The components from the root down; ``()`` for the root."""
        return self.value.parts

    @property
    def parent(self) -> 'RootRelativePath':
        """The directory holding this path; the root is its own parent."""
        return RootRelativePath(self.value.parent)

    @property
    def parents(self) -> tuple['RootRelativePath', ...]:
        """Every ancestor, nearest first and the root last; ``()`` for the root."""
        ancestors: list[RootRelativePath] = []
        for ancestor in self.value.parents:
            ancestors.append(RootRelativePath(ancestor))
        return tuple(ancestors)

    def is_relative_to(self, other: 'RootRelativePath') -> bool:
        """True when this path is ``other`` or lies under it; every path lies under the root."""
        return self.value.is_relative_to(other.value)


ROOT: Final[RootRelativePath] = RootRelativePath(PurePosixPath('.'))
"""The workspace root itself, where every walk from the root starts."""
