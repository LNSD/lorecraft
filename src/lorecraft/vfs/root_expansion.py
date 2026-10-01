"""How a path walks through symlinks, defined once for the scan, the scope query and the virtual view.

`take_snapshot` in `disk.py` expands each root of a scope as it lists the disk; `ScopeIndex` in `scope.py`
expands the same roots afterwards, from the links the snapshot recorded; `VirtualFileSystem` in `snapshot.py`
resolves a path through the same links. All three go through the rules here, so what the scan lists, what the
query says it lists and what the view reaches cannot drift apart:

- `real_scan_root`: where the scan of a root starts, walked through the links on the way when it follows them.
- `walk_to_real_path`: where a path leads, which links are followed, and which `..` steps are refused.
- `linked_scan_root`: the root a followed link adds, and the depth the link uses up.

The callers differ only in where a walk learns what an entry is, which is what `EntryLookup` stands for: the
disk, read as the walk goes, the links a snapshot recorded, or everything a snapshot recorded.
"""

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Final, Protocol, assert_never

from lorecraft.core.path import ROOT, RootRelativePath

from .scan_root import ScanRoot
from .view import EntryKind

MAX_LINKS: Final[int] = 40
"""Links followed before a chain counts as a loop; Linux's MAXSYMLINKS, past which the disk reports ELOOP.

Every walk here counts against it, so the scan, the scope query and the virtual view give up on the same chain."""


class EntryLookup(Protocol):
    """Where a walk learns what an entry is and where a link leads.

    A protocol rather than the links themselves, because the scan learns both from the disk as it walks,
    inspecting each component and recording each link it reads, the scope query has only the links a snapshot
    recorded, and the virtual view has the snapshot's listings and files besides.
    """

    def kind(self, path: RootRelativePath) -> EntryKind | None:
        """What the entry at `path` itself is, a final symlink not followed; `None` when nothing is there.

        Args:
            path: A root-relative entry the walk reached, every link on the way to it already followed.
        """
        ...

    def read_link_target(self, path: RootRelativePath) -> PurePosixPath | None:
        """Read the target of the symlink at `path`; `None` when it is gone.

        The disk implementation records each target it reads in the links of the scan, so reading is not free
        of effect; the snapshot implementations only look it up.

        Args:
            path: A root-relative entry `kind` answered SYMLINK for.
        """
        ...


@dataclass(frozen=True, slots=True)
class RealPath:
    """Where a walk from the root ended.

    Attributes:
        path: The real path, root-relative, with no symlink on the way to it or at it.
        kind: DIRECTORY or FILE; a walk ends nowhere else.
    """

    path: RootRelativePath
    kind: EntryKind


def walk_to_real_path(path: RootRelativePath, entries: EntryLookup, *, follow_links: bool) -> RealPath | None:
    """The real directory or regular file `path` leads to, or `None` where the scan does not go.

    Walks the components from the root, one real directory to the next. Without `follow_links` the walk ends
    at the first symlink, which leaves the path unread. With it a symlink splices its target into the
    components still to walk, as the kernel does.

    The `..` refusal below is the walk's own, and the kernel has no such rule. A snapshot knows a directory
    only by what it recorded in it or under it, and a directory the walk stepped into by name since the last
    link has nothing recorded in it yet, so a `..` climbing back out of one, as in `tmp/../review`, makes a
    chain a snapshot could not vouch for: the walk ends there, for the scan and the views over its snapshot
    alike. A `..` climbing out of the directory a link sits in is followed, since the recorded link makes
    that directory and its ancestors known.

    Args:
        path: The root-relative path to walk, spelled as given, links unresolved.
        entries: What each component is, and where each link leads; whatever it raises propagates unchanged.
        follow_links: Whether a symlink is spliced in and followed; when false the walk ends at the first one.

    Returns:
        The real path and its kind, or `None` when no directory or regular file is there: a component is
        missing, a component on the way is no directory, the last one is neither a directory, a regular file
        nor a symlink, a symlink is not followed or is gone, its target is absolute or climbs above the root, a
        `..` climbs out of a directory the walk stepped into, or the chain is longer than `MAX_LINKS`.

    Raises:
        Exception: Whatever `entries` raises: the disk lookup's `SnapshotEntryInspectError` and
            `SnapshotLinkReadError`; the snapshot lookups raise nothing.
    """
    resolved = ROOT
    remaining = list(path.parts)
    links_followed = 0
    stepped_into_directory = False  # since the last link, or since the start
    while remaining:
        part = remaining.pop(0)
        if part == '..':
            if resolved == ROOT or stepped_into_directory:
                return None
            resolved = resolved.parent
            continue
        candidate = resolved / part
        kind = entries.kind(candidate)
        match kind:
            case EntryKind.DIRECTORY:
                resolved = candidate
                stepped_into_directory = True
            case EntryKind.FILE:
                if remaining:
                    return None  # a file is no directory to step into
                return RealPath(candidate, EntryKind.FILE)
            case EntryKind.OTHER | None:
                return None  # nothing is there, or nothing the scan reads
            case EntryKind.SYMLINK:
                target = entries.read_link_target(candidate)
                if target is None:
                    return None  # gone since `kind` answered, so nothing is there to follow
                links_followed += 1
                if not follow_links or target.is_absolute() or links_followed > MAX_LINKS:
                    return None
                remaining = list(target.parts) + remaining
                stepped_into_directory = False
            case _:
                assert_never(kind)
    return RealPath(resolved, EntryKind.DIRECTORY)


def real_scan_root(scan_root: ScanRoot, entries: EntryLookup) -> ScanRoot | None:
    """The root the scan of `scan_root` lists from: its directory at the real path it leads to.

    A root that follows links is walked through every link on the way to its directory; one that does not
    ends at the first link and lists nothing. A snapshot has no record for a lone file, so a root that is one
    lists nothing either: it is seen only through a listing of its parent, and a scope that must answer whether
    a root exists lists that parent too.

    Args:
        scan_root: One root of the scope, as declared.
        entries: What each component on the way is, and where each link leads.

    Returns:
        The root at its real directory, with the declared depth and link policy, or `None` when the walk
        leads to no directory (see `walk_to_real_path`).

    Raises:
        Exception: Whatever `entries` raises: the disk lookup's `SnapshotEntryInspectError` and
            `SnapshotLinkReadError`; the snapshot lookups raise nothing.
    """
    leads_to = walk_to_real_path(scan_root.directory, entries, follow_links=scan_root.follow_links)
    if leads_to is None or leads_to.kind is not EntryKind.DIRECTORY:
        return None
    return ScanRoot(leads_to.path, scan_root.depth, follow_links=scan_root.follow_links)


def linked_scan_root(scan_root: ScanRoot, link: RootRelativePath, directory: RootRelativePath) -> ScanRoot | None:
    """The root the scan of `scan_root` adds by following `link` to the real `directory` it leads to.

    A link is followed only where a root that follows links lists it. It uses up one level of depth, as a
    DIRECTORY entry does: the linked directory is listed with one level less than the directory holding the
    link was. A link in a directory listed with no depth left adds no root; the scan reads a linked file
    there, but lists no linked directory.

    Args:
        scan_root: A root the scan lists from, at its real directory.
        link: The root-relative symlink, wherever it sits.
        directory: The real directory the link leads to, by `walk_to_real_path` with links followed.

    Returns:
        A root at `directory` that follows links, or `None` when `scan_root` does not follow links, does not
        list `link`, or lists it with no depth left.
    """
    if not scan_root.follow_links or not scan_root.is_covering(link):
        return None
    depth_at_link = scan_root.depth - scan_root.listing_level(link)
    if depth_at_link == 0:
        return None
    return ScanRoot(directory, depth_at_link - 1, follow_links=True)
