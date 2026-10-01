"""What a scan reads, as declared: whether a path lies in what a scope of scan roots reads.

A scope is configuration, not content. `take_snapshot` in `disk.py` reads what a scope declares; this module
answers the other half, whether the scan of a scope lists the directory holding a path, so that a snapshot
holding nothing at the path means nothing was there. The answer comes from the declaration, each root's
directory, depth and link policy, and never from which directories the snapshot happens to hold: a directory
the scope covers but the disk lacks is still in the scope, and everything in it is missing.

Links are the one thing the declaration cannot settle alone, since a link decides where a path leads. The
answer follows the links the snapshot recorded, and only those: a scan records every link in what it lists and
every link on the way to a scope root, so inside the scope no other link exists. Whether a link's target exists
plays no part. How a root expands through a link is not repeated here: the scan and this query both apply the
rules of `root_expansion.py`, the scan to what it finds on disk and this query to what the snapshot recorded.
"""

from pathlib import PurePosixPath

from lorecraft.core.path import RootRelativePath

from .root_expansion import linked_scan_root, real_scan_root, walk_to_real_path
from .scan_root import ScanRoot
from .snapshot import Link
from .view import EntryKind


def is_in_scope(scope: tuple[ScanRoot, ...], links: tuple[Link, ...], path: RootRelativePath) -> bool:
    """Whether a scan of `scope` lists the directory `path` sits in, so the snapshot holds whatever is there.

    The path's directory is walked from the root through the recorded `links`, to where it really
    is; the entry there is in the scope when a root covers it (`ScanRoot.is_covering`). The roots are the scope's,
    each at the real directory the scan starts at, and one more for each link the scan follows: the real
    directory the link leads to, with the depth the link leaves.

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
    recorded = _RecordedLinks(links)
    directory = walk_to_real_path(path.parent, recorded, follow_links=True)
    if directory is None:
        return False
    entry = directory.path / path.name
    for scan_root in _real_scan_roots(scope, recorded):
        if scan_root.is_covering(entry):
            return True
    return False


class _RecordedLinks:
    """What the walks of the scope query see: the links a snapshot recorded, and nothing else.

    The `EntryLookup` this query hands to the rules of `root_expansion.py`. A component with no link recorded
    is taken as a directory, whether or not one exists, since the question is where a path would lead, not
    what is there.
    """

    def __init__(self, links: tuple[Link, ...]) -> None:
        """Index the recorded links by path.

        Args:
            links: Every link the snapshot recorded, `Snapshot.links`.
        """
        self._targets: dict[RootRelativePath, PurePosixPath] = {}
        for link in links:
            self._targets[link.path] = link.target

    def paths(self) -> tuple[RootRelativePath, ...]:
        """Every recorded link's root-relative path."""
        return tuple(self._targets)

    def kind(self, path: RootRelativePath) -> EntryKind:
        """SYMLINK where a link is recorded at `path`, DIRECTORY anywhere else; see `EntryLookup.kind`.

        Args:
            path: The root-relative entry the walk reached.
        """
        if path in self._targets:
            return EntryKind.SYMLINK
        return EntryKind.DIRECTORY

    def read_link_target(self, path: RootRelativePath) -> PurePosixPath | None:
        """The recorded target of the link at `path`; see `EntryLookup.read_link_target`.

        Args:
            path: The root-relative link, one `kind` answered SYMLINK for.
        """
        return self._targets.get(path)


def _real_scan_roots(scope: tuple[ScanRoot, ...], recorded: _RecordedLinks) -> tuple[ScanRoot, ...]:
    """Every root the scan of `scope` lists from, each at a real directory, links it follows included.

    This retraces `take_snapshot` from the declaration, through the same rules: each declared root starts where
    `real_scan_root` puts it, and each recorded link adds the root `linked_scan_root` gives for a root
    already found; those roots add their own. The depth falls with each link, so the roots are finite.

    Args:
        scope: The declared roots, as `take_snapshot` was handed them.
        recorded: Every link the snapshot recorded, as the walks see them.
    """
    real_roots: list[ScanRoot] = []
    for scan_root in scope:
        real_root = real_scan_root(scan_root, recorded)
        if real_root is not None:
            real_roots.append(real_root)

    # Where each recorded link leads, walked once rather than once for every root that lists it.
    linked_directories: dict[RootRelativePath, RootRelativePath] = {}
    for link in recorded.paths():
        leads_to = walk_to_real_path(link, recorded, follow_links=True)
        if leads_to is not None:
            linked_directories[link] = leads_to.path

    pending = list(real_roots)
    while pending:
        scan_root = pending.pop()
        for link, directory in linked_directories.items():
            linked_root = linked_scan_root(scan_root, link, directory)
            if linked_root is not None and linked_root not in real_roots:
                real_roots.append(linked_root)
                pending.append(linked_root)
    return tuple(real_roots)
