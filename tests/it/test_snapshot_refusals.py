"""What a scan keeps of the operating system's refusals when it is given a declaration, and what the view answers.

A scan with no declaration stops at the first refusal, and `test_filesystem` holds those. With one, a refusal on
what the declaration names is kept in the snapshot, and `VirtualFileSystem` answers for that path with a recorded
error where the disk view raises its own. Each test locks one path of a real tree, so the operating system refuses
it. The command tests at the end hold what `lorecraft check` does with a refusal the model does not report.
"""

import os
from collections.abc import Callable
from pathlib import Path
from typing import Final

import pytest
from typer.testing import CliRunner

from lorecraft.cli import build_app
from lorecraft.core.num import UnsignedInt
from lorecraft.core.path import RootRelativePath
from lorecraft.vfs import (
    Declaration,
    DirListError,
    DirResolveError,
    DiskFileSystem,
    FileReadError,
    FileResolveError,
    OsRefusal,
    RecordedDirListError,
    RecordedDirListPathError,
    RecordedDirResolveError,
    RecordedFileReadError,
    RecordedFileReadPathError,
    RecordedFileResolveError,
    RefusedInspect,
    RefusedListing,
    RefusedRead,
    ScanRoot,
    SnapshotDirListError,
    SnapshotFileReadError,
    SnapshotLinkReadError,
    VirtualFileSystem,
    take_snapshot,
)

SCOPE: Final[tuple[ScanRoot, ...]] = (
    ScanRoot(RootRelativePath.parse('docs'), depth=UnsignedInt(1)),
    ScanRoot(RootRelativePath.parse('.agents/skills'), depth=None, follow_links=True),
)
"""A shape of the layout's: `docs/` one level down, links left alone, and skills at any depth, links followed."""


def _is_structure_file(path: RootRelativePath) -> bool:
    """Whether `path` names a structure file; the root has no name, so it is none.

    Args:
        path: The root-relative path to test; only its final filename is checked, and the root is excluded.
    """
    name = path.name
    return name is not None and name.value.endswith('.structure.json')


DECLARATION: Final[Declaration] = Declaration(is_file=_is_structure_file)
"""Names the structure files, as the layout does, and nothing else."""

runner = CliRunner()


def _path(text: str) -> RootRelativePath:
    """The root-relative path spelled `text`.

    Args:
        text: A root-relative path, such as `docs/code`.
    """
    return RootRelativePath.parse(text)


@pytest.fixture(scope='function')
def tree(tmp_path: Path) -> Path:
    """A repository with a structure file, a document, a skill, and a skill that links its `SKILL.md`."""
    files = {
        'docs/__meta__/code.structure.json': '{"tokens": 4000}',
        'docs/code/logging.md': '# Logging\n',
        '.agents/skills/commit/SKILL.md': '---\nname: commit\ndescription: Write a commit message\n---\n\n# Commit\n',
        '.agents/skills/commit/references/guide.md': '# Guide\n',
        'texts/REVIEW.md': '---\nname: review\ndescription: Review a change\n---\n\n# Review\n',
    }
    for relative, text in files.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
    (tmp_path / '.agents' / 'skills' / 'review').mkdir()
    (tmp_path / '.agents' / 'skills' / 'review' / 'SKILL.md').symlink_to('../../../texts/REVIEW.md')
    return tmp_path


@pytest.mark.it
@pytest.mark.skipif(os.geteuid() == 0, reason='root ignores file and directory permissions')
class TestSnapshotWithADeclaration:
    def test_take_snapshot_with_a_corpus_directory_that_cannot_be_listed_keeps_the_refusal(
        self, tree: Path, lock: Callable[[Path], None]
    ) -> None:
        #: Given
        lock(tree / 'docs' / 'code')

        #: When
        snapshot = take_snapshot(tree, SCOPE, declaration=DECLARATION)

        #: Then
        assert snapshot.records[_path('docs/code')] == RefusedListing(OsRefusal.PERMISSION_DENIED), (
            'the listing is what was refused, and the refusal is classified from the errno'
        )
        assert _path('docs/code/logging.md') not in snapshot.records, 'nothing is known of what it holds'

    def test_take_snapshot_with_a_structure_file_that_cannot_be_read_keeps_the_refusal(
        self, tree: Path, lock: Callable[[Path], None]
    ) -> None:
        #: Given
        lock(tree / 'docs' / '__meta__' / 'code.structure.json')

        #: When
        snapshot = take_snapshot(tree, SCOPE, declaration=DECLARATION)

        #: Then
        assert snapshot.records[_path('docs/__meta__/code.structure.json')] == RefusedRead(OsRefusal.PERMISSION_DENIED)
        assert _path('docs/code/logging.md') in snapshot.records, 'the scan went on past the file'

    def test_take_snapshot_with_a_link_whose_chain_cannot_be_inspected_keeps_the_refusal(
        self, tree: Path, lock: Callable[[Path], None]
    ) -> None:
        #: Given
        lock(tree / 'texts')

        #: When
        snapshot = take_snapshot(tree, SCOPE, declaration=DECLARATION)

        #: Then
        assert snapshot.records[_path('texts/REVIEW.md')] == RefusedInspect(OsRefusal.PERMISSION_DENIED), (
            'the entry the chain stopped at is what was refused'
        )

    def test_take_snapshot_with_a_link_to_a_declared_file_that_cannot_be_read_keeps_the_refusal(
        self, tree: Path, lock: Callable[[Path], None]
    ) -> None:
        #: Given
        lock(tree / 'texts' / 'REVIEW.md')
        declaration = Declaration(is_file=lambda path: path == _path('texts/REVIEW.md'))

        #: When
        snapshot = take_snapshot(tree, SCOPE, declaration=declaration)

        #: Then
        assert snapshot.records[_path('texts/REVIEW.md')] == RefusedRead(OsRefusal.PERMISSION_DENIED), (
            'the file the link leads to is what was refused'
        )
        assert _path('.agents/skills/commit/SKILL.md') in snapshot.records, 'the scan went on past the file'

    def test_take_snapshot_with_a_link_to_an_undeclared_file_that_cannot_be_read_still_stops(
        self, tree: Path, lock: Callable[[Path], None]
    ) -> None:
        #: Given
        lock(tree / 'texts' / 'REVIEW.md')

        #: When
        with pytest.raises(SnapshotFileReadError) as exc_info:
            take_snapshot(tree, SCOPE, declaration=DECLARATION)

        #: Then
        assert exc_info.value.path == _path('texts/REVIEW.md'), 'a file the declaration does not name stops it'

    def test_take_snapshot_with_a_document_that_cannot_be_read_still_stops(
        self, tree: Path, lock: Callable[[Path], None]
    ) -> None:
        #: Given
        lock(tree / 'docs' / 'code' / 'logging.md')

        #: When
        with pytest.raises(SnapshotFileReadError) as exc_info:
            take_snapshot(tree, SCOPE, declaration=DECLARATION)

        #: Then
        assert exc_info.value.path == _path('docs/code/logging.md'), 'a file the declaration does not name stops it'

    def test_take_snapshot_with_a_link_whose_target_cannot_be_read_still_stops(self, tree: Path) -> None:
        #: Given
        links = tree / 'links'
        links.mkdir()
        (links / 'up.md').symlink_to('../texts/REVIEW.md')
        # Readable and not searchable: the names are listed, and no link in it can be read.
        links.chmod(0o444)
        scope = (ScanRoot(_path('links'), depth=UnsignedInt(0)),)

        #: When
        try:
            with pytest.raises(SnapshotLinkReadError) as exc_info:
                take_snapshot(tree, scope, declaration=DECLARATION)
        finally:
            links.chmod(0o755)

        #: Then
        assert exc_info.value.path == _path('links/up.md'), 'a link it cannot resolve stops it'

    def test_take_snapshot_with_no_declaration_still_stops_at_a_directory_that_cannot_be_listed(
        self, tree: Path, lock: Callable[[Path], None]
    ) -> None:
        #: Given
        lock(tree / 'docs' / 'code')

        #: When
        with pytest.raises(SnapshotDirListError) as exc_info:
            take_snapshot(tree, SCOPE)

        #: Then
        assert exc_info.value.path == _path('docs/code'), 'no declaration, no refusal is kept'

    def test_take_snapshot_with_nothing_refused_keeps_no_refusal(self, tree: Path) -> None:
        #: Given
        expected: dict[RootRelativePath, RefusedListing | RefusedRead | RefusedInspect] = {}

        #: When
        snapshot = take_snapshot(tree, SCOPE, declaration=DECLARATION)

        #: Then
        assert snapshot.refusals() == expected, 'a tree the operating system refuses nothing of holds none'


@pytest.mark.it
@pytest.mark.skipif(os.geteuid() == 0, reason='root ignores file and directory permissions')
class TestVirtualFileSystemOverARefusal:
    def test_list_dir_with_a_directory_the_scan_could_not_list_raises_a_recorded_error(
        self, tree: Path, lock: Callable[[Path], None]
    ) -> None:
        #: Given
        lock(tree / 'docs' / 'code')
        directory = _path('docs/code')
        virtual = VirtualFileSystem(take_snapshot(tree, SCOPE, declaration=DECLARATION))

        #: When
        with pytest.raises(RecordedDirListError) as exc_info:
            virtual.list_dir(directory)

        #: Then
        assert exc_info.value.path == directory, 'the error names the directory asked for'
        assert exc_info.value.refusal is OsRefusal.PERMISSION_DENIED, 'with the reason the disk gives'

    def test_list_dir_with_a_directory_the_operating_system_refuses_to_list_raises_dir_list_error(
        self, tree: Path, lock: Callable[[Path], None]
    ) -> None:
        #: Given
        lock(tree / 'docs' / 'code')
        disk = DiskFileSystem(tree)

        #: When
        with pytest.raises(DirListError) as exc_info:
            disk.list_dir(_path('docs/code'))

        #: Then
        assert exc_info.value.refusal is OsRefusal.PERMISSION_DENIED, 'the disk view refuses as the recorded one does'

    def test_list_dir_with_the_parent_of_a_refused_directory_lists_it_as_a_directory(
        self, tree: Path, lock: Callable[[Path], None]
    ) -> None:
        #: Given
        lock(tree / 'docs' / 'code')
        virtual = VirtualFileSystem(take_snapshot(tree, SCOPE, declaration=DECLARATION))

        #: When
        names = [str(entry.name) for entry in virtual.list_dir(_path('docs'))]

        #: Then
        assert names == ['__meta__', 'code'], 'the directory it could not list is still an entry of its parent'

    def test_read_text_with_a_structure_file_the_scan_could_not_read_raises_a_recorded_error(
        self, tree: Path, lock: Callable[[Path], None]
    ) -> None:
        #: Given
        lock(tree / 'docs' / '__meta__' / 'code.structure.json')
        file = _path('docs/__meta__/code.structure.json')
        virtual = VirtualFileSystem(take_snapshot(tree, SCOPE, declaration=DECLARATION))

        #: When
        with pytest.raises(RecordedFileReadError) as exc_info:
            virtual.read_text(file)

        #: Then
        assert exc_info.value.path == file, 'the error names the file asked for'
        assert exc_info.value.refusal is OsRefusal.PERMISSION_DENIED, 'with the reason the disk gives'

    def test_read_text_with_a_file_the_operating_system_refuses_to_read_raises_file_read_error(
        self, tree: Path, lock: Callable[[Path], None]
    ) -> None:
        #: Given
        lock(tree / 'docs' / '__meta__' / 'code.structure.json')
        disk = DiskFileSystem(tree)

        #: When
        with pytest.raises(FileReadError) as exc_info:
            disk.read_text(_path('docs/__meta__/code.structure.json'))

        #: Then
        assert exc_info.value.refusal is OsRefusal.PERMISSION_DENIED, 'the disk view refuses as the recorded one does'

    def test_list_dir_with_the_directory_of_a_refused_file_still_lists_it(
        self, tree: Path, lock: Callable[[Path], None]
    ) -> None:
        #: Given
        lock(tree / 'docs' / '__meta__' / 'code.structure.json')
        virtual = VirtualFileSystem(take_snapshot(tree, SCOPE, declaration=DECLARATION))

        #: When
        names = [str(entry.name) for entry in virtual.list_dir(_path('docs/__meta__'))]

        #: Then
        assert names == ['code.structure.json'], 'the file it could not read is still an entry of its directory'

    def test_find_file_with_a_link_whose_chain_the_scan_could_not_inspect_raises_a_recorded_error(
        self, tree: Path, lock: Callable[[Path], None]
    ) -> None:
        #: Given
        lock(tree / 'texts')
        link = _path('.agents/skills/review/SKILL.md')
        virtual = VirtualFileSystem(take_snapshot(tree, SCOPE, declaration=DECLARATION))

        #: When
        with pytest.raises(RecordedFileResolveError) as exc_info:
            virtual.find_file(link)

        #: Then
        assert exc_info.value.path == link, 'the error names the link asked for'
        assert exc_info.value.refusal is OsRefusal.PERMISSION_DENIED, 'with the reason the disk gives'
        assert exc_info.value.source.path == _path('texts/REVIEW.md'), 'the cause names the entry it stopped at'

    def test_find_file_with_a_link_the_operating_system_refuses_to_follow_raises_file_resolve_error(
        self, tree: Path, lock: Callable[[Path], None]
    ) -> None:
        #: Given
        lock(tree / 'texts')
        disk = DiskFileSystem(tree)

        #: When
        with pytest.raises(FileResolveError) as exc_info:
            disk.find_file(_path('.agents/skills/review/SKILL.md'))

        #: Then
        assert exc_info.value.refusal is OsRefusal.PERMISSION_DENIED, 'the disk view refuses as the recorded one does'

    def test_list_dir_with_a_chain_the_scan_could_not_inspect_raises_a_recorded_error_naming_the_entry(
        self, tree: Path, lock: Callable[[Path], None]
    ) -> None:
        #: Given
        (tree / '.agents' / 'skills' / 'texts').symlink_to('../../texts')
        lock(tree / 'texts')
        virtual = VirtualFileSystem(take_snapshot(tree, SCOPE, declaration=DECLARATION))

        #: When
        with pytest.raises(RecordedDirListPathError) as exc_info:
            virtual.list_dir(_path('.agents/skills/texts/REVIEW.md'))

        #: Then
        assert exc_info.value.source.path == _path('texts/REVIEW.md'), 'the cause names the entry it stopped at'

    def test_read_text_with_a_chain_the_scan_could_not_inspect_raises_a_recorded_error_naming_the_entry(
        self, tree: Path, lock: Callable[[Path], None]
    ) -> None:
        #: Given
        (tree / '.agents' / 'skills' / 'texts').symlink_to('../../texts')
        lock(tree / 'texts')
        virtual = VirtualFileSystem(take_snapshot(tree, SCOPE, declaration=DECLARATION))

        #: When
        with pytest.raises(RecordedFileReadPathError) as exc_info:
            virtual.read_text(_path('.agents/skills/texts/REVIEW.md'))

        #: Then
        assert exc_info.value.source.path == _path('texts/REVIEW.md'), 'the cause names the entry it stopped at'

    def test_find_dir_with_a_chain_the_scan_could_not_inspect_raises_a_recorded_error(
        self, tree: Path, lock: Callable[[Path], None]
    ) -> None:
        #: Given
        (tree / '.agents' / 'skills' / 'texts').symlink_to('../../texts')
        lock(tree / 'texts')
        path = _path('.agents/skills/texts/REVIEW.md')
        virtual = VirtualFileSystem(take_snapshot(tree, SCOPE, declaration=DECLARATION))

        #: When
        with pytest.raises(RecordedDirResolveError) as exc_info:
            virtual.find_dir(path)

        #: Then
        assert exc_info.value.refusal is OsRefusal.PERMISSION_DENIED, 'the lookup is refused with the reason given'

    def test_find_dir_with_a_chain_the_operating_system_refuses_to_search_raises_dir_resolve_error(
        self, tree: Path, lock: Callable[[Path], None]
    ) -> None:
        #: Given
        (tree / '.agents' / 'skills' / 'texts').symlink_to('../../texts')
        lock(tree / 'texts')
        disk = DiskFileSystem(tree)

        #: When
        with pytest.raises(DirResolveError) as exc_info:
            disk.find_dir(_path('.agents/skills/texts/REVIEW.md'))

        #: Then
        assert exc_info.value.refusal is OsRefusal.PERMISSION_DENIED, 'the disk view refuses as the recorded one does'

    def test_find_dir_with_a_directory_that_can_be_reached_resolves_it(self, tree: Path) -> None:
        #: Given
        virtual = VirtualFileSystem(take_snapshot(tree, SCOPE, declaration=DECLARATION))

        #: When
        resolved = virtual.find_dir(_path('docs/code'))

        #: Then
        assert resolved == _path('docs/code'), 'a snapshot that kept no refusal answers as it always did'


@pytest.mark.it
@pytest.mark.skipif(os.geteuid() == 0, reason='root ignores file and directory permissions')
class TestCheckOverARefusalNoLoadFailureReports:
    def test_check_with_a_directory_under_docs_no_meta_spec_names_exits_two_and_names_it(
        self, tree: Path, lock: Callable[[Path], None]
    ) -> None:
        #: Given
        (tree / 'docs' / 'notes').mkdir()
        (tree / 'docs' / 'notes' / 'a.md').write_text('# A\n', encoding='utf-8')
        lock(tree / 'docs' / 'notes')

        #: When
        result = runner.invoke(build_app(), ['check', '--root', str(tree)])

        #: Then
        assert result.exit_code == 2, result.output
        assert result.stderr == 'error: cannot snapshot directory docs/notes: permission denied\n', (
            'a directory nothing governs stops the run as it did before the snapshot kept refusals'
        )

    def test_check_with_a_directory_inside_a_skill_that_cannot_be_listed_exits_two_and_names_it(
        self, tree: Path, lock: Callable[[Path], None]
    ) -> None:
        #: Given
        lock(tree / '.agents' / 'skills' / 'commit' / 'references')

        #: When
        result = runner.invoke(build_app(), ['check', '--root', str(tree)])

        #: Then
        assert result.exit_code == 2, result.output
        assert result.stderr == (
            'error: cannot snapshot directory .agents/skills/commit/references: permission denied\n'
        ), 'a directory inside a skill that nothing reports stops the run as it did before'

    def test_check_with_a_corpus_directory_that_cannot_be_listed_exits_one(
        self, tree: Path, lock: Callable[[Path], None]
    ) -> None:
        #: Given
        lock(tree / 'docs' / 'code')

        #: When
        result = runner.invoke(build_app(), ['check', '--root', str(tree), '--format', 'short'])

        #: Then
        assert result.exit_code == 1, result.output
        assert result.stdout == 'docs/code: error[LC002]: path cannot be read\n', 'the corpus directory is reported'

    def test_check_with_a_reported_and_an_unreported_directory_both_locked_exits_two_naming_the_unreported(
        self, tree: Path, lock: Callable[[Path], None]
    ) -> None:
        #: Given
        (tree / 'docs' / 'aaa').mkdir()
        (tree / 'docs' / 'aaa' / 'a.md').write_text('# A\n', encoding='utf-8')
        lock(tree / 'docs' / 'aaa')
        lock(tree / 'docs' / 'code')

        #: When
        result = runner.invoke(build_app(), ['check', '--root', str(tree)])

        #: Then
        assert result.exit_code == 2, result.output
        assert result.stderr == 'error: cannot snapshot directory docs/aaa: permission denied\n', (
            'the directory the model reports is not the one the run stops at'
        )

    def test_check_with_a_reported_link_and_an_unreported_link_into_locked_directories_exits_two_naming_the_second(
        self, tree: Path, lock: Callable[[Path], None]
    ) -> None:
        #: Given
        (tree / 'locked').mkdir()
        (tree / '.agents' / 'skills' / 'commit' / 'references' / 'up.md').symlink_to('../../../../locked/x.md')
        lock(tree / 'texts')
        lock(tree / 'locked')

        #: When
        result = runner.invoke(build_app(), ['check', '--root', str(tree)])

        #: Then
        assert result.exit_code == 2, result.output
        assert result.stderr == 'error: cannot snapshot entry locked/x.md: permission denied\n', (
            'the link of a SKILL.md is reported, and the link inside a skill that nothing loads stops the run'
        )
