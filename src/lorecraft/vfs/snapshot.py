"""What one scan of the workspace saw, as a value, and the view that answers from it.

A `Snapshot` holds the scope it was taken of, listings, file bytes and symlink targets, never a handle or a
stat result, so two snapshots compare and hash structurally. `VirtualFileSystem` answers every `FileSystem`
operation from one snapshot without touching the disk. `take_snapshot` in `disk.py` is the producer that
reads the disk; `Snapshot.from_files` builds one by hand.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Self, assert_never

from lorecraft.core.path import ROOT, RootRelativePath

from .root_expansion import RealPath, find_real_path
from .scan_root import ScanRoot
from .view import DirEntry, EntryKind, FileSystem, RootExit, UnrecordedFileError, decode_text


@dataclass(frozen=True, slots=True)
class Listing:
    """One directory's entries as ``list_dir`` returns them.

    Attributes:
        path: The root-relative directory.
        entries: Its entries, sorted by name.
    """

    path: RootRelativePath
    entries: tuple[DirEntry, ...]


@dataclass(frozen=True, slots=True)
class FileBytes:
    """One regular file's bytes.

    Attributes:
        path: The root-relative file.
        data: Its whole content, undecoded.
    """

    path: RootRelativePath
    data: bytes


@dataclass(frozen=True, slots=True)
class Link:
    """One symlink and the target it names, as ``os.readlink`` returned it, save one rewrite.

    ``take_snapshot`` rewrites an absolute target that names a path under the root relative to the link's
    own directory, so the virtual view can follow it the way the disk view does; a snapshot never records
    where the root sits.

    Attributes:
        path: The root-relative symlink.
        target: The target, unresolved: relative to the link's own directory, or absolute and outside the
            root. A plain ``PurePosixPath``, not a ``RootRelativePath``: it is spelled from the link's
            directory and may climb with ``..``, which only a walk through the link interprets.
    """

    path: RootRelativePath
    target: PurePosixPath


@dataclass(frozen=True, slots=True)
class Snapshot:
    """What one scan saw: its scope, every listing, every FILE entry's bytes and every link's target. Never mutated.

    Tuples only, so two snapshots compare and hash structurally; equality is the "nothing changed" test, the
    scope included. Bytes, not text: a non-UTF-8 file stays here so `read_text` raises `TextDecodeError`
    exactly as the disk view does; byte equality is the change test mtime is not. What a scan reads is the
    scope it is given, and the snapshot records that scope, so whether a path is in scope is answered from the
    snapshot alone. A link is always recorded, and followed only under a scan root that asks for it: where the
    scan did not follow one that leads outside the scope, what the disk view reads through it is not here.

    Every listing, file, link and climbed directory sits at a real path, with no symlink on the way to it. So
    when the virtual view follows a chain, it treats as a directory every listing, every climbed directory, and
    every ancestor of a listing, a file, a link or a climbed directory.

    Reserved, not implemented: `with_file(path, data) -> Snapshot`, a copy with one file's bytes
    replaced (and a FILE entry added to the parent listing when absent), for a server pushing unsaved
    buffers. It is a rebuild of `files` with one record replaced and of one `Listing`; keep the
    representation such that it stays so. A partial rescan, by contrast, cannot drop one record alone: like the
    links met along a chain, `climbed_directories` records no provenance, so a partial rescan must walk every
    recorded link again to drop a climb no chain takes any more.

    Attributes:
        listings: Every directory the scan listed, sorted by path. A SYMLINK or OTHER entry appears in
            its parent's listing and nowhere else.
        files: The bytes of every FILE entry of every listing, and of every regular file a link the scan
            followed leads to, sorted by path. The second kind may sit in a directory the scan did not list.
        links: The target of every SYMLINK entry of every listing, and of a symlink met on the way to a
            scope root or along the chain of a recorded link, sorted by path. The scan walks every recorded
            link's chain for the record, also under a root that does not follow links. Empty when the snapshot was
            built by `from_files`.
        climbed_directories: Every directory a `..` climbed out of on the way to a scope root or along the chain
            of a recorded link, sorted. Such a `..` may climb out of a directory the scan stepped into by name and
            listed nothing in, as `tmp/../review` does; this is how a walk over the snapshot knows `tmp` is a
            directory. Empty when the snapshot was built by `from_files`.
        scope: The scan roots `take_snapshot` was given, in the order given and unmerged. Empty when nothing
            was scanned, as for a snapshot built by `from_files` or by hand, and then no path is in scope.
    """

    listings: tuple[Listing, ...]
    files: tuple[FileBytes, ...]
    links: tuple[Link, ...] = ()
    climbed_directories: tuple[RootRelativePath, ...] = ()
    # Defaults to empty, as `links` does: a snapshot built by hand scanned nothing, so it declares no scope.
    scope: tuple[ScanRoot, ...] = ()

    @classmethod
    def from_files(cls, files: Mapping[RootRelativePath, bytes]) -> Self:
        """Build a snapshot from file bytes alone, deriving every DIRECTORY entry and listing.

        Every directory on the way to a file is listed, the root `.` included. No path may sit under
        another path of the mapping. For tests and, later, the overlay; a scan uses the constructor because
        it also sees symlinks and other entries. Nothing was scanned, so the scope is empty and no path is in
        it, the listed directories included.

        Args:
            files: File bytes keyed by root-relative path; kept as given, and a directory is never a key.
        """
        listed: dict[RootRelativePath, set[DirEntry]] = {}
        for path in files:
            listed.setdefault(path.parent, set()).add(DirEntry(path.name, EntryKind.FILE))
            # path.parents runs from the file's own directory up to the root; the root has no parent listing.
            for directory in path.parents[:-1]:
                listed.setdefault(directory.parent, set()).add(DirEntry(directory.name, EntryKind.DIRECTORY))

        listings: list[Listing] = []
        for directory in sorted(listed):
            entries = sorted(listed[directory], key=lambda entry: entry.name)
            listings.append(Listing(directory, tuple(entries)))
        file_records: list[FileBytes] = []
        for path in sorted(files):
            file_records.append(FileBytes(path, files[path]))
        return cls(listings=tuple(listings), files=tuple(file_records), scope=())

    def entries(self) -> dict[RootRelativePath, EntryKind]:
        """Every path the snapshot recorded, with its kind; what a diff compares.

        That is every listed path (``listing.path / entry.name``), and what the scan recorded outside a
        listing of its parent:

        - A listed directory itself, as DIRECTORY. A scope root, or a directory a followed link leads to, has
          no listed parent to name it, so without this an empty one would come and go unseen. The root is
          left out: it always exists.
        - A file a followed link leads to, as FILE.
        - A symlink met on the way to a scope root, or along the chain of a recorded link, as SYMLINK.
        - A directory a `..` climbed out of on such a chain, as DIRECTORY, unless another record names it.
        """
        found: dict[RootRelativePath, EntryKind] = {}
        for directory in self.climbed_directories:
            found[directory] = EntryKind.DIRECTORY
        for listing in self.listings:
            if listing.path != ROOT:
                found[listing.path] = EntryKind.DIRECTORY
            for entry in listing.entries:
                found[listing.path / entry.name] = entry.kind
        for file in self.files:
            found[file.path] = EntryKind.FILE
        for link in self.links:
            found[link.path] = EntryKind.SYMLINK
        return found


class VirtualFileSystem(FileSystem):
    """A ``FileSystem`` answering from one snapshot; never reads the disk, never changes.

    Anything the snapshot did not record answers like a missing path on disk: an empty listing, a
    ``UnrecordedFileError``, or no directory. A path is walked through the recorded links by
    `find_real_path`, the walk the scan itself took, so the view reaches nothing through a link chain the
    scan did not follow.
    """

    def __init__(self, snapshot: Snapshot) -> None:
        """Index the snapshot's tuples into private dicts; performs no I/O.

        Args:
            snapshot: The recorded state every answer comes from; never changed, and never re-read from disk.
        """
        self._listings: dict[RootRelativePath, tuple[DirEntry, ...]] = {}
        for listing in snapshot.listings:
            self._listings[listing.path] = listing.entries
        self._files: dict[RootRelativePath, bytes] = {}
        for file in snapshot.files:
            self._files[file.path] = file.data
        # The walk's own index of kinds and link targets; the listings and bytes above are what the answers
        # return, and the walk never reads them.
        self._entries = _SnapshotEntries(snapshot)

    def list_dir(self, path: RootRelativePath) -> tuple[DirEntry, ...]:
        """The recorded listing of the directory `path` leads to; see `FileSystem.list_dir`.

        A recorded link on the way, or at it, is followed, as `find_real_dir` follows it, so a linked directory
        lists as the directory it leads to when the scan listed that one.

        Args:
            path: The root-relative directory to list; only what the snapshot recorded can answer.

        Returns:
            The entries in name order, or `()` for a missing, non-directory, unentered or out-of-scope
            path, and for a link the snapshot cannot follow to a listed directory.
        """
        directory = self.find_real_dir(path)
        if directory is None:
            return ()
        return self._listings.get(directory, ())

    def read_text(self, path: RootRelativePath) -> str:
        """Decode the recorded bytes of the file `path` leads to; see `FileSystem.read_text`.

        A recorded link on the way to the file, or at it, is followed, as `find_real_file` follows it. A link
        the scan did not follow to its file has no bytes here and reads as a missing file, as an OTHER entry
        does.

        Args:
            path: The root-relative file to read; it must be a file whose bytes the snapshot recorded.

        Raises:
            TextDecodeError: If the bytes are not UTF-8.
            UnrecordedFileError: If `path` leads to no regular file in the snapshot.
        """
        real_path = self.find_real_file(path)
        if real_path is None:
            raise UnrecordedFileError(path)
        return decode_text(path, self._files[real_path])

    def find_entry_kind(self, path: RootRelativePath) -> EntryKind | None:
        """What the recorded entry at `path` itself is; see `FileSystem.find_entry_kind`.

        A recorded link on the way to `path` is followed, as `find_real_dir` follows it; a recorded link at
        `path` is SYMLINK.

        Args:
            path: The root-relative entry to look up; the root itself is a DIRECTORY.

        Returns:
            The kind the parent's listing gives the entry, or, for an entry the snapshot recorded outside a
            listing of its parent, the kind its record gives it, in the order `_SnapshotEntries.kind` states.
            `None` for a path the snapshot recorded nothing at, and where the parent leads to no directory it
            knows of.
        """
        if path == ROOT:
            return EntryKind.DIRECTORY
        parent = self.find_real_dir(path.parent)
        if parent is None:
            return None
        return self._entries.find_kind(parent / path.name)

    def find_real_dir(self, path: RootRelativePath) -> RootRelativePath | None:
        """Follow the recorded links in `path` and return the real directory it leads to; see `FileSystem`.

        Args:
            path: The root-relative path to resolve; only links the snapshot recorded are followed.

        Returns:
            The real directory, root-relative, or `None` where the disk answers `None` (missing, a
            dangling or looping link, a file on the way or at the end) and also wherever the chain leaves
            what the snapshot recorded: above the root, an absolute target (one outside the root, since
            `take_snapshot` spells every target under it relative), or a directory outside the scope.
        """
        leads_to = self._find_real_path(path)
        match leads_to:
            case RealPath(path=directory, kind=EntryKind.DIRECTORY):
                return directory
            case RealPath() | RootExit() | None:
                return None
            case _:
                assert_never(leads_to)

    def find_real_file(self, path: RootRelativePath) -> RootRelativePath | None:
        """Follow the recorded links in `path` and return the recorded file it leads to; see `FileSystem`.

        Args:
            path: The root-relative path to resolve; only links the snapshot recorded are followed.

        Returns:
            The real file, root-relative, or `None` where `find_real_dir` lists, and also for a directory and
            for a file whose bytes the snapshot did not record, such as one a link the scan did not follow
            leads to.
        """
        leads_to = self._find_real_path(path)
        match leads_to:
            case RealPath(path=file, kind=EntryKind.FILE):
                if file not in self._files:
                    return None
                return file
            case RealPath() | RootExit() | None:
                return None
            case _:
                assert_never(leads_to)

    def find_root_exit(self, path: RootRelativePath) -> RootExit | None:
        """Where the recorded links in `path` lead out of the root; see `FileSystem.find_root_exit`.

        Args:
            path: The root-relative path to walk; only links the snapshot recorded are followed, and nothing
                outside the root is read, since the snapshot holds nothing there.
        """
        leads_to = self._find_real_path(path)
        match leads_to:
            case RootExit():
                return leads_to
            case RealPath() | None:
                return None
            case _:
                assert_never(leads_to)

    def _find_real_path(self, path: RootRelativePath) -> RealPath | RootExit | None:
        """Walk `path` through the recorded links to the real directory or file it leads to.

        The walk is `find_real_path`, the one the scan took over the disk, here over what the snapshot
        recorded (`_SnapshotEntries`): every component must be a directory the snapshot knows of or, as the
        last one, a file, a recorded link splices its target in, and a `..` climbs to the parent.

        Args:
            path: The root-relative path to walk, spelled as given; links in it are followed.

        Returns:
            The real path and its kind, where the chain leaves the root, or `None` when the snapshot holds
            nothing there; `find_real_dir` lists the cases.
        """
        return find_real_path(path, self._entries, follow_links=True)


class _SnapshotEntries:
    """What a walk of the virtual view sees: every entry a snapshot recorded, and nothing else.

    The `EntryLookup` the view hands to `find_real_path`. It differs from the scope query's recorded links
    in one way: a path the snapshot recorded nothing at is nothing, never assumed a directory, since the view
    answers what is there and not only where a path would lead.
    """

    def __init__(self, snapshot: Snapshot) -> None:
        """Index every entry the snapshot recorded by path, with its kind, and every link's target; no I/O.

        A walk asks for one entry at each component, so each answer is one lookup here rather than a scan of
        the parent's listing.

        Args:
            snapshot: The recorded state the walks see; read once, never changed.
        """
        self._targets: dict[RootRelativePath, PurePosixPath] = {}
        for link in snapshot.links:
            self._targets[link.path] = link.target

        # Filled from the weakest record to the strongest, each overwriting the one before, so a path recorded
        # twice keeps the kind `kind` documents. Only a self-inconsistent snapshot records a path twice with two
        # kinds; one taken by `take_snapshot` never does.
        self._kinds: dict[RootRelativePath, EntryKind] = {ROOT: EntryKind.DIRECTORY}
        # A listing sits at a real path, so it and every ancestor of it are directories, and so is a climbed
        # directory. A recorded file's ancestors are too, since it also sits at a real path, and so are a
        # recorded link's, since the scan meets a link only in a real directory.
        for listing in snapshot.listings:
            self._kinds[listing.path] = EntryKind.DIRECTORY
            for ancestor in listing.path.parents:
                self._kinds[ancestor] = EntryKind.DIRECTORY
        for directory in snapshot.climbed_directories:
            self._kinds[directory] = EntryKind.DIRECTORY
            for ancestor in directory.parents:
                self._kinds[ancestor] = EntryKind.DIRECTORY
        for file in snapshot.files:
            for ancestor in file.path.parents:
                self._kinds[ancestor] = EntryKind.DIRECTORY
        for link in snapshot.links:
            for ancestor in link.path.parents:
                self._kinds[ancestor] = EntryKind.DIRECTORY
        for file in snapshot.files:
            self._kinds[file.path] = EntryKind.FILE
        for link in snapshot.links:
            self._kinds[link.path] = EntryKind.SYMLINK
        for listing in snapshot.listings:
            for entry in listing.entries:
                self._kinds[listing.path / entry.name] = entry.kind

    def find_kind(self, path: RootRelativePath) -> EntryKind | None:
        """What the snapshot recorded at `path` itself; see `EntryLookup.find_kind`.

        Where more than one record names `path`, the first of these wins: the kind the parent's listing gives
        the entry; SYMLINK for a recorded link, such as one met on the way to a scope root; FILE for recorded
        bytes, such as a file a followed link leads to; DIRECTORY for a listed directory, such as a scope root,
        a climbed directory, or an ancestor of anything recorded. The listing comes first, where `Snapshot.entries`
        lets a link or a file override it; the two differ only on a snapshot that contradicts itself.

        Args:
            path: A root-relative entry the walk reached, every link on the way to it already followed.

        Returns:
            The recorded kind, or `None` where the snapshot recorded nothing, such as inside a directory the
            scan did not enter or outside the scope.
        """
        return self._kinds.get(path)

    def find_link_target(self, path: RootRelativePath) -> PurePosixPath | None:
        """The recorded target of the link at `path`; see `EntryLookup.find_link_target`.

        Args:
            path: The root-relative link, one `kind` answered SYMLINK for.

        Returns:
            The target as recorded, or `None` when no target was recorded at `path`.
        """
        return self._targets.get(path)

    def may_climb_out_of(self, directory: RootRelativePath) -> bool:
        """Always true: the walk stepped into `directory` only where the snapshot records one; see `EntryLookup`.

        Args:
            directory: The real directory the walk climbs out of.
        """
        return True
