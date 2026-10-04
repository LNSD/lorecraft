"""What one scan of the workspace saw, as a value, and the view that answers from it.

A `Snapshot` holds the scope it was taken of and one record for each path it saw: a directory, a file's bytes, a
symlink's target, or another entry, never a handle or a stat result, so two snapshots compare and hash structurally.
`VirtualFileSystem` answers every `FileSystem` operation from one snapshot without touching the disk. `take_snapshot`
in `disk.py` is the producer that reads the disk; `Snapshot.from_tree` builds one by hand.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Self, assert_never

from lorecraft.core.mapping import FrozenMapping
from lorecraft.core.path import ROOT, PathComponent, RootRelativePath

from .root_expansion import ResolvedDirectory, ResolvedFile, find_destination
from .scan_root import ScanRoot
from .view import DirEntry, EntryKind, FileSystem, ResolvedPath, RootExit, UnrecordedFileError, decode_text

type FileTree = Mapping[str, bytes | FileTree]
"""A directory's contents as `Snapshot.from_tree` takes them: each key one entry's name, mapped to a file's bytes
or to the directory's own contents."""


# kw_only so a call names each flag: `DirectoryRecord(listed=True)` rather than a bare `True`.
@dataclass(frozen=True, slots=True, kw_only=True)
class DirectoryRecord:
    """A directory the scan recorded: one it listed, one a `..` climbed out of, or an entry it did not enter.

    Every combination of the two flags occurs. Neither is set for a directory entry of a listing that the scan did
    not enter, because no depth was left there.

    Attributes:
        listed: Whether the scan listed the directory; its entries are then the records whose parent it is.
        climbed: Whether a `..` climbed out of the directory on the way to a scope root or along the chain of a
            recorded link. Such a `..` may climb out of a directory the scan stepped into by name and listed
            nothing in, as `tmp/../review` does; this is how a walk over the snapshot knows `tmp` is a directory.
    """

    listed: bool = False
    climbed: bool = False

    @property
    def kind(self) -> EntryKind:
        """DIRECTORY, the kind a listing of the parent gives the entry."""
        return EntryKind.DIRECTORY


@dataclass(frozen=True, slots=True)
class FileRecord:
    """One regular file the scan read: an entry of a listing, or a file a followed link leads to.

    Attributes:
        data: Its whole content, undecoded.
    """

    data: bytes

    @property
    def kind(self) -> EntryKind:
        """FILE, the kind a listing of the parent gives the entry."""
        return EntryKind.FILE


@dataclass(frozen=True, slots=True)
class SymlinkRecord:
    """One symlink and the target it names, as `os.readlink` returned it, save one rewrite.

    `take_snapshot` rewrites an absolute target that names a path under the root relative to the link's
    own directory, so the virtual view can follow it the way the disk view does; a snapshot never records
    where the root sits.

    Attributes:
        target: The target, unresolved: relative to the link's own directory, or absolute and outside the
            root. A plain `PurePosixPath`, not a `RootRelativePath`: it is spelled from the link's
            directory and may climb with `..`, which only a walk through the link interprets.
    """

    target: PurePosixPath

    @property
    def kind(self) -> EntryKind:
        """SYMLINK, the kind a listing of the parent gives the entry, whatever it leads to."""
        return EntryKind.SYMLINK


@dataclass(frozen=True, slots=True)
class OtherRecord:
    """One entry of a listing that is no directory, regular file or symlink, such as a fifo; recorded, never read."""

    @property
    def kind(self) -> EntryKind:
        """OTHER, the kind a listing of the parent gives the entry."""
        return EntryKind.OTHER


type EntryRecord = DirectoryRecord | FileRecord | SymlinkRecord | OtherRecord
"""What a snapshot recorded at one path: one record per path, so a path never has two kinds."""


@dataclass(frozen=True, slots=True)
class Snapshot:
    """What one scan saw: its scope, and one record for every path it recorded. Never mutated.

    A frozen mapping and a tuple, so two snapshots compare and hash structurally, whatever order the records were
    taken in; equality is the "nothing changed" test, the scope included. Bytes, not text: a non-UTF-8 file stays
    here so `read_text` raises `TextDecodeError` exactly as the disk view does; byte equality is the change test
    mtime is not. What a scan reads is the scope it is given, and the snapshot records that scope, so whether a path
    is in scope is answered from the snapshot alone. A link is always recorded, and followed only under a scan root
    that asks for it: where the scan did not follow one that leads outside the scope, what the disk view reads
    through it is not here.

    No listing is stored. The entries of a directory the scan listed are the records whose parent it is, in name
    order, the root never an entry of its own listing; a scan records every entry of each directory it lists.

    Every record sits at a resolved path, with no symlink on the way to it. So when the virtual view follows a chain,
    it treats as a directory every directory record and every ancestor of a record, whether recorded or not.

    Reserved, not implemented: `with_file(path, data) -> Snapshot`, a copy with one file's record replaced or added,
    for a server pushing unsaved buffers. It is a rebuild of `records` with one record replaced, the parent's
    listing following from it; keep the representation such that it stays so. A partial rescan, by contrast, cannot
    drop one record alone: like the links met along a chain, a climbed directory records no provenance, so a partial
    rescan must walk every recorded link again to drop a climb no chain takes any more.

    Attributes:
        records: One record for each path the scan recorded, keyed by path: every directory it listed and every
            entry of each, every regular file a followed link leads to, every symlink met on the way to a scope root
            or along the chain of a recorded link, and every directory a `..` climbed out of on such a way. A file a
            followed link leads to may sit in a directory the scan did not list. The scan walks every recorded link's
            chain for the record, also under a root that does not follow links. The root is recorded only when
            listed. A snapshot built by `from_tree` records listed directories and files alone.
        scope: The scan roots `take_snapshot` was given, in the order given and unmerged. Empty when nothing
            was scanned, as for a snapshot built by `from_tree` or by hand, and then no path is in scope.
    """

    records: FrozenMapping[RootRelativePath, EntryRecord]
    # Defaults to empty: a snapshot built by hand scanned nothing, so it declares no scope.
    scope: tuple[ScanRoot, ...] = ()

    @classmethod
    def from_tree(cls, tree: FileTree) -> Self:
        """Build a snapshot from a tree of directories and file bytes, every directory in it listed.

        Every mapping in the tree is a listed directory, the root `.` included, so `from_tree({})` lists the
        root with no entries and an empty mapping under a name is an empty directory. For tests and, later, the
        overlay; a scan records through `take_snapshot` because it also sees symlinks and other entries. Nothing
        was scanned, so the scope is empty and no path is in it, the listed directories included.

        Args:
            tree: The root's contents: each key is one entry's name, mapped to its bytes for a file or to the
                directory's own contents for a directory. Bytes are kept as given.

        Raises:
            PathComponentError: If a key is empty, is `.` or `..`, or holds a `/`.
        """
        records: dict[RootRelativePath, EntryRecord] = {ROOT: DirectoryRecord(listed=True)}
        _record_tree(ROOT, tree, records)
        return cls(FrozenMapping(records), scope=())

    def symlink_targets(self) -> dict[RootRelativePath, PurePosixPath]:
        """Every recorded symlink's target, keyed by the link's path in path order; what the scope query follows."""
        targets: dict[RootRelativePath, PurePosixPath] = {}
        for path, record in self.records.items():
            match record:
                case SymlinkRecord(target=target):
                    targets[path] = target
                case DirectoryRecord() | FileRecord() | OtherRecord():
                    pass
                case _:
                    assert_never(record)
        return dict(sorted(targets.items()))

    def climbed_directories(self) -> tuple[RootRelativePath, ...]:
        """Every directory a `..` climbed out of, in path order; what the scope query lets a `..` climb out of."""
        climbed: list[RootRelativePath] = []
        for path, record in self.records.items():
            match record:
                case DirectoryRecord(climbed=True):
                    climbed.append(path)
                case DirectoryRecord() | FileRecord() | SymlinkRecord() | OtherRecord():
                    pass
                case _:
                    assert_never(record)
        return tuple(sorted(climbed))


def _record_tree(directory: RootRelativePath, tree: FileTree, records: dict[RootRelativePath, EntryRecord]) -> None:
    """Record every entry of `directory` and everything below it, for `Snapshot.from_tree`.

    Args:
        directory: The root-relative directory `tree` holds the contents of, already recorded as listed.
        tree: The directory's contents, each key one entry's name.
        records: The records taken so far, keyed by path; one is added for each entry in or below `directory`.

    Raises:
        PathComponentError: If a key is empty, is `.` or `..`, or holds a `/`.
    """
    for raw_name, node in tree.items():
        path = directory / PathComponent.parse(raw_name)
        match node:
            case bytes():
                records[path] = FileRecord(node)
            case Mapping():
                records[path] = DirectoryRecord(listed=True)
                _record_tree(path, node, records)
            case _:
                assert_never(node)


class VirtualFileSystem(FileSystem):
    """A ``FileSystem`` answering from one snapshot; never reads the disk, never changes.

    Anything the snapshot did not record answers like a missing path on disk: an empty listing, a
    ``UnrecordedFileError``, or no directory. A path is walked through the recorded links by
    `find_destination`, the walk the scan itself took, so the view reaches nothing through a link chain the
    scan did not follow.
    """

    def __init__(self, snapshot: Snapshot) -> None:
        """Index the snapshot's records into private dicts, deriving every listing; performs no I/O.

        Args:
            snapshot: The recorded state every answer comes from; never changed, and never re-read from disk.
        """
        self._listings = _derive_listings(snapshot.records)
        self._files: dict[RootRelativePath, bytes] = {}
        for path, record in snapshot.records.items():
            match record:
                case FileRecord(data=data):
                    self._files[path] = data
                case DirectoryRecord() | SymlinkRecord() | OtherRecord():
                    pass  # no bytes to read
                case _:
                    assert_never(record)
        # The walk's own index of kinds and link targets; the listings and bytes above are what the answers
        # return, and the walk never reads them.
        self._entries = _SnapshotEntries(snapshot)

    def list_dir(self, path: RootRelativePath) -> tuple[DirEntry, ...]:
        """The recorded listing of the directory `path` leads to; see `FileSystem.list_dir`.

        A recorded link on the way, or at it, is followed, as `find_dir` follows it, so a linked directory
        lists as the directory it leads to when the scan listed that one.

        Args:
            path: The root-relative directory to list; only what the snapshot recorded can answer.

        Returns:
            The entries in name order, or `()` for a missing, non-directory, unentered or out-of-scope
            path, and for a link the snapshot cannot follow to a listed directory.
        """
        directory = self.find_dir(path)
        if directory is None:
            return ()
        return self._listings.get(directory, ())

    def read_text(self, path: RootRelativePath) -> str:
        """Decode the recorded bytes of the file `path` leads to; see `FileSystem.read_text`.

        A recorded link on the way to the file, or at it, is followed, as `find_file` follows it. A link
        the scan did not follow to its file has no bytes here and reads as a missing file, as an OTHER entry
        does.

        Args:
            path: The root-relative file to read; it must be a file whose bytes the snapshot recorded.

        Raises:
            TextDecodeError: If the bytes are not UTF-8.
            UnrecordedFileError: If `path` leads to no regular file in the snapshot.
        """
        resolved_path = self.find_file(path)
        if resolved_path is None:
            raise UnrecordedFileError(path)
        return decode_text(path, self._files[resolved_path])

    def find_entry_kind(self, path: RootRelativePath) -> EntryKind | None:
        """What the recorded entry at `path` itself is; see `FileSystem.find_entry_kind`.

        A recorded link on the way to `path` is followed, as `find_dir` follows it; a recorded link at
        `path` is SYMLINK.

        Args:
            path: The root-relative entry to look up; the root itself is a DIRECTORY.

        Returns:
            The kind the entry's record gives it, or DIRECTORY for an ancestor of a record that no record names.
            `None` for a path the snapshot recorded nothing at, and where the parent leads to no directory it
            knows of.
        """
        if path == ROOT:
            return EntryKind.DIRECTORY
        parent = self.find_dir(path.parent)
        if parent is None:
            return None
        return self._entries.find_kind(parent / path.name)

    def find_dir(self, path: RootRelativePath) -> ResolvedPath | None:
        """Follow the recorded links in `path` and return the resolved directory it leads to; see `FileSystem`.

        Args:
            path: The root-relative path to resolve; only links the snapshot recorded are followed.

        Returns:
            The resolved directory, root-relative, or `None` where the disk answers `None` (missing, a
            dangling or looping link, a file on the way or at the end) and also wherever the chain leaves
            what the snapshot recorded: above the root, an absolute target (one outside the root, since
            `take_snapshot` spells every target under it relative), or a directory outside the scope.
        """
        leads_to = self._find_destination(path)
        match leads_to:
            case ResolvedDirectory(path=directory):
                # Resolved: the walk ends at a path it reached through no symlink.
                return ResolvedPath(directory)
            case ResolvedFile() | RootExit() | None:
                return None
            case _:
                assert_never(leads_to)

    def find_file(self, path: RootRelativePath) -> ResolvedPath | None:
        """Follow the recorded links in `path` and return the recorded file it leads to; see `FileSystem`.

        Args:
            path: The root-relative path to resolve; only links the snapshot recorded are followed.

        Returns:
            The resolved file, root-relative, or `None` where `find_dir` lists, and also for a directory. A file
            the scan did not read, such as one a link the scan did not follow leads to, has no record, so the walk
            finds nothing there.
        """
        leads_to = self._find_destination(path)
        match leads_to:
            case ResolvedFile(path=file):
                # Resolved: the walk ends at a path it reached through no symlink.
                return ResolvedPath(file)
            case ResolvedDirectory() | RootExit() | None:
                return None
            case _:
                assert_never(leads_to)

    def find_root_exit(self, path: RootRelativePath) -> RootExit | None:
        """Where the recorded links in `path` lead out of the root; see `FileSystem.find_root_exit`.

        Args:
            path: The root-relative path to walk; only links the snapshot recorded are followed, and nothing
                outside the root is read, since the snapshot holds nothing there.
        """
        leads_to = self._find_destination(path)
        match leads_to:
            case RootExit():
                return leads_to
            case ResolvedDirectory() | ResolvedFile() | None:
                return None
            case _:
                assert_never(leads_to)

    def _find_destination(self, path: RootRelativePath) -> ResolvedDirectory | ResolvedFile | RootExit | None:
        """Walk `path` through the recorded links to the resolved directory or file it leads to.

        The walk is `find_destination`, the one the scan took over the disk, here over what the snapshot
        recorded (`_SnapshotEntries`): every component must be a directory the snapshot knows of or, as the
        last one, a file, a recorded link splices its target in, and a `..` climbs to the parent.

        Args:
            path: The root-relative path to walk, spelled as given; links in it are followed.

        Returns:
            The resolved directory or file, where the chain leaves the root, or `None` when the snapshot holds
            nothing there; `find_dir` lists the cases.
        """
        return find_destination(path, self._entries, follow_links=True)


def _derive_listings(records: Mapping[RootRelativePath, EntryRecord]) -> dict[RootRelativePath, tuple[DirEntry, ...]]:
    """Every listed directory's entries: the records whose parent it is, by name.

    Args:
        records: Every record of one snapshot, keyed by path.

    Returns:
        The entries of each directory recorded as listed, keyed by its path, each in name order.
    """
    found: dict[RootRelativePath, list[DirEntry]] = {}
    for path, record in records.items():
        match record:
            case DirectoryRecord(listed=True):
                found[path] = []
            case DirectoryRecord() | FileRecord() | SymlinkRecord() | OtherRecord():
                pass  # nothing listed there
            case _:
                assert_never(record)
    for path, record in records.items():
        if path == ROOT:
            continue  # the root is its own parent, and never an entry of its own listing
        siblings = found.get(path.parent)
        if siblings is not None:
            # A record's path below the root ends in one valid component, so parsing its name never raises.
            siblings.append(DirEntry(PathComponent.parse(path.name), record.kind))
    listings: dict[RootRelativePath, tuple[DirEntry, ...]] = {}
    for directory, entries in found.items():
        entries.sort(key=lambda entry: entry.name)
        listings[directory] = tuple(entries)
    return listings


class _SnapshotEntries:
    """What a walk of the virtual view sees: every entry a snapshot recorded, and nothing else.

    The `EntryLookup` the view hands to `find_destination`. It differs from the scope query's recorded links
    in one way: a path the snapshot recorded nothing at is nothing, never assumed a directory, since the view
    answers what is there and not only where a path would lead.
    """

    def __init__(self, snapshot: Snapshot) -> None:
        """Index every entry the snapshot recorded by path, with its kind, and every link's target; no I/O.

        A walk asks for one entry at each component, so each answer is one lookup here rather than a search of
        the records.

        Args:
            snapshot: The recorded state the walks see; read once, never changed.
        """
        self._targets = snapshot.symlink_targets()
        self._kinds: dict[RootRelativePath, EntryKind] = {}
        for path, record in snapshot.records.items():
            self._kinds[path] = record.kind
        # Every record sits at a resolved path, so each ancestor of one is a directory, recorded or not, and so is
        # the root.
        for path in snapshot.records:
            for ancestor in path.parents:
                self._kinds.setdefault(ancestor, EntryKind.DIRECTORY)
        self._kinds.setdefault(ROOT, EntryKind.DIRECTORY)

    def find_kind(self, path: RootRelativePath) -> EntryKind | None:
        """What the snapshot recorded at `path` itself; see `EntryLookup.find_kind`.

        Args:
            path: A root-relative entry the walk reached, every link on the way to it already followed.

        Returns:
            The kind the record at `path` gives it; DIRECTORY for the root and for an ancestor of a record that no
            record names, such as the directory holding a symlink met on the way to a scope root; or `None` where
            the snapshot recorded nothing, such as inside a directory the scan did not enter or outside the scope.
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
            directory: The resolved directory the walk climbs out of.
        """
        return True
