"""One scan root: what it lists by the spelling of a path alone, and the depth it refuses.

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
