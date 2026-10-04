"""How a scan root expands through links: the walk, where a root starts, and the root a followed link adds.

Nothing here touches the disk. Each walk reads a tree written in the test through a hand-written
`EntryLookup`, so the rules are seen apart from either of their callers; that the scan and the scope query
agree through them is covered in `tests/it/test_filesystem.py`.
"""

from collections.abc import Mapping
from pathlib import PurePosixPath

import pytest

from lorecraft.core.num import UnsignedInt
from lorecraft.core.path import RootRelativePath

from ..root_expansion import (
    MAX_LINKS,
    ResolvedDirectory,
    ResolvedFile,
    find_destination,
    find_linked_scan_root,
    find_listed_scan_root,
)
from ..scan_root import ScanRoot
from ..view import EntryKind, RootExit


def _path(raw: str) -> RootRelativePath:
    """Parse a root-relative path written in a test.

    Args:
        raw: The path with `/` separators.
    """
    return RootRelativePath.parse(raw)


class _FakeTree:
    """An `EntryLookup` over a tree written in the test; a path it does not name is missing."""

    def __init__(
        self,
        *,
        directories: tuple[str, ...] = (),
        files: tuple[str, ...] = (),
        others: tuple[str, ...] = (),
        links: Mapping[str, str] | None = None,
        gone_links: tuple[str, ...] = (),
        unclimbable: tuple[str, ...] = (),
    ) -> None:
        """Name each entry of the tree by its kind.

        Args:
            directories: Every directory, ancestors included; the root is one without being named.
            files: Every regular file.
            others: Every entry that is neither a directory, a regular file nor a symlink.
            links: Each symlink's path, mapped to its target as `os.readlink` would return it.
            gone_links: Each symlink that vanishes between its inspection and the read of its target.
            unclimbable: Each directory a `..` may not climb out of, as the scope query refuses a guessed one.
        """
        self._kinds: dict[RootRelativePath, EntryKind] = {}
        for raw in directories:
            self._kinds[_path(raw)] = EntryKind.DIRECTORY
        for raw in files:
            self._kinds[_path(raw)] = EntryKind.FILE
        for raw in others:
            self._kinds[_path(raw)] = EntryKind.OTHER
        for raw in gone_links:
            self._kinds[_path(raw)] = EntryKind.SYMLINK
        self._targets: dict[RootRelativePath, PurePosixPath] = {}
        if links is not None:
            for raw, target in links.items():
                self._kinds[_path(raw)] = EntryKind.SYMLINK
                self._targets[_path(raw)] = PurePosixPath(target)
        self._unclimbable: set[RootRelativePath] = set()
        for raw in unclimbable:
            self._unclimbable.add(_path(raw))

    def find_kind(self, path: RootRelativePath) -> EntryKind | None:
        """The kind the test named `path` with; `None` when it named none.

        Args:
            path: The root-relative entry the walk reached.
        """
        return self._kinds.get(path)

    def find_link_target(self, path: RootRelativePath) -> PurePosixPath | None:
        """The target the test gave the link at `path`; `None` for a link that vanished.

        Args:
            path: The root-relative link, one `kind` answered SYMLINK for.
        """
        return self._targets.get(path)

    def may_climb_out_of(self, directory: RootRelativePath) -> bool:
        """Whether the test left `directory` climbable; every directory is unless named unclimbable.

        Args:
            directory: The directory the walk climbs out of.
        """
        return directory not in self._unclimbable


@pytest.mark.unit
class TestFindDestination:
    def test_find_destination_with_a_directory_returns_it_as_a_directory(self) -> None:
        #: Given
        tree = _FakeTree(directories=('docs', 'docs/code'))
        path = _path('docs/code')
        #: When
        leads_to = find_destination(path, tree, follow_links=False)

        #: Then
        assert leads_to == ResolvedDirectory(_path('docs/code')), 'a directory leads to itself'

    def test_find_destination_with_a_regular_file_returns_it_as_a_file(self) -> None:
        #: Given
        tree = _FakeTree(directories=('docs',), files=('docs/a.md',))
        path = _path('docs/a.md')
        #: When
        leads_to = find_destination(path, tree, follow_links=False)

        #: Then
        assert leads_to == ResolvedFile(_path('docs/a.md')), 'a regular file at the end ends the walk'

    def test_find_destination_through_a_file_component_returns_none(self) -> None:
        #: Given
        tree = _FakeTree(directories=('docs',), files=('docs/a.md',))
        path = _path('docs/a.md/b')
        #: When
        leads_to = find_destination(path, tree, follow_links=False)

        #: Then
        assert leads_to is None, 'a file on the way is no directory to step into'

    def test_find_destination_with_a_missing_component_returns_none(self) -> None:
        #: Given
        tree = _FakeTree(directories=('docs',))
        path = _path('docs/nope/a.md')
        #: When
        leads_to = find_destination(path, tree, follow_links=False)

        #: Then
        assert leads_to is None, 'nothing is there to step into'

    def test_find_destination_with_an_other_entry_returns_none(self) -> None:
        #: Given
        tree = _FakeTree(directories=('docs',), others=('docs/fifo',))
        path = _path('docs/fifo')
        #: When
        leads_to = find_destination(path, tree, follow_links=False)

        #: Then
        assert leads_to is None, 'an entry that is neither a directory nor a regular file is nowhere to read'

    def test_find_destination_following_a_link_returns_the_directory_it_leads_to(self) -> None:
        #: Given
        tree = _FakeTree(directories=('skills', 'skills/a'), links={'docs': 'skills'})
        path = _path('docs/a')
        #: When
        leads_to = find_destination(path, tree, follow_links=True)

        #: Then
        assert leads_to == ResolvedDirectory(_path('skills/a')), 'the link splices its target in'

    def test_find_destination_not_following_links_with_a_link_on_the_way_returns_none(self) -> None:
        #: Given
        tree = _FakeTree(directories=('skills', 'skills/a'), links={'docs': 'skills'})
        path = _path('docs/a')
        #: When
        leads_to = find_destination(path, tree, follow_links=False)

        #: Then
        assert leads_to is None, 'without following links the walk ends at the first one'

    def test_find_destination_with_a_link_that_vanished_returns_none(self) -> None:
        #: Given
        tree = _FakeTree(gone_links=('docs',))
        path = _path('docs/a')
        #: When
        leads_to = find_destination(path, tree, follow_links=True)

        #: Then
        assert leads_to is None, 'a link gone before its target was read leads nowhere'

    def test_find_destination_with_an_absolute_target_returns_the_link_as_the_exit(self) -> None:
        #: Given
        tree = _FakeTree(links={'docs': '/srv/docs'})
        path = _path('docs')
        #: When
        leads_to = find_destination(path, tree, follow_links=True)

        #: Then
        assert leads_to == RootExit(_path('docs'), PurePosixPath('/srv/docs')), 'an absolute target is outside the root'

    def test_find_destination_with_a_target_climbing_above_the_root_returns_the_link_as_the_exit(self) -> None:
        #: Given
        tree = _FakeTree(links={'docs': '../docs'})
        path = _path('docs')
        #: When
        leads_to = find_destination(path, tree, follow_links=True)

        #: Then
        assert leads_to == RootExit(_path('docs'), PurePosixPath('../docs')), 'a target above the root is outside it'

    def test_find_destination_with_a_link_deeper_down_climbing_above_the_root_returns_it_as_the_exit(self) -> None:
        #: Given
        tree = _FakeTree(directories=('a',), links={'a/l': '../../outside'})
        path = _path('a/l')
        #: When
        leads_to = find_destination(path, tree, follow_links=True)

        #: Then
        assert leads_to == RootExit(_path('a/l'), PurePosixPath('../../outside')), (
            'climbing out of the link directory to the root and once more leaves the root'
        )

    def test_find_destination_with_a_chain_leaving_the_root_returns_the_last_link_as_the_exit(self) -> None:
        #: Given
        tree = _FakeTree(directories=('a',), links={'a/l': '../hop/x', 'hop': '/srv/team'})
        path = _path('a/l')
        #: When
        leads_to = find_destination(path, tree, follow_links=True)

        #: Then
        assert leads_to == RootExit(_path('hop'), PurePosixPath('/srv/team')), (
            'the exit is the link the chain leaves through, not the one it started at'
        )

    def test_find_destination_not_following_links_with_an_absolute_target_returns_none(self) -> None:
        #: Given
        tree = _FakeTree(links={'docs': '/srv/docs'})
        path = _path('docs')
        #: When
        leads_to = find_destination(path, tree, follow_links=False)

        #: Then
        assert leads_to is None, 'a walk that follows no link never learns where one leads'

    def test_find_destination_with_a_target_climbing_out_of_the_link_directory_returns_where_it_leads(
        self,
    ) -> None:
        #: Given
        tree = _FakeTree(directories=('a', 'b'), links={'a/l': '../b'})
        path = _path('a/l')
        #: When
        leads_to = find_destination(path, tree, follow_links=True)

        #: Then
        assert leads_to == ResolvedDirectory(_path('b')), 'the directory a link sits in is known'

    def test_find_destination_with_a_target_climbing_out_of_a_directory_stepped_into_returns_where_it_leads(
        self,
    ) -> None:
        #: Given
        tree = _FakeTree(directories=('a', 'a/tmp', 'a/alpha'), links={'a/x': 'tmp/../alpha'})
        path = _path('a/x')
        #: When
        leads_to = find_destination(path, tree, follow_links=True)

        #: Then
        assert leads_to == ResolvedDirectory(_path('a/alpha')), (
            'a `..` after a resolved directory stepped into by name is its parent'
        )

    def test_find_destination_with_nested_steps_and_climbs_returns_where_it_leads(self) -> None:
        #: Given
        tree = _FakeTree(
            directories=('a', 'a/tmp', 'a/tmp/sub', 'b', 'b/alpha'),
            links={'a/x': 'tmp/sub/../../../b/alpha'},
        )
        path = _path('a/x')
        #: When
        leads_to = find_destination(path, tree, follow_links=True)

        #: Then
        assert leads_to == ResolvedDirectory(_path('b/alpha')), (
            'each `..` climbs out of the resolved directory the walk is in, however it got there'
        )

    def test_find_destination_with_a_target_climbing_back_into_the_root_returns_the_root(self) -> None:
        #: Given
        tree = _FakeTree(directories=('a', 'a/tmp'), links={'a/x': 'tmp/../..'})
        path = _path('a/x')
        #: When
        leads_to = find_destination(path, tree, follow_links=True)

        #: Then
        assert leads_to == ResolvedDirectory(_path('.')), 'the root is a directory a chain may end at'

    def test_find_destination_with_a_climb_above_the_root_through_a_stepped_into_directory_returns_the_exit(
        self,
    ) -> None:
        #: Given
        tree = _FakeTree(directories=('a', 'a/tmp'), links={'a/x': 'tmp/../../..'})
        path = _path('a/x')
        #: When
        leads_to = find_destination(path, tree, follow_links=True)

        #: Then
        assert leads_to == RootExit(_path('a/x'), PurePosixPath('tmp/../../..')), (
            'past the root is outside it, whatever directories the chain stepped into on the way'
        )

    def test_find_destination_with_a_climb_through_a_link_climbs_out_of_the_directory_it_leads_to(self) -> None:
        #: Given
        tree = _FakeTree(directories=('a', 'b', 'b/c'), links={'a/x': 'y/..', 'a/y': '../b/c'})
        path = _path('a/x')
        #: When
        leads_to = find_destination(path, tree, follow_links=True)

        #: Then
        assert leads_to == ResolvedDirectory(_path('b')), (
            'a `..` after a link is the parent of where the link leads, as the kernel resolves it'
        )

    def test_find_destination_with_a_climb_through_a_file_returns_none(self) -> None:
        #: Given
        tree = _FakeTree(directories=('a', 'a/alpha'), files=('a/f',), links={'a/x': 'f/../alpha'})
        path = _path('a/x')
        #: When
        leads_to = find_destination(path, tree, follow_links=True)

        #: Then
        assert leads_to is None, 'a file is no directory to climb out of'

    def test_find_destination_with_a_climb_through_a_missing_directory_returns_none(self) -> None:
        #: Given
        tree = _FakeTree(directories=('a', 'a/alpha'), links={'a/x': 'missing/../alpha'})
        path = _path('a/x')
        #: When
        leads_to = find_destination(path, tree, follow_links=True)

        #: Then
        assert leads_to is None, 'a missing directory is nothing to climb out of'

    def test_find_destination_with_a_climb_the_lookup_refuses_returns_none(self) -> None:
        #: Given
        tree = _FakeTree(directories=('a', 'a/tmp', 'a/alpha'), links={'a/x': 'tmp/../alpha'}, unclimbable=('a/tmp',))
        path = _path('a/x')
        #: When
        leads_to = find_destination(path, tree, follow_links=True)

        #: Then
        assert leads_to is None, 'a `..` the lookup does not vouch for ends the walk'

    def test_find_destination_with_a_looping_link_returns_none(self) -> None:
        #: Given
        tree = _FakeTree(links={'docs': 'docs'})
        path = _path('docs')
        #: When
        leads_to = find_destination(path, tree, follow_links=True)

        #: Then
        assert leads_to is None, f'a chain longer than {MAX_LINKS} links counts as a loop'


@pytest.mark.unit
class TestFindListedScanRoot:
    def test_find_listed_scan_root_following_links_with_a_link_on_the_way_returns_the_root_where_it_leads(
        self,
    ) -> None:
        #: Given
        tree = _FakeTree(directories=('shared', 'shared/skills'), links={'.agents': 'shared'})
        scan_root = ScanRoot(_path('.agents/skills'), depth=UnsignedInt(1), follow_links=True)

        #: When
        resolved_root = find_listed_scan_root(scan_root, tree)

        #: Then
        assert resolved_root == ScanRoot(_path('shared/skills'), depth=UnsignedInt(1), follow_links=True), (
            'a following root starts where its directory leads, with its declared depth and policy'
        )

    def test_find_listed_scan_root_with_no_depth_limit_returns_the_root_with_no_depth_limit(self) -> None:
        #: Given
        tree = _FakeTree(directories=('shared', 'shared/skills'), links={'.agents': 'shared'})
        scan_root = ScanRoot(_path('.agents/skills'), depth=None, follow_links=True)

        #: When
        resolved_root = find_listed_scan_root(scan_root, tree)

        #: Then
        assert resolved_root == ScanRoot(_path('shared/skills'), depth=None, follow_links=True), (
            'a root with no depth limit keeps it at its resolved directory'
        )

    def test_find_listed_scan_root_not_following_links_with_a_link_on_the_way_returns_none(self) -> None:
        #: Given
        tree = _FakeTree(directories=('shared', 'shared/skills'), links={'.agents': 'shared'})
        scan_root = ScanRoot(_path('.agents/skills'), depth=UnsignedInt(1))

        #: When
        resolved_root = find_listed_scan_root(scan_root, tree)

        #: Then
        assert resolved_root is None, 'a root that does not follow links lists nothing behind one'

    def test_find_listed_scan_root_with_a_regular_file_returns_none(self) -> None:
        #: Given
        tree = _FakeTree(files=('README.md',))
        scan_root = ScanRoot(_path('README.md'), depth=UnsignedInt(0))

        #: When
        resolved_root = find_listed_scan_root(scan_root, tree)

        #: Then
        assert resolved_root is None, 'a lone file is no directory to list from'

    def test_find_listed_scan_root_following_links_with_a_link_to_a_file_at_the_end_returns_none(self) -> None:
        #: Given
        tree = _FakeTree(directories=('shared',), files=('shared/a.md',), links={'docs': 'shared/a.md'})
        scan_root = ScanRoot(_path('docs'), depth=UnsignedInt(1), follow_links=True)

        #: When
        resolved_root = find_listed_scan_root(scan_root, tree)

        #: Then
        assert resolved_root is None, 'a link to a lone file is no directory to list from'

    def test_find_listed_scan_root_with_a_missing_directory_returns_none(self) -> None:
        #: Given
        tree = _FakeTree()
        scan_root = ScanRoot(_path('docs'), depth=UnsignedInt(1))

        #: When
        resolved_root = find_listed_scan_root(scan_root, tree)

        #: Then
        assert resolved_root is None, 'a missing root lists nothing'


@pytest.mark.unit
class TestFindLinkedScanRoot:
    def test_find_linked_scan_root_with_a_link_listed_with_depth_left_returns_a_root_one_level_shallower(self) -> None:
        #: Given
        scan_root = ScanRoot(_path('skills'), depth=UnsignedInt(2), follow_links=True)
        link = _path('skills/a')
        directory = _path('shared/a')
        #: When
        linked_root = find_linked_scan_root(scan_root, link, directory)

        #: Then
        assert linked_root == ScanRoot(_path('shared/a'), depth=UnsignedInt(1), follow_links=True), (
            'the link uses up one level of depth, as a directory entry does'
        )

    def test_find_linked_scan_root_with_a_link_below_the_root_returns_the_depth_left_at_the_link(self) -> None:
        #: Given
        scan_root = ScanRoot(_path('skills'), depth=UnsignedInt(2), follow_links=True)
        link = _path('skills/a/b')
        directory = _path('shared/b')
        #: When
        linked_root = find_linked_scan_root(scan_root, link, directory)

        #: Then
        assert linked_root == ScanRoot(_path('shared/b'), depth=UnsignedInt(0), follow_links=True), (
            'a link one level below the root is listed with one level left, and uses it up'
        )

    def test_find_linked_scan_root_with_a_link_listed_with_no_depth_left_returns_none(self) -> None:
        #: Given
        scan_root = ScanRoot(_path('skills'), depth=UnsignedInt(0), follow_links=True)
        link = _path('skills/a')
        directory = _path('shared/a')
        #: When
        linked_root = find_linked_scan_root(scan_root, link, directory)

        #: Then
        assert linked_root is None, 'a link listed with no depth left adds no directory to list'

    def test_find_linked_scan_root_from_a_root_not_following_links_returns_none(self) -> None:
        #: Given
        scan_root = ScanRoot(_path('skills'), depth=UnsignedInt(2))
        link = _path('skills/a')
        directory = _path('shared/a')
        #: When
        linked_root = find_linked_scan_root(scan_root, link, directory)

        #: Then
        assert linked_root is None, 'a root that does not follow links never follows one it lists'

    def test_find_linked_scan_root_with_a_link_the_root_does_not_list_returns_none(self) -> None:
        #: Given
        scan_root = ScanRoot(_path('skills'), depth=UnsignedInt(2), follow_links=True)
        link = _path('docs/a')
        directory = _path('shared/a')
        #: When
        linked_root = find_linked_scan_root(scan_root, link, directory)

        #: Then
        assert linked_root is None, 'a link outside what the root lists is not followed from it'

    def test_find_linked_scan_root_from_a_root_with_no_depth_limit_returns_a_root_with_no_depth_limit(self) -> None:
        #: Given
        scan_root = ScanRoot(_path('skills'), depth=None, follow_links=True)
        link = _path('skills/a/references/deep/shared')
        directory = _path('shared/references')
        #: When
        linked_root = find_linked_scan_root(scan_root, link, directory)

        #: Then
        assert linked_root == ScanRoot(_path('shared/references'), depth=None, follow_links=True), (
            'a link at any depth under a root with no limit is listed with no limit either'
        )

    def test_find_linked_scan_root_from_a_root_with_no_depth_limit_to_an_ancestor_returns_a_root_equal_to_it(
        self,
    ) -> None:
        #: Given
        scan_root = ScanRoot(_path('skills'), depth=None, follow_links=True)
        link = _path('skills/a/up')
        directory = _path('skills')
        #: When
        linked_root = find_linked_scan_root(scan_root, link, directory)

        #: Then
        assert linked_root == scan_root, 'a link back to the root adds the root itself, which the scan has listed'
