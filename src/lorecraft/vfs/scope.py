"""What a scan reads, as declared: whether a path lies in what a scope of scan roots reads.

A scope is configuration, not content. `take_snapshot` in `disk.py` reads what a scope declares; this module
answers the other half, whether the scan of a scope lists the directory holding a path, so that a snapshot
holding nothing at the path means nothing was there. The answer comes from the declaration, each root's
directory, depth and link policy, and never from which directories the snapshot happens to hold: a directory
the scope covers but the disk lacks is still in the scope, and everything in it is missing.

Links are the one thing the declaration cannot settle alone, since a link decides where a path leads. The
answer follows the links the snapshot recorded, and only those: a scan records every link in what it lists and
every link on the way to a scope root, so inside the scope no other link exists. Whether a link's target exists
plays no part, with one exception. A `..` in a target climbs out of a directory only where the snapshot shows a
directory is there. A component taken for a directory that is not one would otherwise lead the climb somewhere that
exists. How a root expands through a link is not repeated here: the scan and this query both apply the rules of
`root_expansion.py`, the scan to what it finds on disk and this query to what the snapshot recorded.

Expanding the roots through the links costs far more than asking about one path, and it depends on the scope and
the links alone, so it is kept apart from the question: a `ScopeIndex` expands them once and answers any number
of paths.
"""

from pathlib import PurePosixPath
from typing import assert_never

from lorecraft.core.path import RootRelativePath

from .root_expansion import (
    ResolvedDirectory,
    ResolvedFile,
    find_destination,
    find_linked_scan_root,
    find_listed_scan_root,
)
from .scan_root import ScanRoot
from .snapshot import Link, Snapshot
from .view import EntryKind, RootExit


class ScopeIndex:
    """A scope expanded once through the links a snapshot recorded, to say whether any path is in it.

    It holds the recorded links, indexed by path, and every root the scan lists from, each at a resolved directory,
    one for each link the scan follows included. Both depend on the scope and the links alone, never on a path
    asked about, so one index answers every path of a snapshot. It never changes once built, so one index can be
    shared by every caller.
    """

    def __init__(self, snapshot: Snapshot) -> None:
        """Index the links a snapshot recorded and expand its scope's roots through them; reads no disk.

        The scope, the links and the climbed directories are taken from the one snapshot, since only together
        do they describe a scan.

        Args:
            snapshot: The snapshot to answer for; only its scope, its links and its climbed directories are read,
                never a listing or a file.
        """
        self._recorded = _RecordedLinks(snapshot.links, snapshot.climbed_directories)
        self._listed_roots = _listed_scan_roots(snapshot.scope, self._recorded)

    def is_in_scope(self, path: RootRelativePath) -> bool:
        """Whether a scan of the scope lists the directory `path` sits in, so the snapshot holds whatever is there.

        The path's directory is walked from the root through the recorded links, to where it really is; the
        entry there is in the scope when a root covers it (`ScanRoot.is_covering`). The roots are the scope's,
        each at the resolved directory the scan starts at, and one more for each link the scan follows: the resolved
        directory the link leads to, with the depth the link leaves.

        Args:
            path: The root-relative entry to ask about; it need not exist, and nor need its directory.

        Returns:
            True when the scan lists the directory the path leads into, whether or not that directory exists.
            False when it does not, and when the walk leaves what the snapshot can follow: a link with an
            absolute target, one climbing above the root, a `..` out of a directory the snapshot does not show to
            exist, or a chain longer than `MAX_LINKS`.
        """
        walked = find_destination(path.parent, self._recorded, follow_links=True)
        match walked:
            case ResolvedDirectory(path=directory):
                entry = directory / path.name
            case ResolvedFile():
                raise AssertionError('unreachable: the recorded lookup never answers FILE')
            case RootExit() | None:
                return False
            case _:
                assert_never(walked)
        for scan_root in self._listed_roots:
            if scan_root.is_covering(entry):
                return True
        return False


class _RecordedLinks:
    """What the walks of the scope query see: the links and the climbed directories a snapshot recorded.

    The `EntryLookup` this query hands to the rules of `root_expansion.py`. A component with no link recorded
    is taken as a directory, whether or not one exists, since the question is where a path would lead, not
    what is there. A `..` is where that guess would matter: out of a component that is missing or a file, the
    scan stops, while a climb would lead back to a directory that exists. So a `..` climbs only out of a directory
    the snapshot shows to exist: one the scan climbed out of, or one a climbed directory or a recorded link sits under.
    Every chain the scan walked climbed only out of directories it recorded, so this refuses only a climb the scan
    never made.
    """

    def __init__(self, links: tuple[Link, ...], climbed_directories: tuple[RootRelativePath, ...]) -> None:
        """Index the recorded links by path, and the directories known to exist.

        Args:
            links: Every link the snapshot recorded, `Snapshot.links`.
            climbed_directories: Every directory the scan climbed out of, `Snapshot.climbed_directories`.
        """
        self._targets: dict[RootRelativePath, PurePosixPath] = {}
        for link in links:
            self._targets[link.path] = link.target
        # A climbed directory exists, and a recorded link sits in one, so each of them and its ancestors exist.
        self._known_directories: set[RootRelativePath] = set()
        for directory in climbed_directories:
            self._known_directories.add(directory)
            self._known_directories.update(directory.parents)
        for link in links:
            self._known_directories.update(link.path.parents)

    def paths(self) -> tuple[RootRelativePath, ...]:
        """Every recorded link's root-relative path."""
        return tuple(self._targets)

    def find_kind(self, path: RootRelativePath) -> EntryKind:
        """SYMLINK where a link is recorded at `path`, DIRECTORY anywhere else; see `EntryLookup.find_kind`.

        Never FILE: `ScopeIndex.is_in_scope` and `_listed_scan_roots` raise on a walk that ends at a file, relying on
        this.

        Args:
            path: The root-relative entry the walk reached.
        """
        if path in self._targets:
            return EntryKind.SYMLINK
        return EntryKind.DIRECTORY

    def find_link_target(self, path: RootRelativePath) -> PurePosixPath | None:
        """The recorded target of the link at `path`; see `EntryLookup.find_link_target`.

        Args:
            path: The root-relative link, one `kind` answered SYMLINK for.

        Returns:
            The target as recorded, or `None` when no target was recorded at `path`.
        """
        return self._targets.get(path)

    def may_climb_out_of(self, directory: RootRelativePath) -> bool:
        """Whether the snapshot shows `directory` to exist, so a `..` may climb out of it; see `EntryLookup`.

        Args:
            directory: The directory the walk is in, perhaps only taken for one.
        """
        return directory in self._known_directories


def _listed_scan_roots(scope: tuple[ScanRoot, ...], recorded: _RecordedLinks) -> tuple[ScanRoot, ...]:
    """Every root the scan of `scope` lists from, each at a resolved directory, links it follows included.

    This retraces `take_snapshot` from the declaration, through the same rules: each declared root starts where
    `find_listed_scan_root` puts it, and each recorded link adds the root `find_linked_scan_root` gives for a root
    already found; those roots add their own. The roots are finite: each added one sits at a directory a recorded
    link leads to, and its depth is either unlimited, when the root it came from has no limit, or less than that
    root's. A root found again is not added again, so a link leading back to an ancestor of itself ends the
    expansion, as it ends the scan.

    Args:
        scope: The declared roots, as `take_snapshot` was handed them.
        recorded: Every link the snapshot recorded, as the walks see them.
    """
    listed_roots: list[ScanRoot] = []
    for scan_root in scope:
        listed_root = find_listed_scan_root(scan_root, recorded)
        if listed_root is not None:
            listed_roots.append(listed_root)

    # Where each recorded link leads, walked once rather than once for every root that lists it.
    linked_directories: dict[RootRelativePath, RootRelativePath] = {}
    for link in recorded.paths():
        leads_to = find_destination(link, recorded, follow_links=True)
        match leads_to:
            case ResolvedDirectory(path=directory):
                linked_directories[link] = directory
            case ResolvedFile():
                raise AssertionError('unreachable: the recorded lookup never answers FILE')
            case RootExit() | None:
                pass  # the scan follows no link that leads nowhere or out of the root
            case _:
                assert_never(leads_to)

    pending = list(listed_roots)
    while pending:
        scan_root = pending.pop()
        for link, directory in linked_directories.items():
            linked_root = find_linked_scan_root(scan_root, link, directory)
            if linked_root is not None and linked_root not in listed_roots:
                listed_roots.append(linked_root)
                pending.append(linked_root)
    return tuple(listed_roots)
