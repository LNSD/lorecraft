"""The contract of the filesystem boundary: entry kinds, the error families and the abstract view.

Every path crossing this boundary is a `RootRelativePath` such as `docs/code/logging.md`: never absolute,
never holding a `..` component, so no argument can name a file outside the root. The type carries that
proof, so no implementation checks it again. Nothing above the boundary sees a `Path`, a handle, a stat
result or an mtime. Three operations report where a symlink chain goes: `find_dir` and `find_file` where it
leads, as a resolved directory or file, and `find_root_exit` where it leaves the root.
`list_dir` and `read_text` reach through a link on the way to the path they are given, or at it, and never
report or classify a link's target. `find_entry_kind` reaches
through a link on the way and reports one at the path as a link, as a listing of its parent would. Every
implementation of the view is this package's own: `DiskFileSystem` reads the disk under the workspace
root, and `VirtualFileSystem` answers from a `Snapshot`.
"""

import errno
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import PurePosixPath
from typing import NewType

from lorecraft.core.error import Error
from lorecraft.core.path import RootRelativePath

ResolvedPath = NewType('ResolvedPath', RootRelativePath)
"""A path relative to the workspace root with every symlink on the way followed: no symlink is on the way to it
or at it.

`find_dir` and `find_file` return one. Whether a path is resolved depends on the snapshot it was found in, so
nothing can check it from the value: the distinction is static only. `ResolvedPath / name` is a plain
`RootRelativePath`, since the entry it names may itself be a symlink; code that knows the entry is no symlink wraps it
again, and says why where it does.
"""


class EntryKind(Enum):
    """What a directory entry itself is; symlinks are never followed."""

    FILE = 'file'
    DIRECTORY = 'directory'
    SYMLINK = 'symlink'
    OTHER = 'other'


@dataclass(frozen=True, slots=True)
class DirEntry:
    """One entry of a listed directory.

    Attributes:
        name: The entry's own filename, no directory part.
        kind: The entry's kind from lstat; a symlink is SYMLINK whatever it points at.
    """

    name: str
    kind: EntryKind


@dataclass(frozen=True, slots=True)
class RootExit:
    """Where a walk through a path's symlinks left the root: the link that took it out, and that link's target.

    A walk leaves the root through a link whose target is absolute, which a view spells only for a target outside
    the root, or through a `..` that climbs above the root. Only a link target can hold either, since a root-relative
    path holds no `..`, so the link the walk followed last is the one that took it out. Nothing past it is walked,
    so nothing outside the root is read.

    Attributes:
        link: The symlink, at its resolved path, the walk followed last before it left the root.
        target: That link's target, unresolved: absolute, or relative to the link's directory and climbing with
            `..`. Where it climbs above the root, the `..` that does so may come from an earlier link of the chain.
    """

    link: RootRelativePath
    target: PurePosixPath


class OsRefusal(Enum):
    """Why the operating system refused a call on a path, classified once from its ``errno``.

    The set comes from outside the package, so it is an enum a handler can ``match`` over, and each value is
    the reason as a message states it. A variant translating an ``OSError`` holds one, so nothing above it
    reads the ``OSError`` itself.
    """

    NOT_FOUND = 'no such file or directory'
    PERMISSION_DENIED = 'permission denied'
    NOT_A_DIRECTORY = 'not a directory'
    IS_A_DIRECTORY = 'is a directory'
    OTHER = 'refused by the operating system'

    @classmethod
    def from_error(cls, error: OSError) -> 'OsRefusal':
        """Classify an `OSError` by its `errno`; one the enum does not name is `OTHER`.

        Args:
            error: The failure to classify; only its `errno` is read.
        """
        match error.errno:
            case errno.ENOENT:
                return cls.NOT_FOUND
            case errno.EACCES | errno.EPERM:
                return cls.PERMISSION_DENIED
            case errno.ENOTDIR:
                return cls.NOT_A_DIRECTORY
            case errno.EISDIR:
                return cls.IS_A_DIRECTORY
            case _:
                return cls.OTHER


class DirListError(Error):
    """An existing directory under the root cannot be listed; a missing one is not an error.

    Attributes:
        path: The root-relative directory that could not be listed.
        refusal: Why the operating system refused the listing.
        source: The operating system's failure.
    """

    path: RootRelativePath
    refusal: OsRefusal
    source: OSError

    def __init__(self, path: RootRelativePath, refusal: OsRefusal, *, source: OSError) -> None:
        self.path = path
        self.refusal = refusal
        self.source = source
        super().__init__(f'cannot list directory {path}: {refusal.value}')
        self.__cause__ = source


class FileReadError(Error):
    """A file under the root is missing or cannot be read.

    Attributes:
        path: The root-relative file that could not be read.
        refusal: Why the operating system refused the read.
        source: The operating system's failure.
    """

    path: RootRelativePath
    refusal: OsRefusal
    source: OSError

    def __init__(self, path: RootRelativePath, refusal: OsRefusal, *, source: OSError) -> None:
        self.path = path
        self.refusal = refusal
        self.source = source
        super().__init__(f'cannot read file {path}: {refusal.value}')
        self.__cause__ = source


class UnrecordedFileError(Error):
    """A path leads to no regular file a snapshot recorded, which a view over it answers like a missing file.

    Attributes:
        path: The root-relative path that was read.
    """

    path: RootRelativePath

    def __init__(self, path: RootRelativePath) -> None:
        self.path = path
        super().__init__(f'cannot read file {path}: not in the snapshot')


class TextDecodeError(Error):
    """A file under the root is not UTF-8.

    Attributes:
        path: The root-relative file that could not be decoded.
        source: The decoder's failure, which locates the first byte that does not decode.
    """

    path: RootRelativePath
    source: UnicodeDecodeError

    def __init__(self, path: RootRelativePath, *, source: UnicodeDecodeError) -> None:
        self.path = path
        self.source = source
        super().__init__(f'file {path} is not UTF-8')
        self.__cause__ = source


class EntryInspectError(Error):
    """An existing entry under the root cannot be inspected; a missing one is not an error.

    Attributes:
        path: The root-relative path whose entry could not be inspected.
        refusal: Why the operating system refused the inspection.
        source: The operating system's failure.
    """

    path: RootRelativePath
    refusal: OsRefusal
    source: OSError

    def __init__(self, path: RootRelativePath, refusal: OsRefusal, *, source: OSError) -> None:
        self.path = path
        self.refusal = refusal
        self.source = source
        super().__init__(f'cannot inspect entry {path}: {refusal.value}')
        self.__cause__ = source


class DirResolveError(Error):
    """A path under the root cannot be resolved to a directory because the operating system refused a lookup.

    Attributes:
        path: The root-relative path whose symlink chain could not be followed.
        refusal: Why the operating system refused the lookup.
        source: The operating system's failure.
    """

    path: RootRelativePath
    refusal: OsRefusal
    source: OSError

    def __init__(self, path: RootRelativePath, refusal: OsRefusal, *, source: OSError) -> None:
        self.path = path
        self.refusal = refusal
        self.source = source
        super().__init__(f'cannot resolve directory {path}: {refusal.value}')
        self.__cause__ = source


class FileResolveError(Error):
    """A path under the root cannot be resolved to a file because the operating system refused a lookup.

    Attributes:
        path: The root-relative path whose symlink chain could not be followed.
        refusal: Why the operating system refused the lookup.
        source: The operating system's failure.
    """

    path: RootRelativePath
    refusal: OsRefusal
    source: OSError

    def __init__(self, path: RootRelativePath, refusal: OsRefusal, *, source: OSError) -> None:
        self.path = path
        self.refusal = refusal
        self.source = source
        super().__init__(f'cannot resolve file {path}: {refusal.value}')
        self.__cause__ = source


def decode_text(path: RootRelativePath, data: bytes) -> str:
    """Decode a file's bytes as UTF-8; the one decode every implementation shares.

    Args:
        path: The root-relative file the bytes came from; named in the error, not read.
        data: The file's raw bytes.

    Raises:
        TextDecodeError: If the bytes are not UTF-8.
    """
    try:
        return data.decode('utf-8')
    except UnicodeDecodeError as exc:
        raise TextDecodeError(path, source=exc) from exc


class FileSystem(ABC):
    """Read-only, root-relative view of the files under one workspace root.

    Every ``path`` argument and every returned path is a ``RootRelativePath``, so an implementation joins an
    argument onto its root without checking it: an absolute path or a ``..`` component was rejected when the
    value was built.

    An ABC rather than a Protocol because every implementation is this package's own and must be complete,
    so a missing method fails at instantiation instead of at its first call (error-boundaries §1). With
    ``DiskFileSystem`` and ``VirtualFileSystem``, pattern-repository's second real implementation exists.
    """

    @abstractmethod
    def list_dir(self, path: RootRelativePath) -> tuple[DirEntry, ...]:
        """List one directory non-recursively, sorted by name.

        A symlink on the way to the directory, or at it, is followed; a symlink among its entries is
        listed as SYMLINK, whatever it points at.

        Args:
            path: The root-relative directory to list; the root is `.`.

        Returns:
            The entries in name order, or `()` when the path is missing or leads to no directory.

        Raises:
            DirListError: If the directory exists but cannot be read.
        """

    @abstractmethod
    def read_text(self, path: RootRelativePath) -> str:
        """Read one file as UTF-8 text; a symlink on the way to the file, or at it, is followed.

        Args:
            path: The root-relative file to read.

        Raises:
            TextDecodeError: If the bytes are not UTF-8.
            FileReadError: If the file is missing or cannot be read, on disk.
            UnrecordedFileError: If the path leads to no file a snapshot recorded.
        """

    @abstractmethod
    def find_entry_kind(self, path: RootRelativePath) -> EntryKind | None:
        """What the entry at `path` itself is, as `list_dir` of its parent would list it.

        A symlink on the way to `path` is followed, as `list_dir` follows one to the directory it lists; a
        symlink at `path` is SYMLINK, whatever it points at. The root is a DIRECTORY.

        Args:
            path: The root-relative entry to look up; its own kind is reported, not its target's.

        Returns:
            The entry's kind, or `None` when nothing is there: the path is missing, or its parent leads to
            no directory.

        Raises:
            EntryInspectError: If the entry exists but cannot be inspected.
        """

    @abstractmethod
    def find_dir(self, path: RootRelativePath) -> ResolvedPath | None:
        """Follow every symlink in `path` and return the resolved directory it leads to, root-relative.

        One of the three operations that say where a symlink chain goes, with `find_file` and
        `find_root_exit`, which reports where a chain this one refuses leaves the root: `list_dir` and
        `read_text` follow a link without naming the resolved path. A regular directory resolves to itself,
        and the root resolves to `.`.

        Args:
            path: The root-relative path to resolve; every symlink in it is followed.

        Returns:
            The resolved directory, root-relative, or `None` when no directory under the root sits at the
            end of the chain: the path is missing, a link dangles or loops, a component or the target is
            not a directory, or the target lies outside the root and so has no root-relative spelling. A
            chain that leads outside the root resolves to `None` even when the operating system refuses
            to search a directory on the way.

        Raises:
            DirResolveError: If the operating system refuses the lookup, such as a permission error on a
                component, and the chain does not lead outside the root.
        """

    @abstractmethod
    def find_file(self, path: RootRelativePath) -> ResolvedPath | None:
        """Follow every symlink in `path` and return the resolved regular file it leads to, root-relative.

        `find_dir`'s counterpart for a file: a regular file resolves to itself, and a link to one resolves
        to the file it leads to, wherever the chain goes on the way.

        Args:
            path: The root-relative path to resolve; every symlink in it is followed.

        Returns:
            The resolved file, root-relative, or `None` when no regular file under the root sits at the end of
            the chain: the path is missing, a link dangles or loops, a component is not a directory, the
            target is not a regular file, or it lies outside the root. A chain that leads outside the root
            resolves to `None` even when the operating system refuses to search a directory on the way.

        Raises:
            FileResolveError: If the operating system refuses the lookup, such as a permission error on a
                component, and the chain does not lead outside the root.
        """

    @abstractmethod
    def find_root_exit(self, path: RootRelativePath) -> RootExit | None:
        """Where the symlink chain in `path` leaves the root, or `None` when it stays under it or leads nowhere.

        The walk is the one the scan takes (`root_expansion.find_destination`), so the scan, the scope query and
        both views agree on which chains leave the root. It stops at the link that leaves, so nothing outside the
        root is read: a chain leaves when a link on it has an absolute target outside the root, or a `..` on it
        climbs above the root, whatever directories it stepped into on the way. A chain that dangles or loops
        stays under the root.

        Args:
            path: The root-relative path to walk; every symlink in it is followed until the chain leaves.

        Returns:
            The link the walk followed last before it left, with that link's target, or `None` when the chain
            does not leave the root.

        Raises:
            EntryInspectError: If the operating system refuses to inspect an entry on the way or read a link's
                target, on disk.
        """
