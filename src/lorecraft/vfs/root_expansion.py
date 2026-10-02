"""How a path walks through symlinks, defined once for the scan, the scope query and the virtual view.

`take_snapshot` in `disk.py` expands each root of a scope as it lists the disk; `ScopeIndex` in `scope.py`
expands the same roots afterwards, from the links the snapshot recorded; `VirtualFileSystem` in `snapshot.py`
resolves a path through the same links. All three go through the rules here, so what the scan lists, what the
query says it lists and what the view reaches cannot drift apart:

- `find_canonical_scan_root`: where the scan of a root starts, walked through the links on the way when it follows them.
- `find_canonical_path`: where a path leads, which links are followed, and where a chain leaves the root.
- `find_linked_scan_root`: the root a followed link adds, and the depth the link uses up, none when the root has no
  limit.

The callers differ only in where a walk learns what an entry is, which is what `EntryLookup` stands for: the
disk, read as the walk goes, the links and climbed directories a snapshot recorded, or everything a snapshot
recorded.
"""

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Final, Protocol, assert_never

from lorecraft.core.path import ROOT, RootRelativePath

from .scan_root import ScanRoot
from .view import EntryKind, RootExit

MAX_LINKS: Final[int] = 40
"""Links followed before a chain counts as a loop; Linux's MAXSYMLINKS, past which the disk reports ELOOP.

Every walk here counts against it, so the scan, the scope query and the virtual view give up on the same chain."""


class EntryLookup(Protocol):
    """Where a walk learns what an entry is and where a link leads.

    A protocol rather than the links themselves, because the scan learns both from the disk as it walks,
    inspecting each component and recording each link it reads, the scope query has only the links a snapshot
    recorded, and the virtual view has the snapshot's listings and files besides.
    """

    def find_kind(self, path: RootRelativePath) -> EntryKind | None:
        """What the entry at `path` itself is, a final symlink not followed; `None` when nothing is there.

        Args:
            path: A root-relative entry the walk reached, every link on the way to it already followed.
        """
        ...

    def find_link_target(self, path: RootRelativePath) -> PurePosixPath | None:
        """Read the target of the symlink at `path`; `None` when it is gone.

        The disk implementation records each target it reads in the links of the scan, so reading is not free
        of effect; the snapshot implementations only look it up.

        Args:
            path: A root-relative entry `kind` answered SYMLINK for.
        """
        ...

    def may_climb_out_of(self, directory: RootRelativePath) -> bool:
        """Whether a `..` may climb from `directory` to its parent, because a directory is there.

        Not free of effect, as `find_link_target` is not: the scan's implementation records `directory` among the
        directories it climbed out of, as it records each link target it reads, so the snapshot knows it even
        where the scan lists nothing in it. The disk and the snapshot view answer true: the walk stepped into
        `directory` only where they found a directory. Only the scope query can answer false: it takes a component
        it knows nothing of for a directory, and `..` makes that guess matter (see `ScopeIndex`).

        Args:
            directory: The directory the walk is in, not the root; reached by stepping into it or as the
                directory of a link it followed.
        """
        ...


@dataclass(frozen=True, slots=True)
class CanonicalDirectory:
    """A walk from the root that ended at a directory, the root itself included.

    A canonical path is the one a name leads to once every symlink is followed, as an IDE's virtual file system
    names it.

    Attributes:
        path: The directory's canonical path, root-relative: with no symlink on the way to it or at it.
    """

    path: RootRelativePath


@dataclass(frozen=True, slots=True)
class CanonicalFile:
    """A walk from the root that ended at a regular file, as the path's last component.

    Attributes:
        path: The file's canonical path, root-relative: with no symlink on the way to it or at it.
    """

    path: RootRelativePath


def find_canonical_path(
    path: RootRelativePath, entries: EntryLookup, *, follow_links: bool
) -> CanonicalDirectory | CanonicalFile | RootExit | None:
    """The canonical directory or regular file `path` leads to, where it leaves the root, or `None` where it stops.

    Walks the components from the root, one canonical directory to the next, so every step leaves the walk at a
    canonical, root-relative path, as the kernel resolves one. A `..` takes it to the parent of the canonical
    directory it is in. Without `follow_links` the walk ends at the first symlink, which leaves the path unread. With
    it a symlink splices its target into the components still to walk, and the walk goes on from the link's directory.
    Whether the walk goes on is decided from that canonical path alone: anywhere under the root it does, and a `..`
    above the root leaves it, whatever directories the chain stepped into on the way.

    Args:
        path: The root-relative path to walk, spelled as given, links unresolved.
        entries: What each component is, and where each link leads; whatever it raises propagates unchanged.
        follow_links: Whether a symlink is spliced in and followed; when false the walk ends at the first one.

    Returns:
        A `CanonicalDirectory` or `CanonicalFile` where the walk ends; a `RootExit` when a followed link's target
        is absolute or a `..` climbs above the root; or `None` where the walk stops under the root, each for the
        reason given:

        - A component is missing, or is neither a directory, a regular file nor a symlink: nothing is there to
          step into or end at.
        - A regular file is not the last component: a file is no directory to step into.
        - A symlink is not followed, or is gone since its kind was read: nothing is read through it.
        - The chain follows more than `MAX_LINKS` links: it counts as a loop, as the disk reports one.
        - `entries` will not let a `..` climb out of a directory it does not know to exist; only the scope
          query refuses one (see `EntryLookup.may_climb_out_of`).

    Raises:
        Exception: Whatever `entries` raises: the disk lookup's `SnapshotEntryInspectError` and
            `SnapshotLinkReadError`; the snapshot lookups raise nothing.
    """
    resolved = ROOT
    remaining = list(path.parts)
    links_followed = 0
    last_link: RootExit | None = None  # the link followed last, as the exit it would be
    while remaining:
        part = remaining.pop(0)
        if part == '..':
            if resolved == ROOT:
                if last_link is None:
                    raise AssertionError('a root-relative path holds no `..`, so this one came from a link target')
                return last_link
            # Records the climb in the scan; only the scope query ever answers no, for a directory it only guessed.
            if not entries.may_climb_out_of(resolved):
                return None
            resolved = resolved.parent
            continue
        candidate = resolved / part
        kind = entries.find_kind(candidate)
        match kind:
            case EntryKind.DIRECTORY:
                resolved = candidate
            case EntryKind.FILE:
                if remaining:
                    return None  # a file is no directory to step into
                return CanonicalFile(candidate)
            case EntryKind.OTHER | None:
                return None  # nothing is there, or nothing the scan reads
            case EntryKind.SYMLINK:
                target = entries.find_link_target(candidate)
                if target is None:
                    return None  # gone since `kind` answered, so nothing is there to follow
                links_followed += 1
                if not follow_links or links_followed > MAX_LINKS:
                    return None
                last_link = RootExit(candidate, target)
                if target.is_absolute():
                    return last_link
                remaining = list(target.parts) + remaining
            case _:
                assert_never(kind)
    return CanonicalDirectory(resolved)


def find_canonical_scan_root(scan_root: ScanRoot, entries: EntryLookup) -> ScanRoot | None:
    """The root the scan of `scan_root` lists from: its directory at the canonical path it leads to.

    A root that follows links is walked through every link on the way to its directory; one that does not
    ends at the first link and lists nothing. A snapshot has no record for a lone file, so a root that is one
    lists nothing either: it is seen only through a listing of its parent, and a scope that must answer whether
    a root exists lists that parent too.

    Args:
        scan_root: One root of the scope, as declared.
        entries: What each component on the way is, and where each link leads.

    Returns:
        The root at its canonical directory, with the declared depth and link policy, or `None` when the walk
        leads to no directory or leaves the root (see `find_canonical_path`).

    Raises:
        Exception: Whatever `entries` raises: the disk lookup's `SnapshotEntryInspectError` and
            `SnapshotLinkReadError`; the snapshot lookups raise nothing.
    """
    leads_to = find_canonical_path(scan_root.directory, entries, follow_links=scan_root.follow_links)
    match leads_to:
        case CanonicalDirectory(path=directory):
            return ScanRoot(directory, scan_root.depth, follow_links=scan_root.follow_links)
        case CanonicalFile() | RootExit() | None:
            return None
        case _:
            assert_never(leads_to)


def find_linked_scan_root(scan_root: ScanRoot, link: RootRelativePath, directory: RootRelativePath) -> ScanRoot | None:
    """The root the scan of `scan_root` adds by following `link` to the canonical `directory` it leads to.

    A link is followed only where a root that follows links lists it. It uses up one level of depth, as a
    DIRECTORY entry does: the linked directory is listed with one level less than the directory holding the
    link was, and with no limit when `scan_root` has none. A link in a directory listed with no depth left
    adds no root; the scan reads a linked file there, but lists no linked directory.

    Args:
        scan_root: A root the scan lists from, at its canonical directory.
        link: The root-relative symlink, wherever it sits.
        directory: The canonical directory the link leads to, by `find_canonical_path` with links followed.

    Returns:
        A root at `directory` that follows links, or `None` when `scan_root` does not follow links, does not
        list `link`, or lists it with no depth left.
    """
    if not scan_root.follow_links or not scan_root.is_covering(link):
        return None
    # The directory holding the link is `listing_level` levels down, and entering the link costs one more.
    return scan_root.find_root_below(directory, levels=scan_root.listing_level(link) + 1)
