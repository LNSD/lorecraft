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

from .path import ROOT, RootRelativePath
from .snapshot import MAX_LINKS, FileBytes, Link, Listing, Snapshot
from .view import DirEntry, EntryKind, FileSystem, ListDirError, ReadTextError, ResolveDirError, decode_text


def disk_location(root: Path, path: RootRelativePath) -> Path:
    """The disk location of ``path`` under ``root``; the one place a root-relative path meets the disk.

    ``RootRelativePath`` deliberately has no ``__fspath__``, so this join is the only way one reaches ``open``
    or ``os``: never relative to the working directory, always below a root.
    """
    return root / path.value


class DiskFileSystem(FileSystem):
    """The view that reads the disk under one workspace root."""

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
        if not os.path.isdir(real):
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
        follow_links: When true, a symlink that leads to a directory under the root is followed: one on the
            way to ``directory``, and one listed within the depth, which is entered as a DIRECTORY entry is.
            The directory it leads to is listed at its real path, wherever under the root that is. When
            false, a symlink is recorded and never followed.
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
    symlink entry is never entered. With it the scan lists the directory the link leads to, when that is a
    directory under the root, at its real path and with the depth left at the link. Either way every listing
    sits at a real path; a link to a file is never read through.

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
        scope_root = _walk_to_directory(root, scan.directory, links, follow_links=scan.follow_links)
        if scope_root is not None:
            pending.append((scope_root, scan.depth, scan.follow_links))

    while pending:
        directory, depth, follow_links = pending.pop()
        if followed_depth.get(directory, -1) >= depth:
            continue  # a listing that followed links covers one that does not
        # At depth 0 no entry is entered, so there is no link to follow and a plain listing covers it too.
        if (not follow_links or depth == 0) and listed_depth.get(directory, -1) >= depth:
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
                if follow_links and depth > 0:
                    leads_to = _walk_to_directory(root, path, links, follow_links=True)
                    if leads_to is not None:
                        pending.append((leads_to, depth - 1, follow_links))
            kept.append(entry)
        listings[directory] = tuple(kept)

    return Snapshot(
        listings=tuple(Listing(path, listings[path]) for path in sorted(listings)),
        files=tuple(FileBytes(path, files[path]) for path in sorted(files)),
        links=tuple(Link(path, links[path]) for path in sorted(links)),
    )


def _walk_to_directory(
    root: Path, path: RootRelativePath, links: dict[RootRelativePath, PurePosixPath], *, follow_links: bool
) -> RootRelativePath | None:
    """The real directory ``path`` leads to, so the scan may list it, or ``None`` when it may not.

    Walks the components from the root with ``lstat``, one real directory to the next, and records every
    symlink met in ``links``. Without ``follow_links`` the walk ends at the first symlink, which leaves the
    path unlisted. With it a symlink splices its target into the components still to walk, as the kernel
    does and as ``VirtualFileSystem.resolve_dir`` does over the snapshot: recording each link of the chain
    is what lets that view walk the same chain to the same directory.

    A snapshot has no record for a lone file, so a component that is one is seen only through a listing of
    its parent: a scope that must answer whether a root exists lists that parent too. Nor has it one for a
    directory a chain only passes through and climbs back out of with ``..``, which the view does not know.

    Returns:
        The real directory, root-relative, or ``None`` when no directory under the root is there: a
        component is missing or is neither a directory nor a symlink, a symlink is not followed, its
        target is absolute (so outside the root, see ``_read_link``) or climbs above the root, or the
        chain is longer than ``MAX_LINKS``.

    Raises:
        TakeSnapshotError: If a component exists but cannot be inspected, or its link cannot be read.
    """
    resolved = ROOT
    remaining = list(path.parts)
    links_followed = 0
    while remaining:
        part = remaining.pop(0)
        if part == '..':
            if resolved == ROOT:
                return None
            resolved = resolved.parent
            continue
        candidate = resolved / part
        kind = _lstat_kind(root, candidate)
        if kind is EntryKind.DIRECTORY:
            resolved = candidate
            continue
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
    return resolved


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
        The entries in name order, or ``None`` when the path is missing or is not a directory.

    Raises:
        ListDirError: If the directory exists but cannot be read.
    """
    try:
        with os.scandir(disk_location(root, path)) as scan:
            entries = [DirEntry(entry.name, _entry_kind(entry)) for entry in scan]
    except (FileNotFoundError, NotADirectoryError) as exc:  # noqa: F841 — a missing path is None, by contract
        return None
    except OSError as exc:
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
