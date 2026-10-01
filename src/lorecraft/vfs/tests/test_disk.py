"""The one join from a root-relative path onto a disk root."""

from pathlib import Path

import pytest

from lorecraft.core.path import RootRelativePath

from ..disk import disk_location


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
