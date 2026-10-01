"""The one join from a root-relative path onto a disk root, and the scan scope record's one invariant."""

from pathlib import Path

import pytest

from lorecraft.core.path import RootRelativePath

from ..disk import ScanRoot, disk_location


@pytest.mark.unit
class TestDiskLocation:
    def test_disk_location_of_a_path_returns_the_location_below_the_root(self, tmp_path: Path) -> None:
        #: Given
        path = RootRelativePath.parse('docs/code/a.md')

        #: When
        location = disk_location(tmp_path, path)

        #: Then
        assert location == tmp_path / 'docs' / 'code' / 'a.md', 'the path is joined onto the root, never replacing it'

    def test_disk_location_of_the_root_returns_the_disk_root(self, tmp_path: Path) -> None:
        #: Given
        root = RootRelativePath.parse('.')

        #: When
        location = disk_location(tmp_path, root)

        #: Then
        assert location == tmp_path, 'the root-relative root is the disk root itself'


@pytest.mark.unit
class TestScanRoot:
    def test_construct_with_a_negative_depth_raises_value_error(self) -> None:
        #: Given
        directory = RootRelativePath.parse('docs')
        depth = -1

        #: When
        with pytest.raises(ValueError) as exc_info:
            ScanRoot(directory, depth=depth)

        #: Then
        assert exc_info.type is ValueError, 'a negative depth, which would list nothing, is a value error'
        assert str(depth) in str(exc_info.value), 'the message names the rejected depth'
