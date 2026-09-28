"""Explicit document selection against a loaded model over a real ``docs/`` tree.

The model is loaded from ``tmp_path`` through the disk view, and every argument is a real path,
so ``select_document`` resolves it the way the command line does. Each rule of the selection order has one
test asserting the reason it produces, never the message.
"""

from pathlib import Path

import pytest

from lorecraft.cli.select import DocumentPathError, DocumentPathProblem, select_document
from lorecraft_project.aspect import AspectFilename
from lorecraft_project.corpus import CorpusName, CorpusNameError
from lorecraft_project.document import DocumentRef
from lorecraft_project.workspace import WorkspaceModel, load_model
from lorecraft_vfs import DiskFileSystem


def _write(root: Path, relative: str, text: str = '') -> Path:
    """Write one file under the root, creating its parents, and return its path."""
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')
    return path


@pytest.fixture(scope='function')
def model(tmp_path: Path) -> WorkspaceModel:
    """A model over one corpus ``code`` holding ``logging.md`` and a misnamed ``README.md``.

    Beside the corpus sit the paths the rules reject: a nested file, a spec-less directory, an invalid
    corpus name, a file directly under ``docs/`` and a non-Markdown file.
    """
    _write(tmp_path, 'docs/__meta__/code.md')
    _write(tmp_path, 'docs/code/logging.md')
    _write(tmp_path, 'docs/code/README.md')
    _write(tmp_path, 'docs/code/notes.txt')
    _write(tmp_path, 'docs/code/sub/x.md')
    _write(tmp_path, 'docs/schemas/tables/x.md')
    _write(tmp_path, 'docs/bad-name/guide.md')
    _write(tmp_path, 'docs/architecture.md')
    return load_model(DiskFileSystem(tmp_path))


@pytest.mark.it
class TestSelectDocument:
    def test_select_document_with_a_listed_document_returns_its_ref(
        self, tmp_path: Path, model: WorkspaceModel
    ) -> None:
        #: Given
        argument = tmp_path / 'docs' / 'code' / 'logging.md'

        #: When
        ref = select_document(model, tmp_path, argument)

        #: Then
        assert ref == DocumentRef(CorpusName.parse('code'), AspectFilename.parse('logging')), (
            'the argument maps onto the ref the model lists'
        )

    def test_select_document_with_a_symlinked_argument_returns_the_target_ref(
        self, tmp_path: Path, model: WorkspaceModel
    ) -> None:
        #: Given
        alias = tmp_path / 'alias.md'
        alias.symlink_to(tmp_path / 'docs' / 'code' / 'logging.md')

        #: When
        ref = select_document(model, tmp_path, alias)

        #: Then
        assert ref == DocumentRef(CorpusName.parse('code'), AspectFilename.parse('logging')), (
            'symlinks are followed once, so the alias names its target'
        )

    def test_select_document_with_a_missing_file_raises_unreadable(self, tmp_path: Path, model: WorkspaceModel) -> None:
        #: Given
        argument = tmp_path / 'docs' / 'code' / 'missing.md'

        #: When
        with pytest.raises(DocumentPathError) as exc_info:
            select_document(model, tmp_path, argument)

        #: Then
        assert exc_info.value.reason is DocumentPathProblem.UNREADABLE, 'a path that does not resolve is unreadable'
        assert exc_info.value.argument == argument, 'the error quotes the argument as typed'

    def test_select_document_with_a_directory_raises_not_a_file(self, tmp_path: Path, model: WorkspaceModel) -> None:
        #: Given
        argument = tmp_path / 'docs' / 'code'

        #: When
        with pytest.raises(DocumentPathError) as exc_info:
            select_document(model, tmp_path, argument)

        #: Then
        assert exc_info.value.reason is DocumentPathProblem.NOT_A_FILE, 'a directory is not a document'

    def test_select_document_with_a_txt_file_raises_not_markdown(self, tmp_path: Path, model: WorkspaceModel) -> None:
        #: Given
        argument = tmp_path / 'docs' / 'code' / 'notes.txt'

        #: When
        with pytest.raises(DocumentPathError) as exc_info:
            select_document(model, tmp_path, argument)

        #: Then
        assert exc_info.value.reason is DocumentPathProblem.NOT_MARKDOWN, 'only .md files are documents'

    def test_select_document_with_a_specification_file_raises_outside_docs(
        self, tmp_path: Path, model: WorkspaceModel
    ) -> None:
        #: Given
        argument = tmp_path / 'docs' / '__meta__' / 'code.md'

        #: When
        with pytest.raises(DocumentPathError) as exc_info:
            select_document(model, tmp_path, argument)

        #: Then
        assert exc_info.value.reason is DocumentPathProblem.OUTSIDE_DOCS, 'docs/__meta__/ holds no documents'

    def test_select_document_with_a_file_outside_docs_raises_outside_docs(
        self, tmp_path: Path, model: WorkspaceModel
    ) -> None:
        #: Given
        argument = _write(tmp_path, 'README.md')

        #: When
        with pytest.raises(DocumentPathError) as exc_info:
            select_document(model, tmp_path, argument)

        #: Then
        assert exc_info.value.reason is DocumentPathProblem.OUTSIDE_DOCS, 'a file outside docs/ is no document'

    def test_select_document_with_a_file_directly_under_docs_raises_not_in_corpus(
        self, tmp_path: Path, model: WorkspaceModel
    ) -> None:
        #: Given
        argument = tmp_path / 'docs' / 'architecture.md'

        #: When
        with pytest.raises(DocumentPathError) as exc_info:
            select_document(model, tmp_path, argument)

        #: Then
        assert exc_info.value.reason is DocumentPathProblem.NOT_IN_CORPUS, 'a file directly under docs/ has no corpus'

    def test_select_document_with_an_invalid_corpus_name_raises_invalid_corpus_name(
        self, tmp_path: Path, model: WorkspaceModel
    ) -> None:
        #: Given
        argument = tmp_path / 'docs' / 'bad-name' / 'guide.md'

        #: When
        with pytest.raises(DocumentPathError) as exc_info:
            select_document(model, tmp_path, argument)

        #: Then
        assert exc_info.value.reason is DocumentPathProblem.INVALID_CORPUS_NAME, 'the first segment must parse'
        assert isinstance(exc_info.value.__cause__, CorpusNameError), 'the parser failure is chained as the cause'
        assert exc_info.value.detail != '', 'the parser message is carried as the detail'

    def test_select_document_with_a_nested_path_under_a_spec_less_directory_raises_not_a_corpus(
        self, tmp_path: Path, model: WorkspaceModel
    ) -> None:
        #: Given
        argument = tmp_path / 'docs' / 'schemas' / 'tables' / 'x.md'

        #: When
        with pytest.raises(DocumentPathError) as exc_info:
            select_document(model, tmp_path, argument)

        #: Then
        assert exc_info.value.reason is DocumentPathProblem.NOT_A_CORPUS, (
            'the first segment is judged before depth, so the missing spec is the cause, not the nesting'
        )

    def test_select_document_with_a_nested_path_in_a_corpus_raises_nested(
        self, tmp_path: Path, model: WorkspaceModel
    ) -> None:
        #: Given
        argument = tmp_path / 'docs' / 'code' / 'sub' / 'x.md'

        #: When
        with pytest.raises(DocumentPathError) as exc_info:
            select_document(model, tmp_path, argument)

        #: Then
        assert exc_info.value.reason is DocumentPathProblem.NESTED, 'corpora are flat'

    def test_select_document_with_a_document_the_loader_left_out_raises_not_listed(
        self, tmp_path: Path, model: WorkspaceModel
    ) -> None:
        #: Given
        argument = tmp_path / 'docs' / 'code' / 'README.md'

        #: When
        with pytest.raises(DocumentPathError) as exc_info:
            select_document(model, tmp_path, argument)

        #: Then
        assert exc_info.value.reason is DocumentPathProblem.NOT_LISTED, (
            'a file whose stem is not a valid document name is not a listed document'
        )

    def test_select_document_with_a_file_added_after_loading_raises_not_listed(
        self, tmp_path: Path, model: WorkspaceModel
    ) -> None:
        #: Given
        argument = _write(tmp_path, 'docs/code/later.md')

        #: When
        with pytest.raises(DocumentPathError) as exc_info:
            select_document(model, tmp_path, argument)

        #: Then
        assert exc_info.value.reason is DocumentPathProblem.NOT_LISTED, 'the model is a snapshot'
