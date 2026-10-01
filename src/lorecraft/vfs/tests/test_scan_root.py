"""One scan root: what it lists by the spelling of a path alone, the depth it refuses, and how deep it reaches.

Each is seen with a depth and with no depth limit: the root a scan lists a level down, and which of two roots
reaches deeper, are where the two differ.

Nothing here touches the disk or reads a link; what a whole scope reads, links included, is `test_scope.py`.
"""

from typing import Final

import pytest

from lorecraft.core.path import RootRelativePath

from ..scan_root import ScanRoot

DOCS: Final[RootRelativePath] = RootRelativePath.parse('docs')


def _path(raw: str) -> RootRelativePath:
    """Parse a root-relative path written in a test.

    Args:
        raw: The path with `/` separators.
    """
    return RootRelativePath.parse(raw)


@pytest.mark.unit
class TestScanRoot:
    def test_construct_with_a_negative_depth_raises_value_error(self) -> None:
        #: Given
        depth = -1

        #: When
        with pytest.raises(ValueError) as exc_info:
            ScanRoot(DOCS, depth=depth)

        #: Then
        assert exc_info.type is ValueError, 'a negative depth, which would list nothing, is a value error'
        assert str(depth) in str(exc_info.value), 'the message names the rejected depth'

    def test_is_covering_at_depth_zero_with_an_entry_of_the_directory_returns_true(self) -> None:
        #: Given
        scan_root = ScanRoot(DOCS, depth=0)
        path = _path('docs/a.md')

        #: When
        covered = scan_root.is_covering(path)

        #: Then
        assert covered is True, 'depth 0 lists the directory itself, so each of its entries is covered'

    def test_is_covering_at_depth_zero_with_an_entry_one_level_below_returns_false(self) -> None:
        #: Given
        scan_root = ScanRoot(DOCS, depth=0)
        path = _path('docs/feat/a.md')

        #: When
        covered = scan_root.is_covering(path)

        #: Then
        assert covered is False, 'depth 0 never enters docs/feat, so an entry in it is not covered'

    def test_is_covering_at_depth_one_with_an_entry_one_level_below_returns_true(self) -> None:
        #: Given
        scan_root = ScanRoot(DOCS, depth=1)
        path = _path('docs/feat/a.md')

        #: When
        covered = scan_root.is_covering(path)

        #: Then
        assert covered is True, 'depth 1 lists each directory in docs/, whether or not docs/feat exists'

    def test_is_covering_at_depth_one_with_an_entry_two_levels_below_returns_false(self) -> None:
        #: Given
        scan_root = ScanRoot(DOCS, depth=1)
        path = _path('docs/feat/deep/a.md')

        #: When
        covered = scan_root.is_covering(path)

        #: Then
        assert covered is False, 'depth 1 lists docs/feat/deep as an entry and never enters it'

    def test_listing_level_with_an_entry_of_the_directory_returns_zero(self) -> None:
        #: Given
        scan_root = ScanRoot(DOCS, depth=1)
        path = _path('docs/a.md')

        #: When
        level = scan_root.listing_level(path)

        #: Then
        assert level == 0, 'docs/ itself lists docs/a.md, so its listing is no level below docs/'

    def test_listing_level_with_an_entry_two_levels_below_returns_two(self) -> None:
        #: Given
        scan_root = ScanRoot(DOCS, depth=1)
        path = _path('docs/feat/deep/a.md')

        #: When
        level = scan_root.listing_level(path)

        #: Then
        assert level == 2, 'docs/feat/deep lists the entry, two levels below docs/, whatever the depth'

    def test_is_covering_at_depth_one_with_a_directory_one_level_below_returns_true(self) -> None:
        #: Given
        scan_root = ScanRoot(DOCS, depth=1)
        path = _path('docs/feat/deep')

        #: When
        covered = scan_root.is_covering(path)

        #: Then
        assert covered is True, 'docs/feat/deep is an entry of docs/feat, which depth 1 lists'

    def test_is_covering_at_depth_two_with_an_entry_two_levels_below_returns_true(self) -> None:
        #: Given
        scan_root = ScanRoot(DOCS, depth=2)
        path = _path('docs/feat/deep/a.md')

        #: When
        covered = scan_root.is_covering(path)

        #: Then
        assert covered is True, 'depth 2 lists docs/feat/deep, so an entry in it is covered'

    def test_is_covering_with_the_directory_itself_returns_false(self) -> None:
        #: Given
        scan_root = ScanRoot(DOCS, depth=1)
        path = DOCS

        #: When
        covered = scan_root.is_covering(path)

        #: Then
        assert covered is False, 'docs is an entry of the root, which the scan walks to and never lists'

    def test_is_covering_with_a_path_outside_the_directory_returns_false(self) -> None:
        #: Given
        scan_root = ScanRoot(DOCS, depth=1)
        path = _path('src/a.md')

        #: When
        covered = scan_root.is_covering(path)

        #: Then
        assert covered is False, 'src/ is no directory under docs/'

    def test_is_covering_with_a_sibling_sharing_the_directory_prefix_returns_false(self) -> None:
        #: Given
        scan_root = ScanRoot(DOCS, depth=1)
        path = _path('docs-old/a.md')

        #: When
        covered = scan_root.is_covering(path)

        #: Then
        assert covered is False, 'paths are compared by component, so docs-old/ is not under docs/'

    def test_is_covering_when_following_links_answers_by_spelling_as_without(self) -> None:
        #: Given
        scan_root = ScanRoot(DOCS, depth=1, follow_links=True)
        path = _path('docs/feat/deep/a.md')

        #: When
        covered = scan_root.is_covering(path)

        #: Then
        assert covered is False, 'following links moves no entry within reach: is_covering reads the spelling alone'

    def test_is_covering_at_the_workspace_root_with_an_entry_of_it_returns_true(self) -> None:
        #: Given
        scan_root = ScanRoot(_path('.'), depth=0)
        path = _path('a.md')

        #: When
        covered = scan_root.is_covering(path)

        #: Then
        assert covered is True, 'a scan of the root at depth 0 lists the root, so a file in it is covered'

    def test_is_covering_with_no_depth_limit_with_an_entry_three_levels_below_returns_true(self) -> None:
        #: Given
        scan_root = ScanRoot(DOCS, depth=None)
        path = _path('docs/feat/deep/deeper/a.md')

        #: When
        covered = scan_root.is_covering(path)

        #: Then
        assert covered is True, 'a root with no depth limit lists every directory below it, at any depth'

    def test_is_covering_with_no_depth_limit_with_the_directory_itself_returns_false(self) -> None:
        #: Given
        scan_root = ScanRoot(DOCS, depth=None)
        path = DOCS

        #: When
        covered = scan_root.is_covering(path)

        #: Then
        assert covered is False, 'no depth limit still leaves docs itself to the listing of its parent'

    def test_is_covering_with_no_depth_limit_with_a_path_outside_the_directory_returns_false(self) -> None:
        #: Given
        scan_root = ScanRoot(DOCS, depth=None)
        path = _path('src/deep/a.md')

        #: When
        covered = scan_root.is_covering(path)

        #: Then
        assert covered is False, 'no depth limit reaches only below docs/, never beside it'


@pytest.mark.unit
class TestScanRootFindRootBelow:
    def test_find_root_below_with_depth_left_returns_a_root_with_the_levels_taken_off(self) -> None:
        #: Given
        scan_root = ScanRoot(DOCS, depth=3)
        directory = _path('docs/feat/deep')

        #: When
        lowered = scan_root.find_root_below(directory, levels=2)

        #: Then
        assert lowered == ScanRoot(directory, depth=1), 'two levels down from depth 3, one level is left'

    def test_find_root_below_with_exactly_the_depth_returns_a_root_at_depth_zero(self) -> None:
        #: Given
        scan_root = ScanRoot(DOCS, depth=1)
        directory = _path('docs/feat')

        #: When
        lowered = scan_root.find_root_below(directory, levels=1)

        #: Then
        assert lowered == ScanRoot(directory, depth=0), 'depth 1 enters docs/feat and lists it with none left'

    def test_find_root_below_past_the_depth_returns_none(self) -> None:
        #: Given
        scan_root = ScanRoot(DOCS, depth=0)
        directory = _path('docs/feat')

        #: When
        lowered = scan_root.find_root_below(directory, levels=1)

        #: Then
        assert lowered is None, 'depth 0 names docs/feat and never enters it'

    def test_find_root_below_with_no_depth_limit_returns_a_root_with_no_depth_limit(self) -> None:
        #: Given
        scan_root = ScanRoot(DOCS, depth=None)
        directory = _path('docs/feat/deep/deeper')

        #: When
        lowered = scan_root.find_root_below(directory, levels=3)

        #: Then
        assert lowered == ScanRoot(directory, depth=None), 'no depth limit stays no limit however far down'

    def test_find_root_below_from_a_root_following_links_returns_a_root_following_links(self) -> None:
        #: Given
        scan_root = ScanRoot(DOCS, depth=None, follow_links=True)
        directory = _path('shared/feat')

        #: When
        lowered = scan_root.find_root_below(directory, levels=1)

        #: Then
        assert lowered == ScanRoot(directory, depth=None, follow_links=True), 'the link policy is kept'


@pytest.mark.unit
class TestScanRootIsAtLeastAsDeepAs:
    def test_is_at_least_as_deep_as_with_no_depth_limit_against_a_depth_returns_true(self) -> None:
        #: Given
        scan_root = ScanRoot(DOCS, depth=None)
        other = ScanRoot(DOCS, depth=5)

        #: When
        at_least_as_deep = scan_root.is_at_least_as_deep_as(other)

        #: Then
        assert at_least_as_deep is True, 'no depth limit lists deeper than any depth'

    def test_is_at_least_as_deep_as_with_a_depth_against_no_depth_limit_returns_false(self) -> None:
        #: Given
        scan_root = ScanRoot(DOCS, depth=5)
        other = ScanRoot(DOCS, depth=None)

        #: When
        at_least_as_deep = scan_root.is_at_least_as_deep_as(other)

        #: Then
        assert at_least_as_deep is False, 'any depth stops short of a root with no limit'

    def test_is_at_least_as_deep_as_with_no_depth_limit_on_both_returns_true(self) -> None:
        #: Given
        scan_root = ScanRoot(DOCS, depth=None)
        other = ScanRoot(DOCS, depth=None)

        #: When
        at_least_as_deep = scan_root.is_at_least_as_deep_as(other)

        #: Then
        assert at_least_as_deep is True, (
            'two roots with no limit reach equally deep, which ends a scan led back by a link'
        )

    def test_is_at_least_as_deep_as_with_an_equal_depth_returns_true(self) -> None:
        #: Given
        scan_root = ScanRoot(DOCS, depth=1)
        other = ScanRoot(DOCS, depth=1)

        #: When
        at_least_as_deep = scan_root.is_at_least_as_deep_as(other)

        #: Then
        assert at_least_as_deep is True, 'an equal depth lists the same levels'

    def test_is_at_least_as_deep_as_with_a_shallower_depth_returns_false(self) -> None:
        #: Given
        scan_root = ScanRoot(DOCS, depth=1)
        other = ScanRoot(DOCS, depth=2)

        #: When
        at_least_as_deep = scan_root.is_at_least_as_deep_as(other)

        #: Then
        assert at_least_as_deep is False, 'depth 1 stops a level short of depth 2'
