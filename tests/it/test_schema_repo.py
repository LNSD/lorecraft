"""Schema repository behavior against real specification files.

The repository is wired to a real ``DiskFileSystem`` over ``tmp_path`` with the specification directory at the
root, so every path it returns is the bare filename.
"""

import os
from collections.abc import Iterator
from pathlib import Path
from typing import Final

import pytest

from lorecraft.core.path import RootRelativePath
from lorecraft.project.aspect import AspectNamespace
from lorecraft.project.corpus import CorpusName
from lorecraft.project.schemas import (
    CorpusSchemasListError,
    Repository,
    SchemaName,
    SpecAspect,
    SpecFile,
    StructureSchemaReadError,
)
from lorecraft.vfs import DirListError, DiskFileSystem

CODE: Final[CorpusName] = CorpusName.parse('code')
CODE_PYTHON: Final[SchemaName] = (CODE, AspectNamespace.parse('python'))


@pytest.fixture(scope='function')
def repository(tmp_path: Path) -> Repository:
    """A repository whose specification directory is the temporary root itself."""
    return Repository(DiskFileSystem(tmp_path), RootRelativePath.parse(''))


@pytest.fixture(scope='function')
def locked_repository(tmp_path: Path) -> Iterator[Repository]:
    """A repository over a directory whose permissions refuse listing, restored afterwards for cleanup."""
    directory = tmp_path / 'locked'
    directory.mkdir()
    directory.chmod(0o000)
    yield Repository(DiskFileSystem(tmp_path), RootRelativePath.parse('locked'))
    directory.chmod(0o700)


@pytest.mark.it
class TestRepositoryListSpecs:
    def test_list_spec_paths_with_files_of_every_kind_returns_every_regular_file_sorted_by_name(
        self, tmp_path: Path, repository: Repository
    ) -> None:
        #: Given
        for filename in ('notes.txt', 'code.header.json', 'x.spec.json', 'code.md', 'README.md'):
            (tmp_path / filename).write_text('{}', encoding='utf-8')

        #: When
        paths = repository.list_spec_paths()

        #: Then
        assert paths == [
            RootRelativePath.parse('README.md'),
            RootRelativePath.parse('code.header.json'),
            RootRelativePath.parse('code.md'),
            RootRelativePath.parse('notes.txt'),
            RootRelativePath.parse('x.spec.json'),
        ], 'the listing parses nothing: every regular file is listed, whatever its name'

    def test_list_spec_paths_with_a_subdirectory_does_not_list_it(self, tmp_path: Path, repository: Repository) -> None:
        #: Given
        (tmp_path / 'drafts.md').mkdir()

        #: When
        paths = repository.list_spec_paths()

        #: Then
        assert paths == [], 'only regular files are specification files'

    def test_list_spec_paths_with_missing_directory_returns_empty(self, tmp_path: Path) -> None:
        #: Given
        repository = Repository(DiskFileSystem(tmp_path), RootRelativePath.parse('missing'))

        #: When
        paths = repository.list_spec_paths()

        #: Then
        assert paths == [], 'a missing directory holds no specifications'

    @pytest.mark.skipif(os.geteuid() == 0, reason='root ignores directory permissions')
    def test_list_spec_paths_with_unreadable_directory_raises_list_dir_error(
        self, locked_repository: Repository
    ) -> None:
        #: Given
        repository = locked_repository

        #: When
        with pytest.raises(DirListError) as exc_info:
            repository.list_spec_paths()

        #: Then
        assert str(exc_info.value.path) == 'locked', 'the listing failure passes through, naming the directory'


@pytest.mark.it
class TestRepository:
    def test_list_schemas_with_all_kinds_returns_the_parsed_json_files_sorted_by_name(
        self, tmp_path: Path, repository: Repository
    ) -> None:
        #: Given
        for filename in ('feat.structure.json', 'code.structure.json', 'code.header.json', 'README.md'):
            (tmp_path / filename).write_text('{}', encoding='utf-8')

        #: When
        schemas = repository.list_schemas()

        #: Then
        assert schemas == [
            SpecFile(RootRelativePath.parse('code.structure.json'), (CODE,), SpecAspect.STRUCTURE),
            SpecFile(RootRelativePath.parse('feat.structure.json'), (CorpusName.parse('feat'),), SpecAspect.STRUCTURE),
        ], 'every aspect is listed with its root-relative path; prose and a stale header file are not schemas'

    def test_list_schemas_with_misnamed_json_files_leaves_them_out(
        self, tmp_path: Path, repository: Repository
    ) -> None:
        #: Given
        for filename in ('code.headers.json', 'code.budget.json', 'README.header.json', 'feat.feature.header.json'):
            (tmp_path / filename).write_text('{}', encoding='utf-8')

        #: When
        schemas = repository.list_schemas()

        #: Then
        assert schemas == [], 'a file whose name does not parse is not a schema'

    def test_list_schemas_by_corpus_excludes_other_corpora(self, tmp_path: Path, repository: Repository) -> None:
        #: Given
        for filename in (
            'code.structure.json',
            'code-python.structure.json',
            'code.component.structure.json',
            'codebook.structure.json',
        ):
            (tmp_path / filename).write_text('{}', encoding='utf-8')

        #: When
        schemas = repository.list_schemas_by_corpus(CODE)

        #: Then
        assert schemas == [
            SpecFile(RootRelativePath.parse('code-python.structure.json'), CODE_PYTHON, SpecAspect.STRUCTURE),
            SpecFile(RootRelativePath.parse('code.structure.json'), (CODE,), SpecAspect.STRUCTURE),
        ], 'the corpus is read from the parsed stem, so codebook is another corpus and a dotted stem is none'

    def test_get_structure_schema_with_namespace_reads_the_structure_file_text(
        self, tmp_path: Path, repository: Repository
    ) -> None:
        #: Given
        (tmp_path / 'code-python.structure.json').write_text('{"title": "Python"}', encoding='utf-8')
        name = CODE_PYTHON

        #: When
        schema = repository.get_structure_schema(name)

        #: Then
        assert schema == '{"title": "Python"}', (
            'get_structure_schema reads code-python.structure.json, leaving the parse to StructureAspect'
        )

    def test_get_structure_schema_with_missing_file_raises_structure_schema_read_error(
        self, repository: Repository
    ) -> None:
        #: Given
        name: SchemaName = (CODE,)

        #: When
        with pytest.raises(StructureSchemaReadError) as exc_info:
            repository.get_structure_schema(name)

        #: Then
        assert exc_info.value.name == name, (
            'the error names the schema; the repository fails only on a file it cannot read, malformed JSON is the '
            "parse's to refuse"
        )

    def test_list_schemas_with_missing_directory_returns_empty(self, tmp_path: Path) -> None:
        #: Given
        repository = Repository(DiskFileSystem(tmp_path), RootRelativePath.parse('missing'))

        #: When
        schemas = repository.list_schemas()

        #: Then
        assert schemas == [], 'a missing directory holds no schemas'

    @pytest.mark.skipif(os.geteuid() == 0, reason='root ignores directory permissions')
    def test_list_schemas_with_unreadable_directory_raises_list_dir_error(self, locked_repository: Repository) -> None:
        #: Given
        repository = locked_repository

        #: When
        with pytest.raises(DirListError) as exc_info:
            repository.list_schemas()

        #: Then
        assert str(exc_info.value.path) == 'locked', 'the listing failure passes through, naming the directory'

    @pytest.mark.skipif(os.geteuid() == 0, reason='root ignores directory permissions')
    def test_list_schemas_by_corpus_with_unreadable_directory_raises_corpus_list_error(
        self, locked_repository: Repository
    ) -> None:
        #: Given
        repository = locked_repository
        corpus = CODE

        #: When
        with pytest.raises(CorpusSchemasListError) as exc_info:
            repository.list_schemas_by_corpus(corpus)

        #: Then
        assert exc_info.value.corpus == corpus, 'the error names the corpus whose schemas were being listed'
        assert str(exc_info.value.source.path) == 'locked', 'its source names the directory that refused listing'
