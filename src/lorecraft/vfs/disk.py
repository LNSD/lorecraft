"""The filesystem view that reads the disk, and the scan that captures the disk as a snapshot.

The workspace root is joined to a root-relative path only inside this module, through ``disk_location``;
every answer leaves it root-relative again.
"""

import errno
import os
import stat
from pathlib import Path, PurePosixPath
from typing import assert_never

from lorecraft.core.error import Error
from lorecraft.core.path import PathComponent, RootRelativePath

from .root_expansion import (
    ResolvedDirectory,
    ResolvedFile,
    find_destination,
    find_linked_scan_root,
    find_listed_scan_root,
)
from .scan_root import ScanRoot
from .snapshot import FileBytes, Link, Listing, Snapshot
from .view import (
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
    decode_text,
)


def disk_location(root: Path, path: RootRelativePath) -> Path:
    """The disk location of `path` under `root`; the one place a root-relative path meets the disk.

    `RootRelativePath` deliberately has no `__fspath__`, so this join is the only way one reaches `open`
    or `os`: never relative to the working directory, always below a root.

    Args:
        root: The workspace root on disk; joined as given, symlinks not resolved.
        path: The root-relative path to locate; `.` yields the root itself.
    """
    return root / path.value


class DiskFileSystem(FileSystem):
    """The view that reads the disk under one workspace root.

    `list_dir`, `read_text` and `find_entry_kind` follow a symlink wherever the operating system does, outside
    the root included; only `find_dir` and `find_file` refuse a chain that leaves the root, and
    `find_root_exit` reports where it leaves. A snapshot never reads outside the root, so there the two views
    differ.
    """

    def __init__(self, root: Path) -> None:
        """Remember the root, resolved once: the constructor's only I/O.

        `find_dir` compares resolved paths against this root, so it must be resolved itself; a caller's
        root, such as a test's raw `tmp_path`, is resolved here rather than at every call.

        Args:
            root: The workspace root directory; may be spelled through symlinks, and is kept in its resolved form.
        """
        self._root = Path(os.path.realpath(root))

    def list_dir(self, path: RootRelativePath) -> tuple[DirEntry, ...]:
        """List one directory on disk; see `FileSystem.list_dir`.

        Args:
            path: The root-relative directory to list; a link on the way, or at it, is followed by the OS.

        Raises:
            DirListError: If the directory exists but cannot be read.
        """
        try:
            entries = _find_listing(self._root, path)
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
        except (FileNotFoundError, NotADirectoryError):  # a missing path has no kind, by contract
            return None
        except OSError as exc:
            if exc.errno == errno.ELOOP:  # a looping link on the way leads to no directory, like a dangling one
                return None
            raise EntryInspectError(path, OsRefusal.from_error(exc), source=exc) from exc
        return _kind_of_mode(mode)

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
        except (FileNotFoundError, NotADirectoryError):  # missing or through a file resolves to None, by contract
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
        # Asked of the path as given, not of ``resolved``: ``realpath`` follows a chain of any length, while the
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
        except (FileNotFoundError, NotADirectoryError):  # missing or through a file resolves to None, by contract
            return None
        except OSError as exc:
            if exc.errno == errno.ELOOP:  # a looping link leads nowhere, exactly like a dangling one
                return None
            # As in ``find_dir``: a target outside the root is never a file under it, so a refused search
            # there is not a failure.
            leads_to = Path(os.path.realpath(disk_location(self._root, path)))
            if not leads_to.is_relative_to(self._root):
                return None
            raise FileResolveError(path, OsRefusal.from_error(exc), source=exc) from exc
        # Asked of the path as given, as in ``find_dir``: nothing opens the file through a chain longer than
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
            EntryInspectError: If an entry on the way cannot be inspected, or a link's target cannot be read.
        """
        leads_to = find_destination(path, _ViewDiskEntries(self._root), follow_links=True)
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
    `_DiskEntries` does, and fails as a view operation does, with `EntryInspectError`.
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
            EntryInspectError: If the path exists but cannot be inspected.
        """
        try:
            return _find_lstat_kind(self._root, path)
        except SnapshotEntryInspectError as exc:
            raise EntryInspectError(path, exc.refusal, source=exc.source) from exc

    def find_link_target(self, path: RootRelativePath) -> PurePosixPath | None:
        """Read the target of the symlink at `path`; `None` when it vanished.

        Args:
            path: The root-relative symlink whose target is read.

        Raises:
            EntryInspectError: If the symlink exists but its target cannot be read.
        """
        try:
            return _find_symlink_target(self._root, path)
        except SnapshotLinkReadError as exc:
            raise EntryInspectError(path, exc.refusal, source=exc.source) from exc

    def may_climb_out_of(self, directory: RootRelativePath) -> bool:
        """Always true: the walk stepped into `directory` only where `lstat` found one; see `EntryLookup`.

        Args:
            directory: The resolved directory the walk climbs out of.
        """
        return True


class SnapshotDirListError(Error):
    """A directory inside the scan scope exists but cannot be listed.

    Attributes:
        path: The root-relative directory the scan stopped at.
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
        super().__init__(f'cannot snapshot directory {path}: {refusal.value}')
        self.__cause__ = source


class SnapshotEntryInspectError(Error):
    """An entry on the way to a scope root, or along a followed link, exists but cannot be inspected.

    Attributes:
        path: The root-relative entry the scan stopped at.
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
        super().__init__(f'cannot snapshot entry {path}: {refusal.value}')
        self.__cause__ = source


class SnapshotFileReadError(Error):
    """A file inside the scan scope, or one a followed link leads to, exists but cannot be read.

    Attributes:
        path: The root-relative file the scan stopped at.
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
        super().__init__(f'cannot snapshot file {path}: {refusal.value}')
        self.__cause__ = source


class SnapshotLinkReadError(Error):
    """A symlink inside the scan scope, or on the way to it, exists but its target cannot be read.

    Attributes:
        path: The root-relative symlink the scan stopped at.
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
        super().__init__(f'cannot snapshot link {path}: {refusal.value}')
        self.__cause__ = source


def take_snapshot(root: Path, scope: tuple[ScanRoot, ...]) -> Snapshot:
    """Read every listing down to each root's depth, every FILE entry's bytes and every symlink's target, once.

    A root with no depth limit is listed all the way down. A missing scope root is simply absent. A file or
    symlink that vanishes between its listing and its read (an editor's write-then-rename) is dropped from the
    listing rather than failing the scan; a directory that vanishes is left unentered. OTHER entries are
    recorded, never read; an absolute link target under the root is recorded relative to the link's directory
    (see `Link`).

    Every symlink met is recorded, and followed only under a scope root that asks for it
    (`ScanRoot.follow_links`). Without it a scope root with a symlink on the way to it is not listed, and a
    symlink entry is neither entered nor read through. With it the scan goes where the link leads, when that
    is under the root: a directory is listed at its resolved path, with the depth left at the link, and a regular
    file has its bytes recorded at its resolved path. Either way every listing and every file sits at a resolved path.
    Every directory a `..` on the way climbs out of is recorded too, so the snapshot's walks take the same steps.
    Under a root that does not follow links, each link it records, and one on the way to the root, is still
    walked for the record alone, so the targets and climbs on its chain are recorded and nothing more is read.
    Where a root starts, where a link leads and the depth it uses up are the rules of `root_expansion.py`,
    which `ScopeIndex.is_in_scope` answers from too.

    Each directory is listed once for each root that asks for more under it than an earlier listing reached,
    so a followed link back to a directory already listed, such as one of its own ancestors, ends the scan
    there instead of looping, at any depth. Such a link to an ancestor still has the scan list that ancestor's
    whole subtree, as deep as the root reaches.

    Args:
        root: The workspace root on disk; nothing outside it is read.
        scope: The directories to read, each with its own depth and link policy; empty yields an empty snapshot.
            Overlapping roots are merged, a directory listed again only when a root asks for more under it. The
            snapshot records it as given, unmerged, so that it answers which paths are in scope by itself.

    Raises:
        SnapshotDirListError: If a directory in scope cannot be listed.
        SnapshotEntryInspectError: If an entry on the way to a scope root, or along the chain of a recorded link,
            cannot be inspected.
        SnapshotFileReadError: If a file in scope, or one a followed link leads to, cannot be read for a reason
            other than having vanished.
        SnapshotLinkReadError: If a symlink's target cannot be read for a reason other than having vanished.
    """
    listings: dict[RootRelativePath, tuple[DirEntry, ...]] = {}
    files: dict[RootRelativePath, bytes] = {}
    links: dict[RootRelativePath, PurePosixPath] = {}
    climbed_directories: set[RootRelativePath] = set()
    on_disk = _DiskEntries(root, links, climbed_directories)
    # The root each directory was last listed as, without following links and with, so overlapping scope roots
    # list a directory again only when a later root asks for more under it: more depth, or its links followed.
    # This is also what ends the scan when a followed link leads back to a directory already listed, such as an
    # ancestor of the link: the root it adds reaches no deeper than the one that listed the directory.
    listed_as: dict[RootRelativePath, ScanRoot] = {}
    followed_as: dict[RootRelativePath, ScanRoot] = {}
    # Each directory still to list, as a root at its resolved path: the depth left there, and the link policy.
    pending: list[ScanRoot] = []
    for scan_root in scope:
        listed_root = find_listed_scan_root(scan_root, on_disk)
        if listed_root is not None:
            pending.append(listed_root)
        if not scan_root.follow_links:
            _record_chain(scan_root.directory, on_disk)

    while pending:
        listed_root = pending.pop()
        directory = listed_root.directory
        follow_links = listed_root.follow_links
        if _is_listed_as_deep(followed_as, listed_root):
            continue  # a listing that followed links covers one that does not
        if not follow_links and _is_listed_as_deep(listed_as, listed_root):
            continue
        try:
            entries = _find_listing(root, directory)
        except OSError as exc:
            raise SnapshotDirListError(directory, OsRefusal.from_error(exc), source=exc) from exc
        if entries is None:
            continue  # vanished after its parent was listed; see the docstring
        if follow_links:
            followed_as[directory] = listed_root
        else:
            listed_as[directory] = listed_root

        kept: list[DirEntry] = []
        for entry in entries:
            path = directory / entry.name
            match entry.kind:
                case EntryKind.DIRECTORY:
                    entered_root = listed_root.find_root_below(path, levels=1)
                    if entered_root is not None:  # None when no depth is left: the entry is listed, never entered
                        pending.append(entered_root)
                case EntryKind.FILE:
                    data = _find_file_bytes(root, path)
                    if data is None:
                        continue  # vanished after the listing; see the docstring
                    files[path] = data
                case EntryKind.SYMLINK:
                    target = _find_symlink_target(root, path)
                    if target is None:
                        continue  # vanished after the listing; see the docstring
                    links[path] = target
                    if follow_links:
                        _follow_listed_link(root, listed_root, path, on_disk, files, pending)
                    else:
                        _record_chain(path, on_disk)
                case EntryKind.OTHER:
                    pass  # recorded in the listing, never read
                case _:
                    assert_never(entry.kind)
            kept.append(entry)
        listings[directory] = tuple(kept)

    return Snapshot(
        listings=tuple(Listing(path, listings[path]) for path in sorted(listings)),
        files=tuple(FileBytes(path, files[path]) for path in sorted(files)),
        links=tuple(Link(path, links[path]) for path in sorted(links)),
        climbed_directories=tuple(sorted(climbed_directories)),
        scope=scope,
    )


def _is_listed_as_deep(listed: dict[RootRelativePath, ScanRoot], scan_root: ScanRoot) -> bool:
    """Whether `listed` records a listing of `scan_root`'s directory that reached at least as deep as it asks.

    Args:
        listed: The root each directory was listed as so far, keyed by its resolved path.
        scan_root: The root a directory is about to be listed as.
    """
    previous = listed.get(scan_root.directory)
    if previous is None:
        return False
    return previous.is_at_least_as_deep_as(scan_root)


class _DiskEntries:
    """What the walks of one scan see on disk: each entry by `lstat`, each link by `readlink`.

    The `EntryLookup` the scan hands to the rules of `root_expansion.py`. Every link target it reads is
    recorded in the scan's links, and every directory a `..` climbs out of in the scan's climbed directories,
    which is what lets `VirtualFileSystem` walk the same chain to the same place and `ScopeIndex` follow it.
    """

    def __init__(
        self,
        root: Path,
        links: dict[RootRelativePath, PurePosixPath],
        climbed_directories: set[RootRelativePath],
    ) -> None:
        """Read under `root`, recording into `links` and `climbed_directories`.

        Args:
            root: The workspace root on disk.
            links: Every symlink the scan recorded so far, keyed by path; mutated with each link target read.
            climbed_directories: Every directory a walk of the scan climbed out of so far; mutated with each climb.
        """
        self._root = root
        self._links = links
        self._climbed_directories = climbed_directories

    def find_kind(self, path: RootRelativePath) -> EntryKind | None:
        """What `path` itself is on disk; see `EntryLookup.find_kind`.

        Args:
            path: The root-relative entry to inspect, every link on the way to it already followed.

        Raises:
            SnapshotEntryInspectError: If the path exists but cannot be inspected.
        """
        return _find_lstat_kind(self._root, path)

    def find_link_target(self, path: RootRelativePath) -> PurePosixPath | None:
        """Read the target of the symlink at `path` and record it in the scan's links; `None` when it vanished.

        Args:
            path: The root-relative symlink whose target is read.

        Raises:
            SnapshotLinkReadError: If the symlink exists but cannot be read.
        """
        target = _find_symlink_target(self._root, path)
        if target is not None:
            self._links[path] = target
        return target

    def may_climb_out_of(self, directory: RootRelativePath) -> bool:
        """Record `directory` in the scan's climbed directories and allow the climb; see `EntryLookup`.

        The walk stepped into `directory` only where `lstat` found one, so the climb is the kernel's. The record
        is what tells a snapshot's walks that it is a directory, where nothing the scan listed shows it.

        Args:
            directory: The resolved directory the walk climbs out of.
        """
        self._climbed_directories.add(directory)
        return True


def _record_chain(path: RootRelativePath, on_disk: _DiskEntries) -> None:
    """Walk the links in `path` for the record alone, under a scope root that does not follow them.

    The scan lists, reads and enters nothing through such a link, but a view still follows it, so the walk's
    only effects are what `on_disk` records on the way: each link target, and each directory a `..` climbs out
    of. Then every chain a view walks over the snapshot is one the scan walked. Nothing outside the root is
    inspected, since the walk stops where a chain leaves it.

    Args:
        path: The root-relative link, or the scope root with a link on the way to it, to walk.
        on_disk: The scan's view of the disk, recording each link and climb met along the chain.

    Raises:
        SnapshotEntryInspectError: If a component of the chain exists but cannot be inspected.
        SnapshotLinkReadError: If a link of the chain exists but its target cannot be read.
    """
    find_destination(path, on_disk, follow_links=True)


def _follow_listed_link(
    root: Path,
    listed_root: ScanRoot,
    link: RootRelativePath,
    on_disk: _DiskEntries,
    files: dict[RootRelativePath, bytes],
    pending: list[ScanRoot],
) -> None:
    """Go where one listed symlink leads, under a scope root that follows links.

    A directory is queued in `pending` as the root `find_linked_scan_root` adds, when the link leaves it one. A
    regular file has its bytes read into `files`, at any depth, as a FILE entry has. A link that leads nowhere
    under the root is left as recorded.

    Args:
        root: The workspace root on disk.
        listed_root: The root the directory holding the link was just listed as, at its resolved path.
        link: The root-relative symlink just listed, already recorded.
        on_disk: The scan's view of the disk, recording each link met along the chain.
        files: File bytes recorded so far, keyed by resolved path; mutated when the link leads to a regular file.
        pending: Directories still to list; mutated when the link leads to a directory the scan lists.

    Raises:
        SnapshotEntryInspectError: If a component of the chain exists but cannot be inspected.
        SnapshotLinkReadError: If a link of the chain exists but its target cannot be read.
        SnapshotFileReadError: If the file the chain leads to exists but cannot be read.
    """
    leads_to = find_destination(link, on_disk, follow_links=True)
    match leads_to:
        case ResolvedDirectory(path=directory):
            linked_root = find_linked_scan_root(listed_root, link, directory)
            if linked_root is not None:
                pending.append(linked_root)
        case ResolvedFile(path=file):
            data = _find_file_bytes(root, file)
            if data is not None:  # None when it vanished after the walk; the link then stays recorded alone
                files[file] = data
        case RootExit() | None:
            pass  # nothing under the root to read there
        case _:
            assert_never(leads_to)


def _find_lstat_kind(root: Path, path: RootRelativePath) -> EntryKind | None:
    """What `path` itself is, a final symlink not followed; `None` when it is missing.

    Args:
        root: The workspace root on disk.
        path: The root-relative entry to inspect; a symlink on the way is the caller's to have followed.

    Raises:
        SnapshotEntryInspectError: If the path exists but cannot be inspected.
    """
    try:
        mode = os.lstat(disk_location(root, path)).st_mode
    except (FileNotFoundError, NotADirectoryError):  # a missing path has no kind, by contract
        return None
    except OSError as exc:
        raise SnapshotEntryInspectError(path, OsRefusal.from_error(exc), source=exc) from exc
    return _kind_of_mode(mode)


def _kind_of_mode(mode: int) -> EntryKind:
    """Classify an `lstat` mode: a symlink is SYMLINK, never what it points at.

    Args:
        mode: The `st_mode` of an `os.lstat` result, so a symlink shows as one.
    """
    if stat.S_ISLNK(mode):
        return EntryKind.SYMLINK
    if stat.S_ISDIR(mode):
        return EntryKind.DIRECTORY
    if stat.S_ISREG(mode):
        return EntryKind.FILE
    return EntryKind.OTHER


def _find_file_bytes(root: Path, path: RootRelativePath) -> bytes | None:
    """A listed file's bytes; `None` when it vanished after the listing.

    Args:
        root: The workspace root on disk.
        path: The root-relative file to read; a final symlink is followed by the OS.

    Raises:
        SnapshotFileReadError: If the file exists but cannot be read.
    """
    try:
        return disk_location(root, path).read_bytes()
    except FileNotFoundError:  # a vanished file is dropped by the caller, by contract
        return None
    except OSError as exc:
        raise SnapshotFileReadError(path, OsRefusal.from_error(exc), source=exc) from exc


def _find_symlink_target(root: Path, path: RootRelativePath) -> PurePosixPath | None:
    """A listed symlink's target as `os.readlink` returns it; `None` when it vanished after the listing.

    An absolute target under the root comes back relative to the link's directory; see
    `_spell_relative_if_under_root`.

    Args:
        root: The workspace root on disk.
        path: The root-relative symlink whose target is read; the link itself, not what it leads to.

    Raises:
        SnapshotLinkReadError: If the symlink exists but cannot be read.
    """
    try:
        target = PurePosixPath(os.readlink(disk_location(root, path)))
    except FileNotFoundError:  # a vanished link is dropped by the caller, by contract
        return None
    except OSError as exc:
        raise SnapshotLinkReadError(path, OsRefusal.from_error(exc), source=exc) from exc
    return _spell_relative_if_under_root(root, path, target)


def _spell_relative_if_under_root(root: Path, link: RootRelativePath, target: PurePosixPath) -> PurePosixPath:
    """Rewrite an absolute `target` naming a path under the root relative to the directory of `link`.

    A snapshot does not record where the root sits, so the virtual view cannot follow an absolute target,
    while the disk view follows one that leads into the root. Spelled from the link's directory, the same
    chain stays inside what the snapshot recorded. The root counts under both spellings: as given, and
    resolved, since the disk view compares resolved paths.

    The link's directory is a resolved path (every listing is, and a walk to a directory steps from one resolved
    directory to the next), so one ``..`` per component of it climbs exactly to the root. The rest of the
    target is kept as written, ``..`` included, for the view to walk the way the kernel does. A relative
    target, or an absolute one outside the root, is returned unchanged.

    Args:
        root: The workspace root on disk; compared both as given and resolved.
        link: The root-relative path of the symlink, whose directory the result is spelled from.
        target: The link's target as `os.readlink` returned it.
    """
    if not target.is_absolute():
        return target
    root_spellings = (PurePosixPath(os.path.abspath(root)), PurePosixPath(os.path.realpath(root)))
    for root_spelling in root_spellings:
        if target.is_relative_to(root_spelling):
            climb_to_root = ['..'] * len(link.parent.parts)
            return PurePosixPath(*climb_to_root, *target.relative_to(root_spelling).parts)
    return target


def _find_listing(root: Path, path: RootRelativePath) -> tuple[DirEntry, ...] | None:
    """List one directory with a single `os.scandir`, sorted by name.

    Args:
        root: The workspace root on disk.
        path: The root-relative directory to list; a link on the way, or at it, is followed by the OS.

    Returns:
        The entries in name order, or ``None`` when the path is missing, is not a directory, or is a link
        that loops.

    Raises:
        OSError: If the directory exists but cannot be read. ``list_dir`` and ``take_snapshot`` each translate it
            into a variant of their own, since each is a different operation failing.
    """
    try:
        with os.scandir(disk_location(root, path)) as scan:
            # os.scandir never yields an empty name, `.`, `..` or a name holding `/`, so parsing never raises here.
            entries = [DirEntry(PathComponent.parse(entry.name), _entry_kind(entry)) for entry in scan]
    except (FileNotFoundError, NotADirectoryError):  # a missing path is None, by contract
        return None
    except OSError as exc:
        if exc.errno == errno.ELOOP:  # a looping link leads to no directory, exactly like a dangling one
            return None
        raise
    entries.sort(key=lambda entry: entry.name)
    return tuple(entries)


def _entry_kind(entry: os.DirEntry[str]) -> EntryKind:
    """Classify a scanned entry by what it is itself, never by what a symlink points at.

    Args:
        entry: An entry from `os.scandir`; no link is followed to classify it.
    """
    if entry.is_symlink():
        return EntryKind.SYMLINK
    if entry.is_dir(follow_symlinks=False):
        return EntryKind.DIRECTORY
    if entry.is_file(follow_symlinks=False):
        return EntryKind.FILE
    return EntryKind.OTHER
