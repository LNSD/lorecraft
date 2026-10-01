"""What a scan reads, as declared: whether a path lies in what a scope of scan roots reads.

A scope is configuration, not content. `take_snapshot` in `disk.py` reads what a scope declares; this module
answers the other half, whether the scan of a scope lists the directory holding a path, so that a snapshot
holding nothing at the path means nothing was there. The answer comes from the declaration, each root's
directory, depth and link policy, and never from which directories the snapshot happens to hold: a directory
the scope covers but the disk lacks is still in the scope, and everything in it is missing.

Links are the one thing the declaration cannot settle alone, since a link decides where a path leads. The
answer follows the links the snapshot recorded, the way the scan and `VirtualFileSystem` follow them, and only
those: a scan records every link in what it lists and every link on the way to a scope root, so inside the
scope no other link exists. Whether a link's target exists plays no part.
"""

from collections.abc import Mapping
from pathlib import PurePosixPath

from lorecraft.core.path import ROOT, RootRelativePath

from .scan_root import ScanRoot
from .snapshot import MAX_LINKS, Link


def is_in_scope(scope: tuple[ScanRoot, ...], links: tuple[Link, ...], path: RootRelativePath) -> bool:
    """Whether a scan of `scope` lists the directory `path` sits in, so the snapshot holds whatever is there.

    The path's directory is walked from the root through the recorded `links`, to where it really
    is; the entry there is in the scope when a root covers it (`ScanRoot.is_covering`). The roots are the scope's,
    each at the real directory the scan starts at, and, for a root that follows links, one more for each link
    the scan follows from it: the real directory the link leads to, with the depth the link leaves.

    Args:
        scope: The scope the snapshot of `links` was taken of, `Snapshot.scope`; another scope's answer would not
            describe it.
        links: Every link the snapshot recorded, `Snapshot.links`; no listing and no file of the snapshot is read.
        path: The root-relative entry to ask about; it need not exist, and nor need its directory.

    Returns:
        True when the scan lists the directory the path leads into, whether or not that directory exists.
        False when it does not, and when the walk leaves what the snapshot can follow: a link with an absolute
        target, one climbing above the root or out of a directory the walk stepped into by name, as the scan
        refuses too, or a chain longer than `MAX_LINKS`.
    """
    targets: dict[RootRelativePath, PurePosixPath] = {}
    for link in links:
        targets[link.path] = link.target

    directory = _walk_recorded_links(targets, path.parent)
    if directory is None:
        return False
    entry = directory / path.name
    for scan_root in _real_scan_roots(scope, targets):
        if scan_root.is_covering(entry):
            return True
    return False


def _real_scan_roots(
    scope: tuple[ScanRoot, ...], links: Mapping[RootRelativePath, PurePosixPath]
) -> tuple[ScanRoot, ...]:
    """Every root the scan of `scope` lists from, each at a real directory, links it follows included.

    This retraces `take_snapshot` from the declaration. A root that follows links starts where its directory
    leads; one that does not starts at its directory, as written. Then each recorded link a following root
    covers, in a directory listed with depth left, adds a following root at the real directory it leads to,
    one level shallower, as the scan queues it; those roots add their own. The depth falls with each link, so
    the roots are finite.

    Args:
        scope: The declared roots, as `take_snapshot` was handed them.
        links: Every link the snapshot recorded, keyed by its root-relative path.
    """
    real_roots: list[ScanRoot] = []
    for scan_root in scope:
        if not scan_root.follow_links:
            # Kept as written. With a link on the way the scan lists nothing here, and the root then covers nothing
            # a query reaches either: a walked path never lies under a recorded link, since the walk follows it.
            real_roots.append(scan_root)
            continue
        directory = _walk_recorded_links(links, scan_root.directory)
        if directory is not None:
            real_roots.append(ScanRoot(directory, scan_root.depth, follow_links=True))

    pending: list[ScanRoot] = []
    for scan_root in real_roots:
        if scan_root.follow_links:
            pending.append(scan_root)
    while pending:
        scan_root = pending.pop()
        for link in links:
            if not scan_root.is_covering(link):
                continue
            depth_at_link = scan_root.depth - scan_root.listing_level(link)
            if depth_at_link == 0:
                continue  # the scan reads a linked file here, but lists no linked directory
            target = _walk_recorded_links(links, link)
            if target is None:
                continue
            linked_root = ScanRoot(target, depth_at_link - 1, follow_links=True)
            if linked_root not in real_roots:
                real_roots.append(linked_root)
                pending.append(linked_root)
    return tuple(real_roots)


def _walk_recorded_links(
    links: Mapping[RootRelativePath, PurePosixPath], path: RootRelativePath
) -> RootRelativePath | None:
    """Where `path` leads, every recorded link on the way followed and every other component taken as written.

    The walk follows the rules of the scan's own walk, `_walk_to_real_path` in `disk.py`: a link splices its
    target into the components still to walk, and the walk gives up where the scan does. Unlike it, a
    component with no link recorded is stepped into whether or not it exists, since the question is where the
    path would lead, not what is there.

    Args:
        links: Every link the snapshot recorded, keyed by its root-relative path.
        path: The root-relative path to walk, spelled as given.

    Returns:
        The path with every recorded link resolved, or `None` when a link's target is absolute, climbs above
        the root or with `..` out of a directory the walk stepped into by name since the last link, or the
        chain is longer than `MAX_LINKS`.
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
        target = links.get(candidate)
        if target is None:
            resolved = candidate
            stepped_into_directory = True
            continue
        links_followed += 1
        if target.is_absolute() or links_followed > MAX_LINKS:
            return None
        remaining = list(target.parts) + remaining
        stepped_into_directory = False
    return resolved
