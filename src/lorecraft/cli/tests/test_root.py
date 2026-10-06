"""Establishing the workspace root: discovery upward from a start directory, an explicit root, and either."""

import os
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from lorecraft.core.error import Error
from lorecraft.vfs import OsRefusal

from ..root import (
    InvalidRootError,
    RootCandidateInspectError,
    RootInspectError,
    RootNotFoundError,
    WorkingDirectoryReadError,
    establish_root,
    get_root,
    resolve_root,
)


@pytest.fixture(scope='function')
def directory_under_a_locked_parent(tmp_path: Path) -> Iterator[Path]:
    """A directory whose parent refuses search, so nothing below it can be inspected; unlocked afterwards.

    Args:
        tmp_path: The test's temporary directory, under which the locked parent is created.
    """
    locked = tmp_path / 'locked'
    directory = locked / 'sub'
    directory.mkdir(parents=True)
    locked.chmod(0o000)
    yield directory
    locked.chmod(0o700)


@pytest.mark.unit
class TestGetRoot:
    def test_get_root_with_marker_in_a_parent_returns_that_parent(self, tmp_path: Path) -> None:
        #: Given
        (tmp_path / 'docs' / '__meta__').mkdir(parents=True)
        start = tmp_path / 'src' / 'nested'
        start.mkdir(parents=True)

        #: When
        root = get_root(start)

        #: Then
        assert root == tmp_path.resolve(), 'the nearest parent holding docs/__meta__/ is the root'

    def test_get_root_with_marker_in_the_start_directory_returns_it(self, tmp_path: Path) -> None:
        #: Given
        (tmp_path / 'docs' / '__meta__').mkdir(parents=True)
        start = tmp_path

        #: When
        root = get_root(start)

        #: Then
        assert root == tmp_path.resolve(), 'the start directory itself is checked first'

    def test_get_root_with_relative_start_climbs_above_the_working_directory(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        #: Given
        (tmp_path / 'docs' / '__meta__').mkdir(parents=True)
        working_directory = tmp_path / 'src' / 'nested'
        working_directory.mkdir(parents=True)
        monkeypatch.chdir(working_directory)
        start = Path('.')

        #: When
        root = get_root(start)

        #: Then
        assert root == tmp_path.resolve(), 'a relative start is resolved before the search climbs its parents'

    def test_get_root_without_a_marker_raises_root_not_found_error(self, tmp_path: Path) -> None:
        #: Given
        start = tmp_path / 'src'
        start.mkdir()

        #: When
        with pytest.raises(RootNotFoundError) as exc_info:
            get_root(start)

        #: Then
        assert type(exc_info.value).__bases__ == (Error,), 'the variant derives from Error directly, not a family'
        assert exc_info.value.start == start, 'the error retains where the search began'

    @pytest.mark.skipif(os.geteuid() == 0, reason='root ignores directory permissions')
    @pytest.mark.skipif(sys.version_info >= (3, 14), reason="Python 3.14's is_dir answers False for every failure")
    def test_get_root_with_a_start_under_a_locked_parent_raises_root_candidate_inspect_error(
        self, directory_under_a_locked_parent: Path
    ) -> None:
        #: Given
        start = directory_under_a_locked_parent

        #: When
        with pytest.raises(RootCandidateInspectError) as exc_info:
            get_root(start)

        #: Then
        assert type(exc_info.value).__bases__ == (Error,), 'the variant derives from Error directly, not a family'
        assert exc_info.value.candidate == start.resolve(), 'the error names the first directory it could not inspect'
        assert exc_info.value.refusal is OsRefusal.PERMISSION_DENIED, 'a locked parent is a refused permission'
        assert isinstance(exc_info.value.source, PermissionError), 'the error keeps the operating system failure'
        assert exc_info.value.__cause__ is exc_info.value.source, 'the operating system failure is the cause'


@pytest.mark.unit
class TestResolveRoot:
    def test_resolve_root_with_missing_directory_raises_invalid_root_error(self, tmp_path: Path) -> None:
        #: Given
        path = tmp_path / 'missing'

        #: When
        with pytest.raises(InvalidRootError) as exc_info:
            resolve_root(path)

        #: Then
        assert type(exc_info.value).__bases__ == (Error,), 'the variant derives from Error directly, not a family'
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

    @pytest.mark.skipif(os.geteuid() == 0, reason='root ignores directory permissions')
    @pytest.mark.skipif(sys.version_info >= (3, 14), reason="Python 3.14's is_dir answers False for every failure")
    def test_resolve_root_with_a_directory_under_a_locked_parent_raises_root_inspect_error(
        self, directory_under_a_locked_parent: Path
    ) -> None:
        #: Given
        path = directory_under_a_locked_parent

        #: When
        with pytest.raises(RootInspectError) as exc_info:
            resolve_root(path)

        #: Then
        assert type(exc_info.value).__bases__ == (Error,), 'the variant derives from Error directly, not a family'
        assert exc_info.value.path == path.resolve(), 'the error identifies the root it could not inspect'
        assert exc_info.value.refusal is OsRefusal.PERMISSION_DENIED, 'a locked parent is a refused permission'
        assert isinstance(exc_info.value.source, PermissionError), 'the error keeps the operating system failure'
        assert exc_info.value.__cause__ is exc_info.value.source, 'the operating system failure is the cause'


@pytest.mark.unit
class TestEstablishRoot:
    def test_establish_root_with_a_root_given_returns_it_resolved(self, tmp_path: Path) -> None:
        #: Given
        nested = tmp_path / 'nested'
        nested.mkdir()

        #: When
        root = establish_root(nested / '..')

        #: Then
        assert root == tmp_path.resolve(), 'a given root is resolved, whatever the working directory holds'

    def test_establish_root_without_a_root_returns_the_nearest_parent_holding_the_specs(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        #: Given
        (tmp_path / 'docs' / '__meta__').mkdir(parents=True)
        start = tmp_path / 'docs' / 'code'
        start.mkdir()
        monkeypatch.chdir(start)

        #: When
        root = establish_root(None)

        #: Then
        assert root == tmp_path.resolve(), 'without a root, the search climbs from the working directory'

    def test_establish_root_without_a_root_from_a_deleted_working_directory_raises_working_directory_read_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        #: Given
        deleted = tmp_path / 'deleted'
        deleted.mkdir()
        monkeypatch.chdir(deleted)
        deleted.rmdir()

        #: When
        with pytest.raises(WorkingDirectoryReadError) as exc_info:
            establish_root(None)

        #: Then
        assert type(exc_info.value).__bases__ == (Error,), 'the variant derives from Error directly, not a family'
        assert exc_info.value.refusal is OsRefusal.NOT_FOUND, 'a deleted working directory is refused as not found'
        assert isinstance(exc_info.value.source, FileNotFoundError), 'the operating system failure is kept'
        assert exc_info.value.__cause__ is exc_info.value.source, 'the operating system failure is the cause'
