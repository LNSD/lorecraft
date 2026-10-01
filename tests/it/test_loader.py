"""Workspace loader behavior over survey-shaped fixture trees.

Each tree mirrors the ``docs/`` layout of one real target repository (amp, mono, tools, ampup and this one)
with the document bodies left empty: the loader never reads a document, so only names and kinds matter. The
skill cases lay out the project skills directories the same way. The repositories are wired to a real
``DiskFileSystem`` over ``tmp_path``, and every path in the model is root-relative to it.
"""

from pathlib import Path
from textwrap import dedent
from typing import Final

import pytest

from lorecraft.agents import AgentName
from lorecraft.core.path import RootRelativePath
from lorecraft.project.aspect import AspectNamespace
from lorecraft.project.corpus import CorpusName
from lorecraft.project.document.repo import Repository as DocumentRepository
from lorecraft.project.layout import SNAPSHOT_SCOPE, SPECS_DIR
from lorecraft.project.schemas import (
    EmptyStructureSpecError,
    InvalidFrontmatterSchemaError,
    StructureSpecDecodeError,
)
from lorecraft.project.schemas import Repository as SchemaRepository
from lorecraft.project.skill import Repository as SkillRepository
from lorecraft.project.skill import SkillLocation, SkillRef, SkillsDir
from lorecraft.project.workspace.loader import load_model, load_workspace
from lorecraft.project.workspace.model import WorkspaceModel
from lorecraft.vfs import DiskFileSystem, VirtualFileSystem, take_snapshot

CLAUDE: Final[AgentName] = AgentName('claude-code')
CODEX: Final[AgentName] = AgentName('codex')
UNIVERSAL_SKILLS_DIR: Final[RootRelativePath] = RootRelativePath.parse('.agents/skills')
CLAUDE_SKILLS_DIR: Final[RootRelativePath] = RootRelativePath.parse('.claude/skills')

CODE: Final[CorpusName] = CorpusName.parse('code')
FEAT: Final[CorpusName] = CorpusName.parse('feat')

# A structure specification stating one structure rule and a frontmatter schema that accepts any frontmatter; the
# loader validates the specifications, not the documents.
VALID_STRUCTURE_SPEC: Final[str] = dedent(
    """
    {
      "empty_sections": "forbidden",
      "frontmatter": {"type": "object"}
    }
    """
)


@pytest.fixture(scope='function')
def schemas(tmp_path: Path) -> SchemaRepository:
    """A schema repository over the temporary root's `docs/__meta__/`.

    Args:
        tmp_path: Directory the repository reads through a real filesystem, as the repository root.
    """
    return SchemaRepository(DiskFileSystem(tmp_path), SPECS_DIR)


@pytest.fixture(scope='function')
def documents(tmp_path: Path) -> DocumentRepository:
    """A document repository over the temporary root.

    Args:
        tmp_path: Directory the repository reads through a real filesystem, as the repository root.
    """
    return DocumentRepository(DiskFileSystem(tmp_path))


@pytest.fixture(scope='function')
def skills(tmp_path: Path) -> SkillRepository:
    """A skill repository over the temporary root.

    Args:
        tmp_path: Directory the repository reads through a real filesystem, as the repository root.
    """
    return SkillRepository(DiskFileSystem(tmp_path))


def _write(root: Path, relative: str, text: str = '') -> None:
    """Write one file under the root, creating its parents.

    Args:
        root: Directory the file is written under, as the repository root.
        relative: Path of the file below `root`, with `/` separators.
        text: Content of the file, written as UTF-8. Empty by default.
    """
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')


def _skill_location(directory: str) -> SkillLocation:
    """The location of a skill whose directory and `SKILL.md` are no links.

    Args:
        directory: Root-relative path of the skill directory; it and its `SKILL.md` resolve to themselves.
    """
    path = RootRelativePath.parse(directory)
    return SkillLocation(SkillRef(path), resolves_to=path, file_resolves_to=path / 'SKILL.md')


def _linked_skill_location(directory: str, resolves_to: str, file_resolves_to: str) -> SkillLocation:
    """The location of a skill whose directory or `SKILL.md` is a link, with the real paths they lead to.

    Args:
        directory: Root-relative path of the skill directory as an agent reaches it.
        resolves_to: Root-relative path the skill directory resolves to.
        file_resolves_to: Root-relative path the skill's `SKILL.md` resolves to.
    """
    return SkillLocation(
        SkillRef(RootRelativePath.parse(directory)),
        resolves_to=RootRelativePath.parse(resolves_to),
        file_resolves_to=RootRelativePath.parse(file_resolves_to),
    )


def _write_tree(root: Path, prose: tuple[str, ...], schemas: tuple[str, ...], documents: tuple[str, ...]) -> None:
    """Lay out `docs/__meta__/<prose>.md`, `docs/__meta__/<schema>` and `docs/<document>` files.

    Every schema file holds a valid structure specification; one whose name is not a structure specification's is
    never read, so what it holds does not matter.

    Args:
        root: Directory the tree is written under, as the repository root.
        prose: Stems of the empty prose specifications, each written as `<stem>.md`.
        schemas: Filenames of the schema files, each written with a valid structure specification.
        documents: Paths of the empty documents, relative to `docs/`.
    """
    for stem in prose:
        _write(root, f'docs/__meta__/{stem}.md')
    for filename in schemas:
        _write(root, f'docs/__meta__/{filename}', VALID_STRUCTURE_SPEC)
    for relative in documents:
        _write(root, f'docs/{relative}')


def _amp_tree(root: Path) -> None:
    """amp: two governed corpora, a prose-less namespace spec, and two spec-less directories.

    Args:
        root: Directory the tree is written under, as the repository root.
    """
    _write_tree(
        root,
        prose=('README', 'code', 'code-pattern', 'code-principle', 'code-rust', 'feat'),
        schemas=(
            'code.structure.json',
            'code-crate.structure.json',
            'code-pattern.structure.json',
            'code-principle.structure.json',
            'code-rust.structure.json',
            'feat.structure.json',
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
    """mono: prose-only specs, and a `feat` spec with no `docs/feat/` directory.

    Args:
        root: Directory the tree is written under, as the repository root.
    """
    _write_tree(
        root,
        prose=('README', 'code', 'code-pattern', 'code-principle', 'code-rust', 'feat'),
        schemas=(),
        documents=('code/logging.md', 'code/rust-errors-handling.md'),
    )


def _tools_tree(root: Path) -> None:
    """tools: prose-only specs and a `docs/schemas/` directory holding no Markdown.

    Args:
        root: Directory the tree is written under, as the repository root.
    """
    _write_tree(
        root,
        prose=('README', 'code', 'code-pattern', 'code-principle', 'code-rust'),
        schemas=(),
        documents=('code/logging.md',),
    )
    _write(root, 'docs/schemas/npdm.spec.json', '{}')


def _ampup_tree(root: Path) -> None:
    """ampup: two namespace specs whose corpora have no spec of their own.

    Args:
        root: Directory the tree is written under, as the repository root.
    """
    _write_tree(
        root,
        prose=('README', 'code-pattern-docs', 'feature-docs'),
        schemas=(),
        documents=('code/logging.md', 'features/admin.md'),
    )


def _lorecraft_tree(root: Path) -> None:
    """lorecraft: a `feat` namespace spec and a glossary outside any corpus.

    Args:
        root: Directory the tree is written under, as the repository root.
    """
    _write_tree(
        root,
        prose=('README', 'code', 'code-pattern', 'code-principle', 'code-python', 'feat', 'feat-cli'),
        schemas=(
            'code.structure.json',
            'code-pattern.structure.json',
            'code-principle.structure.json',
            'code-python.structure.json',
            'feat.structure.json',
            'feat-cli.structure.json',
        ),
        documents=('code/logging.md', 'code/python-typing.md', 'feat/cli-check.md', 'feat/cli-check-frontmatter.md'),
    )
    _write(root, 'docs/feat/.gitkeep')
    _write(root, 'docs/glossary.md')
    _write(root, 'docs/assets/logo.svg')


def _namespaces(model: WorkspaceModel, corpus: CorpusName) -> tuple[str, ...]:
    """The namespace stems of one corpus in stored order, as strings.

    Args:
        model: Loaded workspace model to read the corpus from.
        corpus: Name of the corpus whose namespace specs are listed; it must be in the model.
    """
    loaded = model.find_corpus(corpus)
    assert loaded is not None, f'the model lists corpus {corpus}'
    return tuple(str(spec.namespace) for spec in loaded.namespace_specs)


def _document_paths(model: WorkspaceModel) -> tuple[str, ...]:
    """Every document path the model lists, in model order, as strings.

    Args:
        model: Loaded workspace model whose documents are listed.
    """
    return tuple(str(ref.path) for ref in model.documents())


@pytest.mark.it
class TestLoadWorkspaceAmp:
    def test_load_workspace_with_the_amp_tree_lists_code_and_feat_only(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository, skills: SkillRepository
    ) -> None:
        #: Given
        _amp_tree(tmp_path)

        #: When
        model = load_workspace(schemas, documents, skills)

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
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository, skills: SkillRepository
    ) -> None:
        #: Given
        _amp_tree(tmp_path)

        #: When
        model = load_workspace(schemas, documents, skills)

        #: Then
        assert _namespaces(model, CODE) == ('crate', 'pattern', 'principle', 'rust'), (
            'single-segment namespaces order by value'
        )
        assert _namespaces(model, FEAT) == (), 'amp has no feat namespace spec'

    def test_load_workspace_with_the_amp_tree_loads_the_prose_less_crate_namespace(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository, skills: SkillRepository
    ) -> None:
        #: Given
        _amp_tree(tmp_path)

        #: When
        model = load_workspace(schemas, documents, skills)

        #: Then
        code = model.find_corpus(CODE)
        assert code is not None, 'the model lists the code corpus'
        crate = code.namespace_specs[0]
        assert crate.files == (SPECS_DIR / 'code-crate.structure.json',), (
            'a namespace spec with JSON files and no prose still loads'
        )
        assert crate.structure is not None, 'the structure aspect is decoded'
        assert crate.structure.frontmatter is not None, 'the frontmatter schema is decoded with it'
        assert crate.structure.frontmatter.path == SPECS_DIR / 'code-crate.structure.json', (
            'the frontmatter schema carries the path of the specification it is written in'
        )


@pytest.mark.it
class TestLoadWorkspaceMono:
    def test_load_workspace_with_the_mono_tree_builds_no_corpus_for_the_feat_spec_without_a_directory(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository, skills: SkillRepository
    ) -> None:
        #: Given
        _mono_tree(tmp_path)

        #: When
        model = load_workspace(schemas, documents, skills)

        #: Then
        assert tuple(corpus.name for corpus in model.corpora) == (CODE,), (
            'a corpus spec without docs/<corpus>/ creates no corpus'
        )

    def test_load_workspace_with_the_mono_tree_leaves_the_frontmatter_ungoverned(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository, skills: SkillRepository
    ) -> None:
        #: Given
        _mono_tree(tmp_path)

        #: When
        model = load_workspace(schemas, documents, skills)

        #: Then
        ref = model.find_document(RootRelativePath.parse('docs/code/rust-errors-handling.md'))
        assert ref is not None, 'the document is listed'
        assert model.governance(ref).frontmatter_schemas() == (), 'prose-only specs carry no frontmatter schema'
        assert _namespaces(model, CODE) == ('pattern', 'principle', 'rust'), 'prose-only namespace specs load'


@pytest.mark.it
class TestLoadWorkspaceTools:
    def test_load_workspace_with_the_tools_tree_lists_code_alone(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository, skills: SkillRepository
    ) -> None:
        #: Given
        _tools_tree(tmp_path)

        #: When
        model = load_workspace(schemas, documents, skills)

        #: Then
        assert tuple(corpus.name for corpus in model.corpora) == (CODE,), 'docs/schemas/ has no stem'
        assert _document_paths(model) == ('docs/code/logging.md',), 'only the code corpus is listed'


@pytest.mark.it
class TestLoadWorkspaceAmpup:
    def test_load_workspace_with_the_ampup_tree_builds_zero_corpora(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository, skills: SkillRepository
    ) -> None:
        #: Given
        _ampup_tree(tmp_path)

        #: When
        model = load_workspace(schemas, documents, skills)

        #: Then
        assert model.corpora == (), 'a namespace spec creates no corpus on its own'
        assert model.documents() == (), 'the Markdown under docs/code/ and docs/features/ is not listed'


@pytest.mark.it
class TestLoadWorkspaceLorecraft:
    def test_load_workspace_with_the_lorecraft_tree_lists_code_and_feat(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository, skills: SkillRepository
    ) -> None:
        #: Given
        _lorecraft_tree(tmp_path)

        #: When
        model = load_workspace(schemas, documents, skills)

        #: Then
        assert tuple(corpus.name for corpus in model.corpora) == (CODE, FEAT), 'docs/assets/ has no stem'
        assert _document_paths(model) == (
            'docs/code/logging.md',
            'docs/code/python-typing.md',
            'docs/feat/cli-check.md',
            'docs/feat/cli-check-frontmatter.md',
        ), 'documents sort by stem, so cli-check precedes cli-check-frontmatter; .gitkeep and the glossary are absent'

    def test_load_workspace_with_the_lorecraft_tree_loads_the_feat_cli_namespace(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository, skills: SkillRepository
    ) -> None:
        #: Given
        _lorecraft_tree(tmp_path)

        #: When
        model = load_workspace(schemas, documents, skills)

        #: Then
        assert _namespaces(model, FEAT) == ('cli',), 'feat-cli narrows the feat corpus'
        assert _namespaces(model, CODE) == ('pattern', 'principle', 'python'), 'the code namespaces order by value'


@pytest.mark.it
class TestLoadWorkspaceEdgeCases:
    def test_load_workspace_with_a_meta_stem_never_makes_the_specification_directory_a_corpus(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository, skills: SkillRepository
    ) -> None:
        #: Given
        _write_tree(
            tmp_path, prose=('code', '__meta__'), schemas=('__meta__.structure.json',), documents=('code/logging.md',)
        )

        #: When
        model = load_workspace(schemas, documents, skills)

        #: Then
        assert [corpus.name for corpus in model.corpora] == [CorpusName.parse('code')], 'only the real corpus loads'

    def test_load_workspace_with_a_namespace_spec_alone_sorting_first_still_loads_the_later_corpora(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository, skills: SkillRepository
    ) -> None:
        #: Given
        # `api` sorts before `code` and has a directory, but only a namespace spec, so it is skipped first
        _write_tree(tmp_path, prose=('api-v1', 'code'), schemas=(), documents=('api/users.md', 'code/logging.md'))

        #: When
        model = load_workspace(schemas, documents, skills)

        #: Then
        assert tuple(corpus.name for corpus in model.corpora) == (CODE,), (
            'skipping a corpus with no spec of its own still loads every corpus after it'
        )

    def test_load_workspace_with_a_corpus_spec_without_a_directory_sorting_first_still_loads_the_later_corpora(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository, skills: SkillRepository
    ) -> None:
        #: Given
        # `agent` sorts before `code` and has a corpus spec, but no docs/agent/, so it is skipped first
        _write_tree(tmp_path, prose=('agent', 'code'), schemas=(), documents=('code/logging.md',))

        #: When
        model = load_workspace(schemas, documents, skills)

        #: Then
        assert tuple(corpus.name for corpus in model.corpora) == (CODE,), (
            'skipping a corpus with no directory still loads every corpus after it'
        )

    def test_load_workspace_with_a_nested_document_ignores_it(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository, skills: SkillRepository
    ) -> None:
        #: Given
        _write_tree(tmp_path, prose=('code',), schemas=(), documents=('code/logging.md', 'code/sub/x.md'))

        #: When
        model = load_workspace(schemas, documents, skills)

        #: Then
        assert _document_paths(model) == ('docs/code/logging.md',), 'a subdirectory of a corpus is not listed'

    def test_load_workspace_with_an_unknown_json_aspect_leaves_it_out_and_loads_the_corpus(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository, skills: SkillRepository
    ) -> None:
        #: Given
        _write_tree(tmp_path, prose=('code',), schemas=('code.headers.json',), documents=('code/logging.md',))

        #: When
        model = load_workspace(schemas, documents, skills)

        #: Then
        code = model.find_corpus(CODE)
        assert code is not None, 'the corpus still loads from its prose stem'
        assert code.spec.files == (SPECS_DIR / 'code.md',), 'a misnamed aspect token is not part of the spec'

    def test_load_workspace_with_a_dotted_stem_leaves_it_out_of_the_corpus_spec(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository, skills: SkillRepository
    ) -> None:
        #: Given
        _write_tree(tmp_path, prose=('feat',), schemas=('feat.feature.structure.json',), documents=('feat/admin.md',))

        #: When
        model = load_workspace(schemas, documents, skills)

        #: Then
        feat = model.find_corpus(FEAT)
        assert feat is not None, 'the corpus loads from its prose stem'
        assert feat.spec.files == (SPECS_DIR / 'feat.md',), 'feat.feature is not a stem, so its file is not a spec'

    def test_load_workspace_with_a_dotted_stem_alone_builds_no_corpus(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository, skills: SkillRepository
    ) -> None:
        #: Given
        _write_tree(tmp_path, prose=(), schemas=('feat.feature.structure.json',), documents=('feat/admin.md',))

        #: When
        model = load_workspace(schemas, documents, skills)

        #: Then
        assert model.corpora == (), 'a file at a dotted stem does not establish a corpus'

    def test_load_workspace_with_an_invalid_namespace_token_leaves_it_out(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository, skills: SkillRepository
    ) -> None:
        #: Given
        _write_tree(tmp_path, prose=('code', 'code-Python'), schemas=(), documents=('code/logging.md',))

        #: When
        model = load_workspace(schemas, documents, skills)

        #: Then
        assert _namespaces(model, CODE) == (), 'the misnamed stem narrows nothing'

    def test_load_workspace_with_a_json_file_at_a_non_stem_leaves_it_out(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository, skills: SkillRepository
    ) -> None:
        #: Given
        _write_tree(tmp_path, prose=('code',), schemas=('README.structure.json',), documents=('code/logging.md',))

        #: When
        model = load_workspace(schemas, documents, skills)

        #: Then
        assert tuple(corpus.name for corpus in model.corpora) == (CODE,), 'the misnamed JSON file makes no corpus'

    def test_load_workspace_with_a_header_file_leaves_it_out(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository, skills: SkillRepository
    ) -> None:
        #: Given
        # a header file from before the frontmatter schema moved into the structure specification
        _write_tree(tmp_path, prose=('code',), schemas=('code.header.json',), documents=('code/logging.md',))

        #: When
        model = load_workspace(schemas, documents, skills)

        #: Then
        corpus = model.find_corpus(CODE)
        assert corpus is not None, 'the corpus still loads from its prose stem'
        assert corpus.spec.files == (SPECS_DIR / 'code.md',), 'the header file is not one of the spec files'
        assert corpus.spec.structure is None, 'and it states no rules'

    def test_load_workspace_with_a_malformed_frontmatter_schema_raises_invalid_frontmatter_schema_error(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository, skills: SkillRepository
    ) -> None:
        #: Given
        # the corpus directory exists and is empty: validation happens before any document matters
        _write_tree(tmp_path, prose=('code',), schemas=(), documents=())
        (tmp_path / 'docs' / 'code').mkdir()
        _write(tmp_path, 'docs/__meta__/code.structure.json', '{"frontmatter": {"type": "nonsense"}}')

        #: When
        with pytest.raises(InvalidFrontmatterSchemaError) as exc_info:
            load_workspace(schemas, documents, skills)

        #: Then
        assert exc_info.value.path == SPECS_DIR / 'code.structure.json', 'the error names the rejected specification'

    def test_load_workspace_with_a_structure_spec_builds_the_structure_aspect(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository, skills: SkillRepository
    ) -> None:
        #: Given
        _write_tree(tmp_path, prose=('code',), schemas=('code.structure.json',), documents=('code/logging.md',))

        #: When
        model = load_workspace(schemas, documents, skills)

        #: Then
        ref = model.find_document(RootRelativePath.parse('docs/code/logging.md'))
        assert ref is not None, 'the document is listed'
        aspects = model.governance(ref).structure_specs()
        assert tuple(aspect.path for aspect in aspects) == (SPECS_DIR / 'code.structure.json',), (
            'the corpus structure specification governs its document'
        )

    def test_load_workspace_with_an_invalid_structure_spec_raises_empty_structure_spec_error(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository, skills: SkillRepository
    ) -> None:
        #: Given
        # the corpus directory exists and is empty: validation happens before any document matters
        _write_tree(tmp_path, prose=('code',), schemas=(), documents=())
        (tmp_path / 'docs' / 'code').mkdir()
        _write(tmp_path, 'docs/__meta__/code.structure.json', '{}')

        #: When
        with pytest.raises(EmptyStructureSpecError) as exc_info:
            load_workspace(schemas, documents, skills)

        #: Then
        assert exc_info.value.path == SPECS_DIR / 'code.structure.json', 'the error names the rejected specification'

    def test_load_workspace_with_a_broken_schema_in_an_unchecked_namespace_still_raises(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository, skills: SkillRepository
    ) -> None:
        #: Given
        _write_tree(tmp_path, prose=('code',), schemas=('code.structure.json',), documents=('code/logging.md',))
        _write(tmp_path, 'docs/__meta__/code-python.structure.json', 'not json')

        #: When
        with pytest.raises(StructureSpecDecodeError) as exc_info:
            load_workspace(schemas, documents, skills)

        #: Then
        assert exc_info.value.path == SPECS_DIR / 'code-python.structure.json', (
            'every structure specification is decoded eagerly'
        )

    def test_load_workspace_with_nested_namespaces_sorts_them_by_segment_count_then_value(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository, skills: SkillRepository
    ) -> None:
        #: Given
        _write_tree(
            tmp_path,
            prose=('code', 'code-python-errors', 'code-python', 'code-pattern', 'code-a-b-c'),
            schemas=(),
            documents=('code/logging.md',),
        )

        #: When
        model = load_workspace(schemas, documents, skills)

        #: Then
        assert _namespaces(model, CODE) == ('pattern', 'python', 'python-errors', 'a-b-c'), (
            'segment count is broadness; value only orders siblings with the same count'
        )

    def test_load_workspace_with_a_namespace_spec_records_its_parsed_name(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository, skills: SkillRepository
    ) -> None:
        #: Given
        _write_tree(tmp_path, prose=('code', 'code-python'), schemas=(), documents=('code/logging.md',))

        #: When
        model = load_workspace(schemas, documents, skills)

        #: Then
        code = model.find_corpus(CODE)
        assert code is not None, 'the model lists the code corpus'
        assert code.namespace_specs[0].name == (CODE, AspectNamespace.parse('python')), (
            'the stem is parsed into corpus and namespace'
        )

    def test_load_workspace_with_a_symlinked_document_leaves_it_out(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository, skills: SkillRepository
    ) -> None:
        #: Given
        _write_tree(tmp_path, prose=('code',), schemas=(), documents=('code/logging.md',))
        (tmp_path / 'docs' / 'code' / 'alias.md').symlink_to(tmp_path / 'docs' / 'code' / 'logging.md')

        #: When
        model = load_workspace(schemas, documents, skills)

        #: Then
        assert _document_paths(model) == ('docs/code/logging.md',), 'the symlink is not a document'

    def test_load_workspace_with_an_invalid_document_stem_leaves_it_out(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository, skills: SkillRepository
    ) -> None:
        #: Given
        _write_tree(tmp_path, prose=('code',), schemas=(), documents=('code/logging.md', 'code/README.md'))

        #: When
        model = load_workspace(schemas, documents, skills)

        #: Then
        assert _document_paths(model) == ('docs/code/logging.md',), 'the misnamed file is not a document'

    def test_load_workspace_with_a_symlinked_corpus_directory_builds_no_corpus_for_it(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository, skills: SkillRepository
    ) -> None:
        #: Given
        _write_tree(
            tmp_path, prose=('code', 'rules'), schemas=('rules.structure.json',), documents=('code/logging.md',)
        )
        (tmp_path / 'docs' / 'rules').symlink_to(tmp_path / 'docs' / 'code')

        #: When
        model = load_workspace(schemas, documents, skills)

        #: Then
        assert tuple(corpus.name for corpus in model.corpora) == (CODE,), 'the symlinked directory is no corpus'

    def test_load_workspace_with_no_docs_directory_builds_an_empty_model(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository, skills: SkillRepository
    ) -> None:
        #: Given
        # nothing is created under the temporary root
        missing_docs = tmp_path / 'docs'

        #: When
        model = load_workspace(schemas, documents, skills)

        #: Then
        assert not missing_docs.exists(), 'the case turns on docs/ being absent'
        assert model == WorkspaceModel(corpora=(), skills_dirs=(), skill_locations=()), (
            'a root without docs/ is an empty workspace'
        )


@pytest.mark.it
class TestLoadWorkspaceSkills:
    def test_load_workspace_with_skills_in_the_universal_directory_lists_them_by_directory(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository, skills: SkillRepository
    ) -> None:
        #: Given
        _write(tmp_path, '.agents/skills/review/SKILL.md')
        _write(tmp_path, '.agents/skills/commit/SKILL.md')

        #: When
        model = load_workspace(schemas, documents, skills)

        #: Then
        assert model.skill_locations == (
            _skill_location('.agents/skills/commit'),
            _skill_location('.agents/skills/review'),
        ), 'every skill is listed, sorted by directory'

    def test_load_workspace_with_skills_and_a_corpus_keeps_the_skills_out_of_the_documents(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository, skills: SkillRepository
    ) -> None:
        #: Given
        _write_tree(tmp_path, prose=('code',), schemas=(), documents=('code/logging.md',))
        _write(tmp_path, '.agents/skills/review/SKILL.md')

        #: When
        model = load_workspace(schemas, documents, skills)

        #: Then
        assert _document_paths(model) == ('docs/code/logging.md',), 'a skill belongs to no corpus'

    def test_load_workspace_with_the_universal_directory_alone_records_it_for_the_agent_that_reads_it(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository, skills: SkillRepository
    ) -> None:
        #: Given
        _write(tmp_path, '.agents/skills/review/SKILL.md')

        #: When
        model = load_workspace(schemas, documents, skills)

        #: Then
        assert model.skills_dirs == (
            SkillsDir(agent=CODEX, path=UNIVERSAL_SKILLS_DIR, resolves_to=UNIVERSAL_SKILLS_DIR),
        ), 'only the agent whose skills directory the repository has is recorded'

    def test_load_workspace_with_a_directory_linked_to_another_records_both_agents_at_one_real_directory(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository, skills: SkillRepository
    ) -> None:
        #: Given
        _write(tmp_path, '.agents/skills/review/SKILL.md')
        (tmp_path / '.claude').mkdir()
        (tmp_path / '.claude' / 'skills').symlink_to('../.agents/skills')

        #: When
        model = load_workspace(schemas, documents, skills)

        #: Then
        assert model.skills_dirs == (
            SkillsDir(agent=CLAUDE, path=CLAUDE_SKILLS_DIR, resolves_to=UNIVERSAL_SKILLS_DIR),
            SkillsDir(agent=CODEX, path=UNIVERSAL_SKILLS_DIR, resolves_to=UNIVERSAL_SKILLS_DIR),
        ), 'each agent keeps its own record, and both name the one real directory'

    def test_load_workspace_with_skills_in_two_agents_directories_lists_all_of_them(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository, skills: SkillRepository
    ) -> None:
        #: Given
        _write(tmp_path, '.agents/skills/review/SKILL.md')
        _write(tmp_path, '.claude/skills/commit/SKILL.md')

        #: When
        model = load_workspace(schemas, documents, skills)

        #: Then
        assert model.skill_locations == (
            _skill_location('.agents/skills/review'),
            _skill_location('.claude/skills/commit'),
        ), 'every agent directory is read, and the refs sort across them'

    def test_load_workspace_with_one_skills_directory_inside_another_sorts_the_refs_as_a_whole(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository, skills: SkillRepository
    ) -> None:
        #: Given
        _write(tmp_path, '.agents/skills/alpha/SKILL.md')
        _write(tmp_path, '.agents/skills/zeta/SKILL.md')
        _write(tmp_path, '.agents/skills/claude/inner/SKILL.md')
        (tmp_path / '.claude').mkdir()
        (tmp_path / '.claude' / 'skills').symlink_to('../.agents/skills/claude')

        #: When
        model = load_workspace(schemas, documents, skills)

        #: Then
        assert model.skill_locations == (
            _skill_location('.agents/skills/alpha'),
            _skill_location('.agents/skills/claude/inner'),
            _skill_location('.agents/skills/zeta'),
        ), 'the refs of a nested skills directory sort among the refs of the one holding it'

    def test_load_workspace_with_no_skills_directory_records_none(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository, skills: SkillRepository
    ) -> None:
        #: Given
        # nothing is created under the temporary root
        missing_skills_dir = tmp_path / '.agents' / 'skills'

        #: When
        model = load_workspace(schemas, documents, skills)

        #: Then
        assert not missing_skills_dir.exists(), 'the case turns on the skills directories being absent'
        assert model.skills_dirs == (), 'an agent whose skills directory is absent is not recorded'


@pytest.mark.it
class TestLoadModel:
    def test_load_model_over_a_snapshot_lists_the_skills_both_agents_read_once(self, tmp_path: Path) -> None:
        #: Given
        _write(tmp_path, '.agents/skills/review/SKILL.md')
        (tmp_path / '.claude').mkdir()
        (tmp_path / '.claude' / 'skills').symlink_to('../.agents/skills')
        snapshot = take_snapshot(tmp_path, SNAPSHOT_SCOPE)

        #: When
        model = load_model(VirtualFileSystem(snapshot))

        #: Then
        assert model.skill_locations == (_skill_location('.agents/skills/review'),), (
            'the snapshot scope covers the skills directories, and the linked directory adds no second ref'
        )

    def test_load_model_over_a_snapshot_lists_a_skill_linked_outside_the_skills_directories(
        self, tmp_path: Path
    ) -> None:
        #: Given
        _write(tmp_path, 'skills/review/SKILL.md')
        (tmp_path / '.agents' / 'skills').mkdir(parents=True)
        (tmp_path / '.agents' / 'skills' / 'review').symlink_to('../../skills/review')
        snapshot = take_snapshot(tmp_path, SNAPSHOT_SCOPE)

        #: When
        model = load_model(VirtualFileSystem(snapshot))

        #: Then
        assert model.skill_locations == (
            _linked_skill_location('.agents/skills/review', 'skills/review', 'skills/review/SKILL.md'),
        ), 'the scan follows the link, so the snapshot lists the skill the disk view lists'

    def test_load_model_over_a_snapshot_lists_a_skill_whose_skill_file_is_linked(self, tmp_path: Path) -> None:
        #: Given
        _write(tmp_path, 'shared/REVIEW.md')
        (tmp_path / '.agents' / 'skills' / 'review').mkdir(parents=True)
        (tmp_path / '.agents' / 'skills' / 'review' / 'SKILL.md').symlink_to('../../../shared/REVIEW.md')
        snapshot = take_snapshot(tmp_path, SNAPSHOT_SCOPE)

        #: When
        model = load_model(VirtualFileSystem(snapshot))

        #: Then
        assert model.skill_locations == (
            _linked_skill_location('.agents/skills/review', '.agents/skills/review', 'shared/REVIEW.md'),
        ), 'the scan reads through the linked SKILL.md, so the snapshot lists the skill the disk view lists'

    def test_load_model_over_a_snapshot_with_a_skills_directory_linked_elsewhere_lists_its_skills(
        self, tmp_path: Path
    ) -> None:
        #: Given
        _write(tmp_path, 'skills/review/SKILL.md')
        (tmp_path / '.claude').mkdir()
        (tmp_path / '.claude' / 'skills').symlink_to('../skills')
        snapshot = take_snapshot(tmp_path, SNAPSHOT_SCOPE)

        #: When
        model = load_model(VirtualFileSystem(snapshot))

        #: Then
        assert model.skill_locations == (_skill_location('skills/review'),), (
            'a skills directory linked to one no agent declares is read where it leads'
        )

    def test_load_model_over_the_disk_lists_a_skill_linked_outside_the_skills_directories(self, tmp_path: Path) -> None:
        #: Given
        _write(tmp_path, 'skills/review/SKILL.md')
        (tmp_path / '.agents' / 'skills').mkdir(parents=True)
        (tmp_path / '.agents' / 'skills' / 'review').symlink_to('../../skills/review')
        fs = DiskFileSystem(tmp_path)

        #: When
        model = load_model(fs)

        #: Then
        assert model.skill_locations == (
            _linked_skill_location('.agents/skills/review', 'skills/review', 'skills/review/SKILL.md'),
        ), 'the disk view follows the link, and the ref names the entry under the skills directory'
