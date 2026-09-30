"""The filesystem view that reads the disk, and the scan that captures the disk as a snapshot.

The workspace root is joined to a root-relative path only inside this module, through ``disk_location``;
every answer leaves it root-relative again.
"""

import errno
import os
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from lorecraft.core.error import Error
from lorecraft.core.path import ROOT, RootRelativePath

from .snapshot import MAX_LINKS, FileBytes, Link, Listing, Snapshot
from .view import (
    DirEntry,
    EntryKind,
    EntryKindError,
    FileSystem,
    ListDirError,
    ReadTextError,
    ResolveDirError,
    ResolveFileError,
    decode_text,
)


def disk_location(root: Path, path: RootRelativePath) -> Path:
    """The disk location of ``path`` under ``root``; the one place a root-relative path meets the disk.

    ``RootRelativePath`` deliberately has no ``__fspath__``, so this join is the only way one reaches ``open``
    or ``os``: never relative to the working directory, always below a root.
    """
    return root / path.value


class DiskFileSystem(FileSystem):
    """The view that reads the disk under one workspace root.

    ``list_dir``, ``read_text`` and ``entry_kind`` follow a symlink wherever the operating system does, outside
    the root included; only ``resolve_dir`` and ``resolve_file`` refuse a chain that leaves the root. A
    snapshot never reads outside the root, so there the two views differ.
    """

    def __init__(self, root: Path) -> None:
        """Remember the root, made real once: the constructor's only I/O.

        ``resolve_dir`` compares real paths against this root, so it must be real itself; a caller's root,
        such as a test's raw ``tmp_path``, is resolved here rather than at every call.
        """
        self._root = Path(os.path.realpath(root))

    def list_dir(self, path: RootRelativePath) -> tuple[DirEntry, ...]:
        """List one directory on disk; see ``FileSystem.list_dir``.

        Raises:
            ListDirError: If the directory exists but cannot be read.
        """
        entries = _scan(self._root, path)
        if entries is None:
            return ()
        return entries

    def read_text(self, path: RootRelativePath) -> str:
        """Read one file on disk as UTF-8 text; see ``FileSystem.read_text``.

        Raises:
            DecodeTextError: If the bytes are not UTF-8.
            ReadTextError: If the file is missing or cannot be read.
        """
        try:
            data = disk_location(self._root, path).read_bytes()
        except OSError as exc:
            raise ReadTextError(path, exc.strerror or str(exc)) from exc
        return decode_text(path, data)

    def entry_kind(self, path: RootRelativePath) -> EntryKind | None:
        """What the entry at ``path`` itself is on disk, from ``os.lstat``; see ``FileSystem.entry_kind``.

        Raises:
            EntryKindError: If the entry exists but cannot be inspected.
        """
        try:
            mode = os.lstat(disk_location(self._root, path)).st_mode
        except (FileNotFoundError, NotADirectoryError) as exc:  # noqa: F841 — a missing path has no kind, by contract
            return None
        except OSError as exc:
            if exc.errno == errno.ELOOP:  # a looping link on the way leads to no directory, like a dangling one
                return None
            raise EntryKindError(path, exc.strerror or str(exc)) from exc
        return _kind_of_mode(mode)

    def resolve_dir(self, path: RootRelativePath) -> RootRelativePath | None:
        """Resolve a directory's symlink chain on disk; see ``FileSystem.resolve_dir``.

        Raises:
            ResolveDirError: If the operating system refuses the lookup, such as a permission error on a
                component, and the chain does not lead outside the root.
        """
        try:
            real = os.path.realpath(disk_location(self._root, path), strict=True)
        except (FileNotFoundError, NotADirectoryError) as exc:  # noqa: F841 — missing or through a file resolves to None, by contract
            return None
        except OSError as exc:
            if exc.errno == errno.ELOOP:  # a looping link leads nowhere, exactly like a dangling one
                return None
            # The non-strict walk tolerates the refusal and still says where the chain leads. A target
            # outside the root is never a directory under it, so a refused search there is not a failure.
            leads_to = Path(os.path.realpath(disk_location(self._root, path)))
            if not leads_to.is_relative_to(self._root):
                return None
            raise ResolveDirError(path, exc.strerror or str(exc)) from exc
        # Asked of the path as given, not of ``real``: ``realpath`` follows a chain of any length, while the
        # operating system gives up past its own limit, and then nothing opens the directory through it.
        if not os.path.isdir(disk_location(self._root, path)):
            return None
        try:
            relative = Path(real).relative_to(self._root)
        except ValueError as exc:  # noqa: F841 — a target outside the root has no root-relative spelling
            return None
        return RootRelativePath.parse(relative.as_posix())

    def resolve_file(self, path: RootRelativePath) -> RootRelativePath | None:
        """Resolve a file's symlink chain on disk; see ``FileSystem.resolve_file``.

        Raises:
            ResolveFileError: If the operating system refuses the lookup, such as a permission error on a
                component, and the chain does not lead outside the root.
        """
        try:
            real = os.path.realpath(disk_location(self._root, path), strict=True)
        except (FileNotFoundError, NotADirectoryError) as exc:  # noqa: F841 — missing or through a file resolves to None, by contract
            return None
        except OSError as exc:
            if exc.errno == errno.ELOOP:  # a looping link leads nowhere, exactly like a dangling one
                return None
            # As in ``resolve_dir``: a target outside the root is never a file under it, so a refused search
            # there is not a failure.
            leads_to = Path(os.path.realpath(disk_location(self._root, path)))
            if not leads_to.is_relative_to(self._root):
                return None
            raise ResolveFileError(path, exc.strerror or str(exc)) from exc
        # Asked of the path as given, as in ``resolve_dir``: nothing opens the file through a chain longer than
        # the operating system follows.
        if not os.path.isfile(disk_location(self._root, path)):
            return None
        try:
            relative = Path(real).relative_to(self._root)
        except ValueError as exc:  # noqa: F841 — a target outside the root has no root-relative spelling
            return None
        return RootRelativePath.parse(relative.as_posix())


@dataclass(frozen=True, slots=True)
class ScanRoot:
    """One directory a snapshot reads, how deep, and whether through symlinks.

    Attributes:
        directory: Root-relative directory the scan starts at.
        depth: 0 lists ``directory`` only; 1 also lists each DIRECTORY entry inside it, and so on. Never
            negative. Entries beyond the depth are listed by their parent and never entered.
        follow_links: When true, a symlink that leads somewhere under the root is followed: one on the way
            to ``directory``, and one listed by the scan. A link to a directory costs depth as a DIRECTORY
            entry does, and the directory is listed at its real path, wherever under the root that is. A
            link to a regular file has the file's bytes read, as a FILE entry has, and recorded at the
            file's real path. When false, a symlink is recorded and never followed.
    """

    directory: RootRelativePath
    depth: int
    follow_links: bool = False

    def __post_init__(self) -> None:
        """Reject a negative depth, which would list nothing and read nothing.

        Raises:
            ValueError: If ``depth`` is negative.
        """
        if self.depth < 0:
            raise ValueError(f'depth must be 0 or more, got {self.depth}')


class TakeSnapshotError(Error):
    """A directory, file or symlink inside the scan scope exists but cannot be read.

    Attributes:
        path: The root-relative path the scan stopped at.
    """

    path: RootRelativePath

    def __init__(self, path: RootRelativePath, detail: str) -> None:
        self.path = path
        super().__init__(f'cannot snapshot {path}: {detail}')


def take_snapshot(root: Path, scope: tuple[ScanRoot, ...]) -> Snapshot:
    """Read every listing down to each root's depth, every FILE entry's bytes and every symlink's target, once.

    A missing scope root is simply absent. A file or symlink that vanishes between its listing and its read
    (an editor's write-then-rename) is dropped from the listing rather than failing the scan; a directory
    that vanishes is left unentered. OTHER entries are recorded, never read; an absolute link target under
    the root is recorded relative to the link's directory (see ``Link``).

    Every symlink met is recorded, and followed only under a scope root that asks for it
    (``ScanRoot.follow_links``). Without it a scope root with a symlink on the way to it is not listed, and a
    symlink entry is neither entered nor read through. With it the scan goes where the link leads, when that
    is under the root: a directory is listed at its real path, with the depth left at the link, and a regular
    file has its bytes recorded at its real path. Either way every listing and every file sits at a real path.

    Raises:
        TakeSnapshotError: If a directory in scope cannot be listed, or a file or symlink in it cannot be
            read, for a reason other than having vanished.
    """
    listings: dict[RootRelativePath, tuple[DirEntry, ...]] = {}
    files: dict[RootRelativePath, bytes] = {}
    links: dict[RootRelativePath, PurePosixPath] = {}
    # How deep each directory was listed, without following links and with, so overlapping scope roots list
    # a directory again only when a later root asks for more under it: more depth, or its links followed.
    listed_depth: dict[RootRelativePath, int] = {}
    followed_depth: dict[RootRelativePath, int] = {}
    pending: list[tuple[RootRelativePath, int, bool]] = []
    for scan in scope:
        scope_root = _walk_to_real_path(root, scan.directory, links, follow_links=scan.follow_links)
        if scope_root is not None and scope_root.kind is EntryKind.DIRECTORY:
            pending.append((scope_root.path, scan.depth, scan.follow_links))

    while pending:
        directory, depth, follow_links = pending.pop()
        if followed_depth.get(directory, -1) >= depth:
            continue  # a listing that followed links covers one that does not
        if not follow_links and listed_depth.get(directory, -1) >= depth:
            continue
        try:
            entries = _scan(root, directory)
        except ListDirError as exc:
            raise TakeSnapshotError(directory, exc.detail) from exc
        if entries is None:
            continue  # vanished after its parent was listed; see the docstring
        if follow_links:
            followed_depth[directory] = depth
        else:
            listed_depth[directory] = depth

        kept: list[DirEntry] = []
        for entry in entries:
            path = directory / entry.name
            if entry.kind is EntryKind.DIRECTORY and depth > 0:
                pending.append((path, depth - 1, follow_links))
            elif entry.kind is EntryKind.FILE:
                data = _read_bytes(root, path)
                if data is None:
                    continue  # vanished after the listing; see the docstring
                files[path] = data
            elif entry.kind is EntryKind.SYMLINK:
                target = _read_link(root, path)
                if target is None:
                    continue  # vanished after the listing; see the docstring
                links[path] = target
                if follow_links:
                    _follow_listed_link(root, path, depth, links, files, pending)
            kept.append(entry)
        listings[directory] = tuple(kept)

    return Snapshot(
        listings=tuple(Listing(path, listings[path]) for path in sorted(listings)),
        files=tuple(FileBytes(path, files[path]) for path in sorted(files)),
        links=tuple(Link(path, links[path]) for path in sorted(links)),
    )


def _follow_listed_link(
    root: Path,
    link: RootRelativePath,
    depth: int,
    links: dict[RootRelativePath, PurePosixPath],
    files: dict[RootRelativePath, bytes],
    pending: list[tuple[RootRelativePath, int, bool]],
) -> None:
    """Go where one listed symlink leads, under a scope root that follows links.

    A directory is queued in ``pending`` to be listed one level deeper, when ``depth`` leaves a level: the
    link costs depth as a DIRECTORY entry does. A regular file has its bytes read into ``files``, at any
    depth, as a FILE entry has. A link that leads nowhere under the root is left as recorded.

    Raises:
        TakeSnapshotError: If a component of the chain, or the file it leads to, exists but cannot be read.
    """
    leads_to = _walk_to_real_path(root, link, links, follow_links=True)
    if leads_to is None:
        return
    if leads_to.kind is EntryKind.DIRECTORY and depth > 0:
        pending.append((leads_to.path, depth - 1, True))
    if leads_to.kind is EntryKind.FILE:
        data = _read_bytes(root, leads_to.path)
        if data is not None:  # None when it vanished after the walk; the link then stays recorded alone
            files[leads_to.path] = data


@dataclass(frozen=True, slots=True)
class _RealPath:
    """Where a walk from the root ended.

    Attributes:
        path: The real path, root-relative, with no symlink on the way to it or at it.
        kind: DIRECTORY or FILE; a walk ends nowhere else.
    """

    path: RootRelativePath
    kind: EntryKind


def _walk_to_real_path(
    root: Path, path: RootRelativePath, links: dict[RootRelativePath, PurePosixPath], *, follow_links: bool
) -> _RealPath | None:
    """The real directory or regular file ``path`` leads to, so the scan may read it, or ``None``.

    Walks the components from the root with ``lstat``, one real directory to the next, and records every
    symlink met in ``links``. Without ``follow_links`` the walk ends at the first symlink, which leaves the
    path unread. With it a symlink splices its target into the components still to walk, as the kernel
    does and as ``VirtualFileSystem`` does over the snapshot: recording each link of the chain is what lets
    that view walk the same chain to the same place.

    The view knows a directory only by what the snapshot recorded in it or under it. A directory the walk
    stepped into by name since the last link has nothing recorded in it yet, so a ``..`` climbing back out
    of one, as in ``tmp/../review``, makes a chain the view could not walk: the walk ends there instead of
    reading what the view would not reach. A ``..`` climbing out of the directory a link sits in is followed,
    since the recorded link makes that directory and its ancestors known.

    A snapshot has no record for a lone file, so a scope root that is one is seen only through a listing of
    its parent: a scope that must answer whether a root exists lists that parent too.

    Returns:
        The real path and its kind, or ``None`` when no directory or regular file under the root is there:
        a component is missing, a component on the way is no directory, the last one is neither a
        directory, a regular file nor a symlink, a symlink is not followed, its target is absolute (so
        outside the root, see ``_read_link``) or climbs above the root, a ``..`` climbs out of a directory
        the walk stepped into, or the chain is longer than ``MAX_LINKS``.

    Raises:
        TakeSnapshotError: If a component exists but cannot be inspected, or its link cannot be read.
    """
    resolved = ROOT
    remaining = list(path.parts)
    links_followed = 0
    stepped_into_since_last_link = 0
    while remaining:
        part = remaining.pop(0)
        if part == '..':
            if resolved == ROOT or stepped_into_since_last_link > 0:
                return None
            resolved = resolved.parent
            continue
        candidate = resolved / part
        kind = _lstat_kind(root, candidate)
        if kind is EntryKind.DIRECTORY:
            resolved = candidate
            stepped_into_since_last_link += 1
            continue
        if kind is EntryKind.FILE and not remaining:
            return _RealPath(candidate, EntryKind.FILE)
        if kind is not EntryKind.SYMLINK:
            return None
        target = _read_link(root, candidate)
        if target is None:
            return None  # vanished after the lstat, so nothing is there to follow
        links[candidate] = target
        links_followed += 1
        if not follow_links or target.is_absolute() or links_followed > MAX_LINKS:
            return None
        remaining = list(target.parts) + remaining
        stepped_into_since_last_link = 0
    return _RealPath(resolved, EntryKind.DIRECTORY)


def _lstat_kind(root: Path, path: RootRelativePath) -> EntryKind | None:
    """What ``path`` itself is, a final symlink not followed; ``None`` when it is missing.

    Raises:
        TakeSnapshotError: If the path exists but cannot be inspected.
    """
    try:
        mode = os.lstat(disk_location(root, path)).st_mode
    except (FileNotFoundError, NotADirectoryError) as exc:  # noqa: F841 — a missing path has no kind, by contract
        return None
    except OSError as exc:
        raise TakeSnapshotError(path, exc.strerror or str(exc)) from exc
    return _kind_of_mode(mode)


def _kind_of_mode(mode: int) -> EntryKind:
    """Classify an ``lstat`` mode: a symlink is SYMLINK, never what it points at."""
    if stat.S_ISLNK(mode):
        return EntryKind.SYMLINK
    if stat.S_ISDIR(mode):
        return EntryKind.DIRECTORY
    if stat.S_ISREG(mode):
        return EntryKind.FILE
    return EntryKind.OTHER


def _read_bytes(root: Path, path: RootRelativePath) -> bytes | None:
    """A listed file's bytes; ``None`` when it vanished after the listing.

    Raises:
        TakeSnapshotError: If the file exists but cannot be read.
    """
    try:
        return disk_location(root, path).read_bytes()
    except FileNotFoundError as exc:  # noqa: F841 — a vanished file is dropped by the caller, by contract
        return None
    except OSError as exc:
        raise TakeSnapshotError(path, exc.strerror or str(exc)) from exc


def _read_link(root: Path, path: RootRelativePath) -> PurePosixPath | None:
    """A listed symlink's target as ``os.readlink`` returns it; ``None`` when it vanished after the listing.

    An absolute target under the root comes back relative to the link's directory; see
    ``_spell_relative_if_under_root``.

    Raises:
        TakeSnapshotError: If the symlink exists but cannot be read.
    """
    try:
        target = PurePosixPath(os.readlink(disk_location(root, path)))
    except FileNotFoundError as exc:  # noqa: F841 — a vanished link is dropped by the caller, by contract
        return None
    except OSError as exc:
        raise TakeSnapshotError(path, exc.strerror or str(exc)) from exc
    return _spell_relative_if_under_root(root, path, target)


def _spell_relative_if_under_root(root: Path, link: RootRelativePath, target: PurePosixPath) -> PurePosixPath:
    """Rewrite an absolute ``target`` naming a path under the root relative to the directory of ``link``.

    A snapshot does not record where the root sits, so the virtual view cannot follow an absolute target,
    while the disk view follows one that leads into the root. Spelled from the link's directory, the same
    chain stays inside what the snapshot recorded. The root counts under both spellings: as given, and made
    real, since the disk view compares real paths.

    The link's directory is a real path (every listing is, and a walk to a directory steps from one real
    directory to the next), so one ``..`` per component of it climbs exactly to the root. The rest of the
    target is kept as written, ``..`` included, for the view to walk the way the kernel does. A relative
    target, or an absolute one outside the root, is returned unchanged.
    """
    if not target.is_absolute():
        return target
    root_spellings = (PurePosixPath(os.path.abspath(root)), PurePosixPath(os.path.realpath(root)))
    for root_spelling in root_spellings:
        if target.is_relative_to(root_spelling):
            climb_to_root = ['..'] * len(link.parent.parts)
            return PurePosixPath(*climb_to_root, *target.relative_to(root_spelling).parts)
    return target


def _scan(root: Path, path: RootRelativePath) -> tuple[DirEntry, ...] | None:
    """List one directory with a single ``os.scandir``, sorted by name.

    Returns:
        The entries in name order, or ``None`` when the path is missing, is not a directory, or is a link
        that loops.

    Raises:
        ListDirError: If the directory exists but cannot be read.
    """
    try:
        with os.scandir(disk_location(root, path)) as scan:
            entries = [DirEntry(entry.name, _entry_kind(entry)) for entry in scan]
    except (FileNotFoundError, NotADirectoryError) as exc:  # noqa: F841 — a missing path is None, by contract
        return None
    except OSError as exc:
        if exc.errno == errno.ELOOP:  # a looping link leads to no directory, exactly like a dangling one
            return None
        raise ListDirError(path, exc.strerror or str(exc)) from exc
    entries.sort(key=lambda entry: entry.name)
    return tuple(entries)


def _entry_kind(entry: os.DirEntry[str]) -> EntryKind:
    """Classify a scanned entry by what it is itself, never by what a symlink points at."""
    if entry.is_symlink():
        return EntryKind.SYMLINK
    if entry.is_dir(follow_symlinks=False):
        return EntryKind.DIRECTORY
    if entry.is_file(follow_symlinks=False):
        return EntryKind.FILE
    return EntryKind.OTHER
