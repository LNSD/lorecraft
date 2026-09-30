"""The contract of the filesystem boundary: entry kinds, the error families and the abstract view.

Every path crossing this boundary is a ``RootRelativePath`` such as ``docs/code/logging.md``: never absolute,
never holding a ``..`` component, so no argument can name a file outside the root. The type carries that
proof, so no implementation checks it again. Nothing above the boundary sees a ``Path``, a handle, a stat
result or an mtime. ``resolve_dir`` and ``resolve_file`` are the two operations that report where a symlink
chain leads, as a root-relative directory or file; ``list_dir`` and ``read_text`` reach through a link on the
way to the path they are given, or at it, and never report or classify a link's target. ``entry_kind`` reaches
through a link on the way and reports one at the path as a link, as a listing of its parent would. Every
implementation of the view is this package's own: ``DiskFileSystem`` reads the disk under the workspace
root, and ``VirtualFileSystem`` answers from a ``Snapshot``.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

from lorecraft.core.error import Error

from .path import RootRelativePath


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


class ListDirError(Error):
    """An existing directory under the root cannot be listed; a missing one is not an error.

    Attributes:
        path: The root-relative directory that could not be listed.
        detail: The operating system's own description of the failure.
    """

    path: RootRelativePath
    detail: str

    def __init__(self, path: RootRelativePath, detail: str) -> None:
        self.path = path
        self.detail = detail
        super().__init__(f'cannot list directory {path}: {detail}')


class ReadTextError(Error):
    """A file under the root cannot be read.

    Attributes:
        path: The root-relative file that could not be read.
        detail: The operating system's or decoder's own description of the failure.
    """

    path: RootRelativePath
    detail: str

    def __init__(self, path: RootRelativePath, detail: str) -> None:
        self.path = path
        self.detail = detail
        super().__init__(f'cannot read file {path}: {detail}')


class DecodeTextError(ReadTextError):
    """A file under the root is not UTF-8."""


class EntryKindError(Error):
    """An existing entry under the root cannot be inspected; a missing one is not an error.

    Attributes:
        path: The root-relative path whose entry could not be inspected.
        detail: The operating system's own description of the failure.
    """

    path: RootRelativePath
    detail: str

    def __init__(self, path: RootRelativePath, detail: str) -> None:
        self.path = path
        self.detail = detail
        super().__init__(f'cannot inspect entry {path}: {detail}')


class ResolveDirError(Error):
    """A path under the root cannot be resolved because the operating system refused a lookup.

    Attributes:
        path: The root-relative path whose symlink chain could not be followed.
        detail: The operating system's own description of the refusal.
    """

    path: RootRelativePath
    detail: str

    def __init__(self, path: RootRelativePath, detail: str) -> None:
        self.path = path
        self.detail = detail
        super().__init__(f'cannot resolve directory {path}: {detail}')


class ResolveFileError(Error):
    """A path under the root cannot be resolved to a file because the operating system refused a lookup.

    Attributes:
        path: The root-relative path whose symlink chain could not be followed.
        detail: The operating system's own description of the refusal.
    """

    path: RootRelativePath
    detail: str

    def __init__(self, path: RootRelativePath, detail: str) -> None:
        self.path = path
        self.detail = detail
        super().__init__(f'cannot resolve file {path}: {detail}')


def decode_text(path: RootRelativePath, data: bytes) -> str:
    """Decode a file's bytes as UTF-8; the one decode every implementation shares.

    Raises:
        DecodeTextError: If the bytes are not UTF-8.
    """
    try:
        return data.decode('utf-8')
    except UnicodeDecodeError as exc:
        raise DecodeTextError(path, str(exc)) from exc


class FileSystem(ABC):
    """Read-only, root-relative view of the files under one workspace root.

    Every ``path`` argument and every returned path is a ``RootRelativePath``, so an implementation joins an
    argument onto its root without checking it: an absolute path or a ``..`` component was rejected when the
    value was built.

    An ABC rather than a Protocol because every implementation is this package's own and must be complete,
    so a missing method fails at instantiation instead of at its first call (python-exceptions §1). With
    ``DiskFileSystem`` and ``VirtualFileSystem``, pattern-repository's second real implementation exists.
    """

    @abstractmethod
    def list_dir(self, path: RootRelativePath) -> tuple[DirEntry, ...]:
        """List one directory non-recursively, sorted by name.

        A symlink on the way to the directory, or at it, is followed; a symlink among its entries is
        listed as SYMLINK, whatever it points at.

        Returns:
            The entries in name order, or ``()`` when the path is missing or leads to no directory.

        Raises:
            ListDirError: If the directory exists but cannot be read.
        """

    @abstractmethod
    def read_text(self, path: RootRelativePath) -> str:
        """Read one file as UTF-8 text; a symlink on the way to the file, or at it, is followed.

        Raises:
            DecodeTextError: If the bytes are not UTF-8.
            ReadTextError: If the file is missing or cannot be read.
        """

    @abstractmethod
    def entry_kind(self, path: RootRelativePath) -> EntryKind | None:
        """What the entry at ``path`` itself is, as ``list_dir`` of its parent would list it.

        A symlink on the way to ``path`` is followed, as ``list_dir`` follows one to the directory it lists; a
        symlink at ``path`` is SYMLINK, whatever it points at. The root is a DIRECTORY.

        Returns:
            The entry's kind, or ``None`` when nothing is there: the path is missing, or its parent leads to
            no directory.

        Raises:
            EntryKindError: If the entry exists but cannot be inspected.
        """

    @abstractmethod
    def resolve_dir(self, path: RootRelativePath) -> RootRelativePath | None:
        """Follow every symlink in ``path`` and return the real directory it leads to, root-relative.

        One of the two operations that say where a symlink leads, with ``resolve_file``: ``list_dir`` and
        ``read_text`` follow a link without naming the real path. A regular directory resolves to itself,
        and the root resolves to ``.``.

        Returns:
            The real directory, root-relative, or ``None`` when no directory under the root sits at the
            end of the chain: the path is missing, a link dangles or loops, a component or the target is
            not a directory, or the target lies outside the root and so has no root-relative spelling. A
            chain that leads outside the root resolves to ``None`` even when the operating system refuses
            to search a directory on the way.

        Raises:
            ResolveDirError: If the operating system refuses the lookup, such as a permission error on a
                component, and the chain does not lead outside the root.
        """

    @abstractmethod
    def resolve_file(self, path: RootRelativePath) -> RootRelativePath | None:
        """Follow every symlink in ``path`` and return the real regular file it leads to, root-relative.

        ``resolve_dir``'s counterpart for a file: a regular file resolves to itself, and a link to one resolves
        to the file it leads to, wherever the chain goes on the way.

        Returns:
            The real file, root-relative, or ``None`` when no regular file under the root sits at the end of
            the chain: the path is missing, a link dangles or loops, a component is not a directory, the
            target is not a regular file, or it lies outside the root. A chain that leads outside the root
            resolves to ``None`` even when the operating system refuses to search a directory on the way.

        Raises:
            ResolveFileError: If the operating system refuses the lookup, such as a permission error on a
                component, and the chain does not lead outside the root.
        """
