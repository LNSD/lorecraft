"""The view that reads the disk under one workspace root, for tests that compare it with the snapshot's view."""

import errno
import os
from pathlib import Path
from typing import assert_never

from lorecraft.core.path import RootRelativePath
from lorecraft.vfs import (
    DirEntry,
    DirListError,
    DirResolveError,
    EntryInspectError,
    EntryKind,
    FileReadError,
    FileResolveError,
    FileSystem,
    OsRefusal,
    ResolvedPath,
    RootExit,
    RootExitWalkError,
    SnapshotEntryInspectError,
    SnapshotLinkReadError,
    SymlinkTarget,
    disk_location,
)
from lorecraft.vfs.disk import find_listing, find_lstat_kind, find_symlink_target, kind_of_mode
from lorecraft.vfs.root_expansion import ResolvedDirectory, ResolvedFile, find_destination
from lorecraft.vfs.view import decode_text


class DiskFileSystem(FileSystem):
    """The view that reads the disk under one workspace root.

    `list_dir`, `read_text` and `find_entry_kind` follow a symlink wherever the operating system does, outside
    the root included; only `find_dir` and `find_file` refuse a chain that leaves the root, and
    `find_root_exit` reports where it leaves. A snapshot never reads outside the root, so there the two views
    differ.
    """

    def __init__(self, root: Path) -> None:
        """Remember the root, resolved once: the constructor's only I/O.

        Args:
            root: The workspace root directory; may be spelled through symlinks, and is kept in its resolved form.
        """
        # `find_dir` compares resolved paths against this root, so it must be resolved itself; a caller's root, such
        # as a test's raw `tmp_path`, is resolved here rather than at every call.
        self._root = Path(os.path.realpath(root))

    def list_dir(self, path: RootRelativePath) -> tuple[DirEntry, ...]:
        """List one directory on disk; see `FileSystem.list_dir`.

        Args:
            path: The root-relative directory to list; a link on the way, or at it, is followed by the OS.

        Raises:
            DirListError: If the directory exists but cannot be read.
        """
        try:
            entries = find_listing(self._root, path)
        except OSError as exc:
            raise DirListError(path, OsRefusal.from_error(exc), source=exc) from exc
        if entries is None:
            return ()
        return entries

    def read_text(self, path: RootRelativePath) -> str:
        """Read one file on disk as UTF-8 text; see `FileSystem.read_text`.

        Args:
            path: The root-relative file to read; a link on the way, or at it, is followed by the OS.

        Raises:
            TextDecodeError: If the bytes are not UTF-8.
            FileReadError: If the file is missing or cannot be read.
        """
        try:
            data = disk_location(self._root, path).read_bytes()
        except OSError as exc:
            raise FileReadError(path, OsRefusal.from_error(exc), source=exc) from exc
        return decode_text(path, data)

    def find_entry_kind(self, path: RootRelativePath) -> EntryKind | None:
        """What the entry at `path` itself is on disk, from `os.lstat`; see `FileSystem.find_entry_kind`.

        Args:
            path: The root-relative entry to inspect; a final symlink is reported as SYMLINK, not followed.

        Raises:
            EntryInspectError: If the entry exists but cannot be inspected.
        """
        try:
            mode = os.lstat(disk_location(self._root, path)).st_mode
        except FileNotFoundError, NotADirectoryError:  # a missing path has no kind, by contract
            return None
        except OSError as exc:
            if exc.errno == errno.ELOOP:  # a looping link on the way leads to no directory, like a dangling one
                return None
            raise EntryInspectError(path, OsRefusal.from_error(exc), source=exc) from exc
        return kind_of_mode(mode)

    def find_dir(self, path: RootRelativePath) -> ResolvedPath | None:
        """Resolve a directory's symlink chain on disk; see `FileSystem.find_dir`.

        Args:
            path: The root-relative path to resolve; every link in it is followed, in or out of the root.

        Raises:
            DirResolveError: If the operating system refuses the lookup, such as a permission error on a
                component, and the chain does not lead outside the root.
        """
        try:
            resolved = os.path.realpath(disk_location(self._root, path), strict=True)
        except FileNotFoundError, NotADirectoryError:  # missing or through a file resolves to None, by contract
            return None
        except OSError as exc:
            if exc.errno == errno.ELOOP:  # a looping link leads nowhere, exactly like a dangling one
                return None
            # The non-strict walk tolerates the refusal and still says where the chain leads. A target
            # outside the root is never a directory under it, so a refused search there is not a failure.
            leads_to = Path(os.path.realpath(disk_location(self._root, path)))
            if not leads_to.is_relative_to(self._root):
                return None
            raise DirResolveError(path, OsRefusal.from_error(exc), source=exc) from exc
        # Asked of the path as given, not of `resolved`: `realpath` follows a chain of any length, while the
        # operating system gives up past its own limit, and then nothing opens the directory through it.
        if not os.path.isdir(disk_location(self._root, path)):
            return None
        try:
            relative = Path(resolved).relative_to(self._root)
        except ValueError:  # a target outside the root has no root-relative spelling
            return None
        # Resolved: `realpath` followed every symlink on the way, and the root itself is resolved.
        return ResolvedPath(RootRelativePath.parse(relative.as_posix()))

    def find_file(self, path: RootRelativePath) -> ResolvedPath | None:
        """Resolve a file's symlink chain on disk; see `FileSystem.find_file`.

        Args:
            path: The root-relative path to resolve; every link in it is followed, in or out of the root.

        Raises:
            FileResolveError: If the operating system refuses the lookup, such as a permission error on a
                component, and the chain does not lead outside the root.
        """
        try:
            resolved = os.path.realpath(disk_location(self._root, path), strict=True)
        except FileNotFoundError, NotADirectoryError:  # missing or through a file resolves to None, by contract
            return None
        except OSError as exc:
            if exc.errno == errno.ELOOP:  # a looping link leads nowhere, exactly like a dangling one
                return None
            # As in `find_dir`: a target outside the root is never a file under it, so a refused search
            # there is not a failure.
            leads_to = Path(os.path.realpath(disk_location(self._root, path)))
            if not leads_to.is_relative_to(self._root):
                return None
            raise FileResolveError(path, OsRefusal.from_error(exc), source=exc) from exc
        # Asked of the path as given, as in `find_dir`: nothing opens the file through a chain longer than
        # the operating system follows.
        if not os.path.isfile(disk_location(self._root, path)):
            return None
        try:
            relative = Path(resolved).relative_to(self._root)
        except ValueError:  # a target outside the root has no root-relative spelling
            return None
        # Resolved: `realpath` followed every symlink on the way, and the root itself is resolved.
        return ResolvedPath(RootRelativePath.parse(relative.as_posix()))

    def find_root_exit(self, path: RootRelativePath) -> RootExit | None:
        """Where the chain in `path` leaves the root on disk; see `FileSystem.find_root_exit`.

        The walk is the scan's, over each entry's `lstat` and each link's `readlink`, so it agrees with the
        virtual view and reads nothing outside the root. It differs from `find_dir`, which asks the
        operating system: a chain that leaves the root and climbs back into it is followed there, and leaves here.

        Args:
            path: The root-relative path to walk; every link in it is followed until the chain leaves the root.

        Raises:
            RootExitWalkError: If an entry on the way cannot be inspected, or a link's target cannot be read.
        """
        try:
            leads_to = find_destination(path, _ViewDiskEntries(self._root), follow_links=True)
        except (SnapshotEntryInspectError, SnapshotLinkReadError) as exc:
            # The cause is the `OSError` the refusal carries, the same one `source` names, not the wrapper caught here.
            raise RootExitWalkError(path, exc.path, exc.refusal, source=exc.source) from exc.source
        match leads_to:
            case RootExit():
                return leads_to
            case ResolvedDirectory() | ResolvedFile() | None:
                return None
            case _:
                assert_never(leads_to)


class _ViewDiskEntries:
    """What the disk view's walk sees: each entry by `lstat`, each link by `readlink`, recorded nowhere.

    The `EntryLookup` `DiskFileSystem.find_root_exit` hands to `find_destination`. It reads as the scan's
    `_DiskEntries` does, and fails as the scan's does, with `SnapshotEntryInspectError` and `SnapshotLinkReadError`.
    """

    def __init__(self, root: Path) -> None:
        """Read under `root`; performs no I/O.

        Args:
            root: The workspace root on disk, in its resolved form.
        """
        self._root = root

    def find_kind(self, path: RootRelativePath) -> EntryKind | None:
        """What `path` itself is on disk; see `EntryLookup.find_kind`.

        Args:
            path: The root-relative entry to inspect, every link on the way to it already followed.

        Raises:
            SnapshotEntryInspectError: If the path exists but cannot be inspected.
        """
        return find_lstat_kind(self._root, path)

    def find_link_target(self, path: RootRelativePath) -> SymlinkTarget | None:
        """Read the target of the symlink at `path`; `None` when it vanished.

        Args:
            path: The root-relative symlink whose target is read.

        Raises:
            SnapshotLinkReadError: If the symlink exists but its target cannot be read.
        """
        return find_symlink_target(self._root, path)

    def may_climb_out_of(self, directory: RootRelativePath) -> bool:
        """Always true: the walk stepped into `directory` only where `lstat` found one; see `EntryLookup`.

        Args:
            directory: The resolved directory the walk climbs out of.
        """
        return True

    def record_climb(self, directory: RootRelativePath) -> None:
        """Record nothing: this lookup keeps no record of a climb; see `EntryLookup`.

        Args:
            directory: The resolved directory the walk climbed out of.
        """
