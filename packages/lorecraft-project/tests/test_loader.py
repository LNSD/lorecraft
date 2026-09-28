"""Workspace loader behavior over survey-shaped fixture trees.

Each tree mirrors the ``docs/`` layout of one real target repository (amp, mono, tools, ampup and this one)
with the document bodies left empty: the loader never reads a document, so only names and kinds matter. The
repositories are wired to a real ``DiskFileSystem`` over ``tmp_path``, and every path in the model is
root-relative to it.
"""

from pathlib import Path
from typing import Final

import pytest

from lorecraft_project.aspect import AspectNamespace
from lorecraft_project.corpus import CorpusName
from lorecraft_project.document.repo import Repository as DocumentRepository
from lorecraft_project.layout import SPECS_DIR
from lorecraft_project.schemas import GetHeaderSchemaError, InvalidHeaderSchemaError
from lorecraft_project.schemas import Repository as SchemaRepository
from lorecraft_project.workspace.loader import load_workspace
from lorecraft_project.workspace.model import WorkspaceModel
from lorecraft_vfs import DiskFileSystem, RootRelativePath

CODE: Final[CorpusName] = CorpusName.parse('code')
FEAT: Final[CorpusName] = CorpusName.parse('feat')

# A well-formed Draft 2020-12 schema that accepts any frontmatter; the loader validates the dialect, not
# the documents.
VALID_HEADER_SCHEMA: Final[str] = '{"type": "object"}'


@pytest.fixture(scope='function')
def schemas(tmp_path: Path) -> SchemaRepository:
    """A schema repository over the temporary root's ``docs/__meta__/``."""
    return SchemaRepository(DiskFileSystem(tmp_path), SPECS_DIR)


@pytest.fixture(scope='function')
def documents(tmp_path: Path) -> DocumentRepository:
    """A document repository over the temporary root."""
    return DocumentRepository(DiskFileSystem(tmp_path))


def _write(root: Path, relative: str, text: str = '') -> None:
    """Write one file under the root, creating its parents."""
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')


def _write_tree(root: Path, prose: tuple[str, ...], schemas: tuple[str, ...], documents: tuple[str, ...]) -> None:
    """Lay out ``docs/__meta__/<prose>.md``, ``docs/__meta__/<schema>`` and ``docs/<document>`` files."""
    for stem in prose:
        _write(root, f'docs/__meta__/{stem}.md')
    for filename in schemas:
        _write(root, f'docs/__meta__/{filename}', VALID_HEADER_SCHEMA)
    for relative in documents:
        _write(root, f'docs/{relative}')


def _amp_tree(root: Path) -> None:
    """amp: two governed corpora, a prose-less namespace spec, and two spec-less directories."""
    _write_tree(
        root,
        prose=('README', 'code', 'code-pattern', 'code-principle', 'code-rust', 'feat'),
        schemas=(
            'code.header.json',
            'code.structure.json',
            'code.budget.json',
            'code-crate.header.json',
            'code-crate.budget.json',
            'code-pattern.header.json',
            'code-pattern.structure.json',
            'code-principle.header.json',
            'code-principle.structure.json',
            'code-rust.header.json',
            'code-rust.structure.json',
            'feat.header.json',
            'feat.budget.json',
        ),
        documents=(
            'code/crates.md',
            'code/crate-metadb-security.md',
            'code/rust-errors-handling.md',
            'feat/admin.md',
            'blog/verifiable-extraction.md',
            'schemas/manifest/README.md',
            'schemas/tables/evm-rpc.md',
            'architecture.md',
        ),
    )


def _mono_tree(root: Path) -> None:
    """mono: prose-only specs, and a ``feat`` spec with no ``docs/feat/`` directory."""
    _write_tree(
        root,
        prose=('README', 'code', 'code-pattern', 'code-principle', 'code-rust', 'feat'),
        schemas=(),
        documents=('code/logging.md', 'code/rust-errors-handling.md'),
    )


def _tools_tree(root: Path) -> None:
    """tools: prose-only specs and a ``docs/schemas/`` directory holding no Markdown."""
    _write_tree(
        root,
        prose=('README', 'code', 'code-pattern', 'code-principle', 'code-rust'),
        schemas=(),
        documents=('code/logging.md',),
    )
    _write(root, 'docs/schemas/npdm.spec.json', '{}')


def _ampup_tree(root: Path) -> None:
    """ampup: two namespace specs whose corpora have no spec of their own."""
    _write_tree(
        root,
        prose=('README', 'code-pattern-docs', 'feature-docs'),
        schemas=(),
        documents=('code/logging.md', 'features/admin.md'),
    )


def _lorecraft_tree(root: Path) -> None:
    """lorecraft: a ``feat`` namespace spec and a glossary outside any corpus."""
    _write_tree(
        root,
        prose=('README', 'code', 'code-pattern', 'code-principle', 'code-python', 'feat', 'feat-cli'),
        schemas=(
            'code.header.json',
            'code.structure.json',
            'code.budget.json',
            'code-pattern.header.json',
            'code-pattern.structure.json',
            'code-principle.header.json',
            'code-principle.structure.json',
            'code-python.header.json',
            'code-python.structure.json',
            'feat.header.json',
            'feat.structure.json',
            'feat.budget.json',
            'feat-cli.header.json',
        ),
        documents=('code/logging.md', 'code/python-typing.md', 'feat/cli-check.md', 'feat/cli-check-header.md'),
    )
    _write(root, 'docs/feat/.gitkeep')
    _write(root, 'docs/glossary.md')
    _write(root, 'docs/assets/logo.svg')


def _namespaces(model: WorkspaceModel, corpus: CorpusName) -> tuple[str, ...]:
    """The namespace stems of one corpus in stored order, as strings."""
    loaded = model.corpus(corpus)
    assert loaded is not None, f'the model lists corpus {corpus}'
    return tuple(str(spec.namespace) for spec in loaded.namespace_specs)


def _document_paths(model: WorkspaceModel) -> tuple[str, ...]:
    """Every document path the model lists, in model order, as strings."""
    return tuple(str(ref.path) for ref in model.documents())


@pytest.mark.it
class TestLoadWorkspaceAmp:
    def test_load_workspace_with_the_amp_tree_lists_code_and_feat_only(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository
    ) -> None:
        #: Given
        _amp_tree(tmp_path)

        #: When
        model = load_workspace(schemas, documents)

        #: Then
        assert tuple(corpus.name for corpus in model.corpora) == (CODE, FEAT), (
            'only directories with a spec at their stem are corpora; blog/ and schemas/ have none'
        )
        assert _document_paths(model) == (
            'docs/code/crate-metadb-security.md',
            'docs/code/crates.md',
            'docs/code/rust-errors-handling.md',
            'docs/feat/admin.md',
        ), 'documents directly inside each corpus are listed, corpus order then filename order'

    def test_load_workspace_with_the_amp_tree_sorts_the_code_namespaces_broad_to_narrow(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository
    ) -> None:
        #: Given
        _amp_tree(tmp_path)

        #: When
        model = load_workspace(schemas, documents)

        #: Then
        assert _namespaces(model, CODE) == ('crate', 'pattern', 'principle', 'rust'), (
            'single-segment namespaces order by value'
        )
        assert _namespaces(model, FEAT) == (), 'amp has no feat namespace spec'

    def test_load_workspace_with_the_amp_tree_loads_the_prose_less_crate_namespace(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository
    ) -> None:
        #: Given
        _amp_tree(tmp_path)

        #: When
        model = load_workspace(schemas, documents)

        #: Then
        code = model.corpus(CODE)
        assert code is not None, 'the model lists the code corpus'
        crate = code.namespace_specs[0]
        assert crate.files == (SPECS_DIR / 'code-crate.budget.json', SPECS_DIR / 'code-crate.header.json'), (
            'a namespace spec with JSON files and no prose still loads'
        )
        assert crate.header is not None, 'the header aspect is decoded'
        assert crate.header.path == SPECS_DIR / 'code-crate.header.json', 'the aspect carries its file path'


@pytest.mark.it
class TestLoadWorkspaceMono:
    def test_load_workspace_with_the_mono_tree_builds_no_corpus_for_the_feat_spec_without_a_directory(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository
    ) -> None:
        #: Given
        _mono_tree(tmp_path)

        #: When
        model = load_workspace(schemas, documents)

        #: Then
        assert tuple(corpus.name for corpus in model.corpora) == (CODE,), (
            'a corpus spec without docs/<corpus>/ creates no corpus'
        )

    def test_load_workspace_with_the_mono_tree_leaves_the_header_aspect_ungoverned(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository
    ) -> None:
        #: Given
        _mono_tree(tmp_path)

        #: When
        model = load_workspace(schemas, documents)

        #: Then
        ref = model.locate(RootRelativePath.parse('docs/code/rust-errors-handling.md'))
        assert ref is not None, 'the document is listed'
        assert model.governance(ref).header_schemas() == (), 'prose-only specs carry no header schema'
        assert _namespaces(model, CODE) == ('pattern', 'principle', 'rust'), 'prose-only namespace specs load'


@pytest.mark.it
class TestLoadWorkspaceTools:
    def test_load_workspace_with_the_tools_tree_lists_code_alone(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository
    ) -> None:
        #: Given
        _tools_tree(tmp_path)

        #: When
        model = load_workspace(schemas, documents)

        #: Then
        assert tuple(corpus.name for corpus in model.corpora) == (CODE,), 'docs/schemas/ has no stem'
        assert _document_paths(model) == ('docs/code/logging.md',), 'only the code corpus is listed'


@pytest.mark.it
class TestLoadWorkspaceAmpup:
    def test_load_workspace_with_the_ampup_tree_builds_zero_corpora(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository
    ) -> None:
        #: Given
        _ampup_tree(tmp_path)

        #: When
        model = load_workspace(schemas, documents)

        #: Then
        assert model.corpora == (), 'a namespace spec creates no corpus on its own'
        assert model.documents() == (), 'the Markdown under docs/code/ and docs/features/ is not listed'


@pytest.mark.it
class TestLoadWorkspaceLorecraft:
    def test_load_workspace_with_the_lorecraft_tree_lists_code_and_feat(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository
    ) -> None:
        #: Given
        _lorecraft_tree(tmp_path)

        #: When
        model = load_workspace(schemas, documents)

        #: Then
        assert tuple(corpus.name for corpus in model.corpora) == (CODE, FEAT), 'docs/assets/ has no stem'
        assert _document_paths(model) == (
            'docs/code/logging.md',
            'docs/code/python-typing.md',
            'docs/feat/cli-check.md',
            'docs/feat/cli-check-header.md',
        ), 'documents sort by stem, so cli-check precedes cli-check-header; .gitkeep and the glossary are absent'

    def test_load_workspace_with_the_lorecraft_tree_loads_the_feat_cli_namespace(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository
    ) -> None:
        #: Given
        _lorecraft_tree(tmp_path)

        #: When
        model = load_workspace(schemas, documents)

        #: Then
        assert _namespaces(model, FEAT) == ('cli',), 'feat-cli narrows the feat corpus'
        assert _namespaces(model, CODE) == ('pattern', 'principle', 'python'), 'the code namespaces order by value'


@pytest.mark.it
class TestLoadWorkspaceEdgeCases:
    def test_load_workspace_with_a_meta_stem_never_makes_the_specification_directory_a_corpus(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository
    ) -> None:
        #: Given
        _write_tree(
            tmp_path, prose=('code', '__meta__'), schemas=('__meta__.header.json',), documents=('code/logging.md',)
        )

        #: When
        model = load_workspace(schemas, documents)

        #: Then
        assert [corpus.name for corpus in model.corpora] == [CorpusName.parse('code')], 'only the real corpus loads'

    def test_load_workspace_with_a_nested_document_ignores_it(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository
    ) -> None:
        #: Given
        _write_tree(tmp_path, prose=('code',), schemas=(), documents=('code/logging.md', 'code/sub/x.md'))

        #: When
        model = load_workspace(schemas, documents)

        #: Then
        assert _document_paths(model) == ('docs/code/logging.md',), 'a subdirectory of a corpus is not listed'

    def test_load_workspace_with_an_unknown_json_aspect_leaves_it_out_and_loads_the_corpus(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository
    ) -> None:
        #: Given
        _write_tree(tmp_path, prose=('code',), schemas=('code.headers.json',), documents=('code/logging.md',))

        #: When
        model = load_workspace(schemas, documents)

        #: Then
        code = model.corpus(CODE)
        assert code is not None, 'the corpus still loads from its prose stem'
        assert code.spec.files == (SPECS_DIR / 'code.md',), 'a misnamed aspect token is not part of the spec'

    def test_load_workspace_with_a_dotted_stem_leaves_it_out_of_the_corpus_spec(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository
    ) -> None:
        #: Given
        _write_tree(tmp_path, prose=('feat',), schemas=('feat.feature.structure.json',), documents=('feat/admin.md',))

        #: When
        model = load_workspace(schemas, documents)

        #: Then
        feat = model.corpus(FEAT)
        assert feat is not None, 'the corpus loads from its prose stem'
        assert feat.spec.files == (SPECS_DIR / 'feat.md',), 'feat.feature is not a stem, so its file is not a spec'

    def test_load_workspace_with_a_dotted_stem_alone_builds_no_corpus(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository
    ) -> None:
        #: Given
        _write_tree(tmp_path, prose=(), schemas=('feat.feature.structure.json',), documents=('feat/admin.md',))

        #: When
        model = load_workspace(schemas, documents)

        #: Then
        assert model.corpora == (), 'a file at a dotted stem does not establish a corpus'

    def test_load_workspace_with_an_invalid_namespace_token_leaves_it_out(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository
    ) -> None:
        #: Given
        _write_tree(tmp_path, prose=('code', 'code-Python'), schemas=(), documents=('code/logging.md',))

        #: When
        model = load_workspace(schemas, documents)

        #: Then
        assert _namespaces(model, CODE) == (), 'the misnamed stem narrows nothing'

    def test_load_workspace_with_a_json_file_at_a_non_stem_leaves_it_out(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository
    ) -> None:
        #: Given
        _write_tree(tmp_path, prose=('code',), schemas=('README.header.json',), documents=('code/logging.md',))

        #: When
        model = load_workspace(schemas, documents)

        #: Then
        assert tuple(corpus.name for corpus in model.corpora) == (CODE,), 'the misnamed JSON file makes no corpus'

    def test_load_workspace_with_broken_json_raises_get_header_schema_error(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository
    ) -> None:
        #: Given
        _write_tree(tmp_path, prose=('code',), schemas=(), documents=('code/logging.md',))
        _write(tmp_path, 'docs/__meta__/code.header.json', '{')

        #: When
        with pytest.raises(GetHeaderSchemaError) as exc_info:
            load_workspace(schemas, documents)

        #: Then
        assert 'docs/__meta__/code.header.json' in str(exc_info.value), 'the error names the broken schema'

    def test_load_workspace_with_an_invalid_json_schema_raises_invalid_header_schema_error(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository
    ) -> None:
        #: Given
        # the corpus directory exists and is empty: validation happens before any document matters
        _write_tree(tmp_path, prose=('code',), schemas=(), documents=())
        (tmp_path / 'docs' / 'code').mkdir()
        _write(tmp_path, 'docs/__meta__/code.header.json', '{"type": "nonsense"}')

        #: When
        with pytest.raises(InvalidHeaderSchemaError) as exc_info:
            load_workspace(schemas, documents)

        #: Then
        assert exc_info.value.path == SPECS_DIR / 'code.header.json', 'the error names the rejected schema'

    def test_load_workspace_with_a_broken_schema_in_an_unchecked_namespace_still_raises(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository
    ) -> None:
        #: Given
        _write_tree(tmp_path, prose=('code',), schemas=('code.header.json',), documents=('code/logging.md',))
        _write(tmp_path, 'docs/__meta__/code-python.header.json', 'not json')

        #: When
        with pytest.raises(GetHeaderSchemaError) as exc_info:
            load_workspace(schemas, documents)

        #: Then
        assert 'code-python.header.json' in str(exc_info.value), 'every header schema is decoded eagerly'

    def test_load_workspace_with_nested_namespaces_sorts_them_by_segment_count_then_value(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository
    ) -> None:
        #: Given
        _write_tree(
            tmp_path,
            prose=('code', 'code-python-errors', 'code-python', 'code-pattern', 'code-a-b-c'),
            schemas=(),
            documents=('code/logging.md',),
        )

        #: When
        model = load_workspace(schemas, documents)

        #: Then
        assert _namespaces(model, CODE) == ('pattern', 'python', 'python-errors', 'a-b-c'), (
            'segment count is broadness; value only orders siblings with the same count'
        )

    def test_load_workspace_with_a_namespace_spec_records_its_parsed_name(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository
    ) -> None:
        #: Given
        _write_tree(tmp_path, prose=('code', 'code-python'), schemas=(), documents=('code/logging.md',))

        #: When
        model = load_workspace(schemas, documents)

        #: Then
        code = model.corpus(CODE)
        assert code is not None, 'the model lists the code corpus'
        assert code.namespace_specs[0].name == (CODE, AspectNamespace.parse('python')), (
            'the stem is parsed into corpus and namespace'
        )

    def test_load_workspace_with_a_symlinked_document_leaves_it_out(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository
    ) -> None:
        #: Given
        _write_tree(tmp_path, prose=('code',), schemas=(), documents=('code/logging.md',))
        (tmp_path / 'docs' / 'code' / 'alias.md').symlink_to(tmp_path / 'docs' / 'code' / 'logging.md')

        #: When
        model = load_workspace(schemas, documents)

        #: Then
        assert _document_paths(model) == ('docs/code/logging.md',), 'the symlink is not a document'

    def test_load_workspace_with_an_invalid_document_stem_leaves_it_out(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository
    ) -> None:
        #: Given
        _write_tree(tmp_path, prose=('code',), schemas=(), documents=('code/logging.md', 'code/README.md'))

        #: When
        model = load_workspace(schemas, documents)

        #: Then
        assert _document_paths(model) == ('docs/code/logging.md',), 'the misnamed file is not a document'

    def test_load_workspace_with_a_symlinked_corpus_directory_builds_no_corpus_for_it(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository
    ) -> None:
        #: Given
        _write_tree(tmp_path, prose=('code', 'rules'), schemas=('rules.header.json',), documents=('code/logging.md',))
        (tmp_path / 'docs' / 'rules').symlink_to(tmp_path / 'docs' / 'code')

        #: When
        model = load_workspace(schemas, documents)

        #: Then
        assert tuple(corpus.name for corpus in model.corpora) == (CODE,), 'the symlinked directory is no corpus'

    def test_load_workspace_with_no_docs_directory_builds_an_empty_model(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository
    ) -> None:
        #: Given
        # nothing is created under the temporary root
        missing_docs = tmp_path / 'docs'

        #: When
        model = load_workspace(schemas, documents)

        #: Then
        assert not missing_docs.exists(), 'the case turns on docs/ being absent'
        assert model == WorkspaceModel(corpora=()), 'a root without docs/ is an empty workspace'
