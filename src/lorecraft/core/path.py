"""The path values: a path under the workspace root, spelled from it, and one component of such a path."""

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Final, Self

from lorecraft.core.error import Error


class PathComponentError(Error):
    """A name is empty, is `.` or `..`, or holds a `/`, so it is not one component of a path.

    Attributes:
        name: The rejected name, exactly as supplied.
    """

    name: str

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(
            f'{name!r} is not a path component: it must be non-empty, neither "." nor "..", and hold no "/"'
        )


# order=True so a collection of components sorts by name, the order a directory lists its entries in.
@dataclass(frozen=True, slots=True, order=True)
class PathComponent:
    """One component of a path: a single file or directory name, such as `SKILL.md` or `.agents`.

    A valid component:

    - Is not empty.
    - Is neither `.` nor `..`, which name a directory relative to another rather than an entry in it.
    - Holds no `/`, so it names one entry and never a path below it.

    Parsing never normalizes: a name is accepted exactly as supplied or rejected. Joined onto a
    `RootRelativePath`, a component names a child of that path, never the path itself, its parent or a
    descendant further down.

    Attributes:
        value: The validated name, exactly as supplied.
    """

    value: str

    @classmethod
    def parse(cls, raw: str) -> Self:
        """Return a validated path component.

        Args:
            raw: One file or directory name, as listed or written.

        Raises:
            PathComponentError: If the name is empty, is `.` or `..`, or holds a `/`.
        """
        return cls(raw)

    def __post_init__(self) -> None:
        """Keep direct construction from bypassing the invariant.

        Raises:
            PathComponentError: If the name is empty, is `.` or `..`, or holds a `/`.
        """
        if self.value in ('', '.', '..') or '/' in self.value:
            raise PathComponentError(self.value)

    def __str__(self) -> str:
        """The name exactly as supplied, such as `SKILL.md`."""
        return self.value


class RootRelativePathError(Error):
    """A path is absolute or holds a ``..`` component, so it could name something outside the root.

    Attributes:
        path: The rejected path, as ``PurePosixPath`` spelled it.
    """

    path: PurePosixPath

    def __init__(self, path: PurePosixPath) -> None:
        self.path = path
        super().__init__(f'{str(path)!r} is not root-relative: it must be neither absolute nor hold a ".." component')


# order=True so a collection of paths sorts by path.
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

        Args:
            raw: Path as spelled, with POSIX separators. Normalized as `PurePosixPath` does; empty means the root.

        Raises:
            RootRelativePathError: If the path is absolute or holds a `..` component.
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
        """The path with POSIX separators, such as `docs/code/a.md`, as findings and the workspace tree print it."""
        return str(self.value)

    def __truediv__(self, name: str | PathComponent) -> 'RootRelativePath':
        """This path joined with `name`, checked again: a `..` or an absolute `name` is rejected.

        Args:
            name: Component, or `/`-separated components, to append below this path. A `PathComponent` names
                a child of this path, so joining one is never rejected.

        Raises:
            RootRelativePathError: If the joined path is absolute or holds a `..` component.
        """
        return RootRelativePath(self.value / str(name))

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
        """True when this path is `other` or lies under it; every path lies under the root.

        Args:
            other: Candidate ancestor. Compared lexically, component by component, never as a string prefix.
        """
        return self.value.is_relative_to(other.value)


ROOT: Final[RootRelativePath] = RootRelativePath(PurePosixPath('.'))
"""The workspace root itself, where every walk from the root starts."""
