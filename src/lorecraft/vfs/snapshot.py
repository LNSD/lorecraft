"""What one scan of the workspace saw, as a value, and the view that answers from it.

A ``Snapshot`` holds listings, file bytes and symlink targets, never a handle or a stat result, so two
snapshots compare and hash structurally. ``VirtualFileSystem`` answers the three ``FileSystem`` operations
from one snapshot without touching the disk. ``take_snapshot`` in ``disk.py`` is the producer that reads
the disk; ``Snapshot.of_files`` builds one by hand.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Final, Self

from .path import ROOT, RootRelativePath
from .view import DirEntry, EntryKind, FileSystem, ReadTextError, decode_text

MAX_LINKS: Final[int] = 40
"""Links followed before a chain counts as a loop; Linux's MAXSYMLINKS, past which the disk reports ELOOP.

The scan and the virtual view share it, so both give up on the same chain."""


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
            directory and may climb with ``..``, which only ``resolve_dir``'s walk interprets.
    """

    path: RootRelativePath
    target: PurePosixPath


@dataclass(frozen=True, slots=True)
class Snapshot:
    """What one scan saw: every listing, every FILE entry's bytes and every symlink's target. Never mutated.

    Tuples only, so two snapshots compare and hash structurally; equality is the "nothing changed" test.
    Bytes, not text: a non-UTF-8 file stays here so ``read_text`` raises ``DecodeTextError`` exactly as the
    disk view does; byte equality is the change test mtime is not. What a scan reads is the scope it is given.
    A link is always recorded, and followed only under a scan root that asks for it: where the scan did not
    follow one that leads outside the scope, what the disk view reads through it is not here.

    Every listing sits at a real path, with no symlink on the way to it. That is what lets the virtual view
    treat every ancestor of a listing or a link as a directory when it follows a chain.

    Reserved, not implemented: ``with_file(path, data) -> Snapshot``, a copy with one file's bytes
    replaced (and a FILE entry added to the parent listing when absent), for a server pushing unsaved
    buffers. It is a rebuild of ``files`` with one record replaced and of one ``Listing``; keep the
    representation such that it stays so.

    Attributes:
        listings: Every directory the scan listed, sorted by path. A SYMLINK or OTHER entry appears in
            its parent's listing and nowhere else.
        files: The bytes of every FILE entry of every listing, sorted by path.
        links: The target of every SYMLINK entry of every listing, and of a symlink met on the way to a
            scope root or along a chain the scan followed, sorted by path. Empty when the snapshot was
            built by ``of_files``.
    """

    listings: tuple[Listing, ...]
    files: tuple[FileBytes, ...]
    links: tuple[Link, ...] = ()

    @classmethod
    def of_files(cls, files: Mapping[RootRelativePath, bytes]) -> Self:
        """Build a snapshot from file bytes alone, deriving every DIRECTORY entry and listing.

        Every directory on the way to a file is listed, the root ``.`` included. No path may sit under
        another path of the mapping. For tests and, later, the overlay; a scan uses the constructor because
        it also sees symlinks and other entries.
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
        return cls(listings=tuple(listings), files=tuple(file_records))

    def entries(self) -> dict[RootRelativePath, EntryKind]:
        """Every listed path (``listing.path / entry.name``) with its kind; what a diff compares.

        A symlink met on the way to a scope root, or along a chain the scan followed, may sit in no listing
        and is included as SYMLINK.
        """
        found: dict[RootRelativePath, EntryKind] = {}
        for listing in self.listings:
            for entry in listing.entries:
                found[listing.path / entry.name] = entry.kind
        for link in self.links:
            found[link.path] = EntryKind.SYMLINK
        return found


class VirtualFileSystem(FileSystem):
    """A ``FileSystem`` answering from one snapshot; never reads the disk, never changes.

    Anything the snapshot did not record answers like a missing path on disk: an empty listing, a
    ``ReadTextError``, or no directory.
    """

    def __init__(self, snapshot: Snapshot) -> None:
        """Index the snapshot's tuples into private dicts; performs no I/O."""
        self._listings: dict[RootRelativePath, tuple[DirEntry, ...]] = {}
        for listing in snapshot.listings:
            self._listings[listing.path] = listing.entries
        self._files: dict[RootRelativePath, bytes] = {}
        for file in snapshot.files:
            self._files[file.path] = file.data
        self._links: dict[RootRelativePath, PurePosixPath] = {}
        for link in snapshot.links:
            self._links[link.path] = link.target

        # A listing sits at a real path, so it and every ancestor of it are directories; a recorded link's
        # ancestors are too, since the scan meets a link only in a real directory.
        self._directories: set[RootRelativePath] = {ROOT}
        for path in self._listings:
            self._directories.add(path)
            self._directories.update(path.parents)
        for path in self._links:
            self._directories.update(path.parents)

    def list_dir(self, path: RootRelativePath) -> tuple[DirEntry, ...]:
        """The recorded listing of the directory ``path`` leads to; see ``FileSystem.list_dir``.

        A recorded link on the way is followed, as ``resolve_dir`` follows it, so a linked directory lists
        as the directory it leads to when the scan listed that one.

        Returns:
            The entries in name order, or ``()`` for a missing, non-directory, unentered or out-of-scope
            path, and for a link the snapshot cannot follow to a listed directory.

        Raises:
            ListDirError: Never; kept in the contract for the disk implementation.
        """
        directory = self.resolve_dir(path)
        if directory is None:
            return ()
        return self._listings.get(directory, ())

    def read_text(self, path: RootRelativePath) -> str:
        """Decode the recorded bytes of the file ``path`` names; see ``FileSystem.read_text``.

        A recorded link on the way to the file's directory is followed, as ``resolve_dir`` follows it. The
        file itself must be a regular one: a SYMLINK or OTHER entry has no bytes and is a missing file here.

        Raises:
            DecodeTextError: If the bytes are not UTF-8.
            ReadTextError: If no regular file at ``path`` is in the snapshot.
        """
        directory = self.resolve_dir(path.parent)
        if directory is None:
            raise ReadTextError(path, 'not in the snapshot')
        data = self._files.get(directory / path.name)
        if data is None:
            raise ReadTextError(path, 'not in the snapshot')
        return decode_text(path, data)

    def resolve_dir(self, path: RootRelativePath) -> RootRelativePath | None:
        """Follow the recorded links in ``path`` and return the real directory it leads to; see ``FileSystem``.

        The walk goes one component at a time from the root, as the kernel does: a recorded link splices
        its target into the components still to walk, ``..`` steps up from the real directory reached so
        far, and any other component must be a directory the snapshot knows of.

        Returns:
            The real directory, root-relative, or ``None`` where the disk answers ``None`` (missing, a
            dangling or looping link, a file on the way) and also wherever the chain leaves what the
            snapshot recorded: above the root, an absolute target (one outside the root, since
            ``take_snapshot`` spells every target under it relative), or a directory outside the scope.

        Raises:
            ResolveDirError: Never; kept in the contract for the disk implementation.
        """
        # ``path`` holds no ``..`` (its type guarantees it), but a spliced link target may, so the walk
        # still handles one; ``resolved`` never climbs above the root, as its type requires.
        resolved = ROOT
        remaining = list(path.parts)
        links_followed = 0
        while remaining:
            part = remaining.pop(0)
            if part == '..':
                if resolved == ROOT:
                    return None  # above the root: nothing the snapshot recorded
                resolved = resolved.parent
                continue
            candidate = resolved / part
            target = self._links.get(candidate)
            if target is not None:
                links_followed += 1
                if links_followed > MAX_LINKS or target.is_absolute():
                    return None
                remaining = list(target.parts) + remaining
                continue
            if not self._is_directory(candidate):
                return None
            resolved = candidate
        return resolved

    def _is_directory(self, path: RootRelativePath) -> bool:
        """True when the snapshot knows ``path`` is a real directory.

        Known means listed, an ancestor of something recorded, or a DIRECTORY entry of a listed parent (a
        directory the scan did not enter).
        """
        if path in self._directories:
            return True
        parent_entries = self._listings.get(path.parent)
        if parent_entries is None:
            return False  # outside what the scan listed
        return DirEntry(path.name, EntryKind.DIRECTORY) in parent_entries
