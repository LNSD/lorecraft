"""Establishing the workspace root: discovery upward from a start directory, and an explicit root."""

from pathlib import Path

import pytest

from ..root import InvalidRootError, RootError, RootNotFoundError, find_root, resolve_root


@pytest.mark.unit
class TestFindRoot:
    def test_find_root_with_marker_in_a_parent_returns_that_parent(self, tmp_path: Path) -> None:
        #: Given
        (tmp_path / 'docs' / '__meta__').mkdir(parents=True)
        start = tmp_path / 'src' / 'nested'
        start.mkdir(parents=True)

        #: When
        root = find_root(start)

        #: Then
        assert root == tmp_path.resolve(), 'the nearest parent holding docs/__meta__/ is the root'

    def test_find_root_with_marker_in_the_start_directory_returns_it(self, tmp_path: Path) -> None:
        #: Given
        (tmp_path / 'docs' / '__meta__').mkdir(parents=True)
        start = tmp_path

        #: When
        root = find_root(start)

        #: Then
        assert root == tmp_path.resolve(), 'the start directory itself is checked first'

    def test_find_root_with_relative_start_climbs_above_the_working_directory(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        #: Given
        (tmp_path / 'docs' / '__meta__').mkdir(parents=True)
        working_directory = tmp_path / 'src' / 'nested'
        working_directory.mkdir(parents=True)
        monkeypatch.chdir(working_directory)
        start = Path('.')

        #: When
        root = find_root(start)

        #: Then
        assert root == tmp_path.resolve(), 'a relative start is resolved before the search climbs its parents'

    def test_find_root_without_a_marker_raises_root_not_found_error(self, tmp_path: Path) -> None:
        #: Given
        start = tmp_path / 'src'
        start.mkdir()

        #: When
        with pytest.raises(RootNotFoundError) as exc_info:
            find_root(start)

        #: Then
        assert isinstance(exc_info.value, RootError), 'the error belongs to the root family'
        assert exc_info.value.start == start, 'the error retains where the search began'


@pytest.mark.unit
class TestResolveRoot:
    def test_resolve_root_with_missing_directory_raises_invalid_root_error(self, tmp_path: Path) -> None:
        #: Given
        path = tmp_path / 'missing'

        #: When
        with pytest.raises(InvalidRootError) as exc_info:
            resolve_root(path)

        #: Then
        assert isinstance(exc_info.value, RootError), 'the error belongs to the root family'
        assert exc_info.value.path == path.resolve(), 'the error identifies the rejected directory'

    def test_resolve_root_with_a_file_raises_invalid_root_error(self, tmp_path: Path) -> None:
        #: Given
        path = tmp_path / 'file.txt'
        path.write_text('', encoding='utf-8')

        #: When
        with pytest.raises(InvalidRootError) as exc_info:
            resolve_root(path)

        #: Then
        assert exc_info.value.path == path.resolve(), 'a file is not a root'

    def test_resolve_root_with_parent_segment_returns_absolute_directory(self, tmp_path: Path) -> None:
        #: Given
        nested = tmp_path / 'nested'
        nested.mkdir()
        path = nested / '..'

        #: When
        resolved = resolve_root(path)

        #: Then
        assert resolved == tmp_path.resolve(), 'resolution removes parent segments from an existing directory'
