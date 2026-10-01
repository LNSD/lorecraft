"""Document repository behavior against a real ``docs/`` tree.

The repository is wired to a real ``DiskFileSystem`` over ``tmp_path``, so entry kinds come from ``os.scandir``
and the error families come from the operating system refusing a read. Every path it returns is
root-relative to ``tmp_path``.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from lorecraft.core.path import RootRelativePath
from lorecraft.project.aspect import AspectFilename
from lorecraft.project.corpus import CorpusName
from lorecraft.project.document.ref import DocumentRef
from lorecraft.project.document.repo import (
    CorpusListError,
    Document,
    DocumentDecodeError,
    DocumentFile,
    DocumentReadError,
    Repository,
)
from lorecraft.vfs import DirListError, DiskFileSystem, FileReadError, TextDecodeError


@pytest.fixture(scope='function')
def repository(tmp_path: Path) -> Repository:
    """A repository over the temporary root; `docs/` does not exist until a test creates it.

    Args:
        tmp_path: Directory the repository reads from, as the repository root.
    """
    return Repository(DiskFileSystem(tmp_path))


@pytest.fixture(scope='function')
def code_dir(tmp_path: Path) -> Path:
    """An empty `docs/code/` corpus directory under the temporary root.

    Args:
        tmp_path: Directory the corpus directory is created under, as the repository root.
    """
    directory = tmp_path / 'docs' / 'code'
    directory.mkdir(parents=True)
    return directory


@pytest.fixture(scope='function')
def locked_docs(tmp_path: Path) -> Iterator[Path]:
    """A `docs/` whose permissions refuse listing, restored afterwards so pytest can clean it up.

    Args:
        tmp_path: Directory the locked `docs/` is created under, as the repository root.
    """
    directory = tmp_path / 'docs'
    directory.mkdir()
    directory.chmod(0o000)
    yield directory
    directory.chmod(0o700)


@pytest.fixture(scope='function')
def locked_code_dir(code_dir: Path) -> Iterator[Path]:
    """A `docs/code/` whose permissions refuse listing, restored afterwards so pytest can clean it up.

    Args:
        code_dir: The corpus directory whose permissions are removed and later restored.
    """
    code_dir.chmod(0o000)
    yield code_dir
    code_dir.chmod(0o700)


@pytest.mark.it
class TestRepositoryListCorpusDirectories:
    def test_list_corpus_directories_with_directories_and_files_returns_only_directories(
        self, tmp_path: Path, repository: Repository
    ) -> None:
        #: Given
        (tmp_path / 'docs' / 'feat').mkdir(parents=True)
        (tmp_path / 'docs' / 'code').mkdir()
        (tmp_path / 'docs' / 'architecture.md').write_text('', encoding='utf-8')

        #: When
        directories = repository.list_corpus_directories()

        #: Then
        assert directories == ('code', 'feat'), (
            'directories are listed by name and a file directly under docs/ is dropped'
        )

    def test_list_corpus_directories_with_a_symlinked_directory_leaves_it_out(
        self, tmp_path: Path, repository: Repository
    ) -> None:
        #: Given
        (tmp_path / 'docs' / 'code').mkdir(parents=True)
        (tmp_path / 'docs' / 'rules').symlink_to(tmp_path / 'docs' / 'code')

        #: When
        directories = repository.list_corpus_directories()

        #: Then
        assert directories == ('code',), 'a symlinked directory is no corpus, whatever it leads to'

    def test_list_corpus_directories_with_no_docs_directory_returns_empty(
        self, tmp_path: Path, repository: Repository
    ) -> None:
        #: Given
        # nothing is created under the temporary root
        missing_docs = tmp_path / 'docs'

        #: When
        directories = repository.list_corpus_directories()

        #: Then
        assert not missing_docs.exists(), 'the case turns on docs/ being absent'
        assert directories == (), 'a root without docs/ has no corpora rather than failing'

    @pytest.mark.skipif(os.geteuid() == 0, reason='root ignores directory permissions')
    def test_list_corpus_directories_with_an_unreadable_docs_raises_list_dir_error(
        self, repository: Repository, locked_docs: Path
    ) -> None:
        #: Given
        locked = locked_docs

        #: When
        with pytest.raises(DirListError) as exc_info:
            repository.list_corpus_directories()

        #: Then
        assert str(exc_info.value.path) == locked.name, 'the listing failure passes through, naming docs/'


@pytest.mark.it
class TestRepositoryListDocuments:
    def test_list_documents_with_a_nested_directory_ignores_it(self, code_dir: Path, repository: Repository) -> None:
        #: Given
        (code_dir / 'logging.md').write_text('', encoding='utf-8')
        (code_dir / 'sub').mkdir()
        (code_dir / 'sub' / 'nested.md').write_text('', encoding='utf-8')
        corpus = CorpusName.parse('code')

        #: When
        documents = repository.list_documents(corpus)

        #: Then
        assert documents == (DocumentFile(RootRelativePath.parse('docs/code/logging.md'), 'logging'),), (
            'a subdirectory inside a corpus is not a document and is not descended into'
        )

    def test_list_documents_with_a_txt_file_ignores_it(self, code_dir: Path, repository: Repository) -> None:
        #: Given
        (code_dir / 'logging.md').write_text('', encoding='utf-8')
        (code_dir / 'notes.txt').write_text('', encoding='utf-8')
        corpus = CorpusName.parse('code')

        #: When
        documents = repository.list_documents(corpus)

        #: Then
        assert documents == (DocumentFile(RootRelativePath.parse('docs/code/logging.md'), 'logging'),), (
            'only .md entries are documents'
        )

    def test_list_documents_with_a_symlinked_document_leaves_it_out(
        self, code_dir: Path, repository: Repository
    ) -> None:
        #: Given
        (code_dir / 'logging.md').write_text('', encoding='utf-8')
        (code_dir / 'alias.md').symlink_to(code_dir / 'logging.md')
        corpus = CorpusName.parse('code')

        #: When
        documents = repository.list_documents(corpus)

        #: Then
        assert documents == (DocumentFile(RootRelativePath.parse('docs/code/logging.md'), 'logging'),), (
            'a symlinked .md is no document, whatever it leads to'
        )

    def test_list_documents_with_a_readme_returns_its_stem_unvalidated(
        self, code_dir: Path, repository: Repository
    ) -> None:
        #: Given
        (code_dir / 'README.md').write_text('', encoding='utf-8')
        corpus = CorpusName.parse('code')

        #: When
        documents = repository.list_documents(corpus)

        #: Then
        assert documents == (DocumentFile(RootRelativePath.parse('docs/code/README.md'), 'README'),), (
            'the stem is listed as spelled; whether it is a valid name is decided above the repository'
        )

    def test_list_documents_with_a_missing_corpus_directory_returns_empty(
        self, tmp_path: Path, repository: Repository
    ) -> None:
        #: Given
        (tmp_path / 'docs').mkdir()
        corpus = CorpusName.parse('feat')

        #: When
        documents = repository.list_documents(corpus)

        #: Then
        assert documents == (), 'a missing corpus directory lists as nothing rather than failing'

    @pytest.mark.skipif(os.geteuid() == 0, reason='root ignores directory permissions')
    def test_list_documents_with_an_unreadable_corpus_directory_raises_corpus_list_error(
        self, repository: Repository, locked_code_dir: Path
    ) -> None:
        #: Given
        corpus = CorpusName.parse(locked_code_dir.name)

        #: When
        with pytest.raises(CorpusListError) as exc_info:
            repository.list_documents(corpus)

        #: Then
        assert exc_info.value.corpus == corpus, 'the error names the corpus being listed'
        assert str(exc_info.value.source.path) == 'docs/code', 'its source is the listing of the corpus directory'
        assert str(corpus) in str(exc_info.value), 'the message names the corpus'


@pytest.mark.it
class TestRepositoryGetDocument:
    def test_get_document_with_a_utf8_file_returns_its_text(self, code_dir: Path, repository: Repository) -> None:
        #: Given
        (code_dir / 'logging.md').write_text('---\nname: "logging"\n---\n', encoding='utf-8')
        ref = DocumentRef(CorpusName.parse('code'), AspectFilename.parse('logging'))

        #: When
        document = repository.get_document(ref)

        #: Then
        assert document == Document(ref, '---\nname: "logging"\n---\n'), 'the document carries its ref and text'

    def test_get_document_with_a_missing_file_raises_document_read_error(
        self, code_dir: Path, repository: Repository
    ) -> None:
        #: Given
        ref = DocumentRef(CorpusName.parse('code'), AspectFilename.parse('missing'))

        #: When
        with pytest.raises(DocumentReadError) as exc_info:
            repository.get_document(ref)

        #: Then
        assert exc_info.value.ref == ref, 'the error names the document that could not be read'
        assert isinstance(exc_info.value.source, FileReadError), 'its source is the failed read'
        assert 'docs/code/missing.md' in str(exc_info.value), 'the message names the document'

    def test_get_document_with_non_utf8_bytes_raises_document_decode_error(
        self, code_dir: Path, repository: Repository
    ) -> None:
        #: Given
        (code_dir / 'latin.md').write_bytes(b'---\nname: "latin"\n---\n\xff\xfe\n')
        ref = DocumentRef(CorpusName.parse('code'), AspectFilename.parse('latin'))

        #: When
        with pytest.raises(DocumentDecodeError) as exc_info:
            repository.get_document(ref)

        #: Then
        assert exc_info.value.ref == ref, 'the error names the document that could not be decoded'
        assert isinstance(exc_info.value.source, TextDecodeError), 'its source is the failed decode'
        assert not isinstance(exc_info.value, DocumentReadError), 'a decode failure is a variant of its own'
        assert 'docs/code/latin.md' in str(exc_info.value), 'the message names the document'
