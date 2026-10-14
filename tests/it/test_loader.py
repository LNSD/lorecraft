"""Workspace loader behavior over survey-shaped fixture trees.

Each tree mirrors the ``docs/`` layout of one real target repository (amp, mono, tools, ampup and this one)
with the document bodies left empty: the loader never reads a document, so only names and kinds matter. The
skill cases lay out the project skills directories the same way. The repositories are wired to a real
``DiskFileSystem`` over ``tmp_path``, and every path in the model is root-relative to it.
"""

import os
import stat
from collections.abc import Callable, Iterator
from pathlib import Path, PurePosixPath
from textwrap import dedent
from typing import Final

import pytest

from lorecraft.agents import AgentName
from lorecraft.core.mapping import FrozenMapping
from lorecraft.core.path import PathComponent, RootRelativePath
from lorecraft.project.aspect import AspectFilename, AspectNamespace
from lorecraft.project.corpus import CorpusName
from lorecraft.project.document import DocumentRef
from lorecraft.project.document.repo import Repository as DocumentRepository
from lorecraft.project.layout import SNAPSHOT_SCOPE, SPECS_DIR
from lorecraft.project.schemas import CorpusSpecName, NamespaceSpecName, SectionName
from lorecraft.project.schemas import Repository as SchemaRepository
from lorecraft.project.schemas.structure import StructureSpec
from lorecraft.project.skill import OutsideSymlink, SkillLocation, SkillRef, SkillsDir
from lorecraft.project.skill import Repository as SkillRepository
from lorecraft.project.workspace import (
    AdjacentAnyRuns,
    EmptyStructureSpec,
    FailedStructure,
    ForbiddenOutlineSections,
    ForeignFrontmatterDialect,
    FrontmatterSchemaId,
    InvalidFrontmatterSchema,
    InvalidTitlePattern,
    LoadFailure,
    RepeatedForbiddenSections,
    RepeatedOutlineSections,
    UndecodableStructureSpec,
    UnlistableCorpusDirectory,
    UnlistableDirectory,
    UnlistableSkillDirectory,
    UnlistableSkillsDirectory,
    UnreadableStructureFile,
    UnresolvableSkillEntry,
    UnresolvableSkillFile,
    UnresolvableSkillsDirectory,
    UntypedFrontmatterSchema,
)
from lorecraft.project.workspace.loader import load_model, load_workspace
from lorecraft.project.workspace.model import WorkspaceModel
from lorecraft.vfs import DiskFileSystem, OsRefusal, ResolvedPath, RootExit, VirtualFileSystem, take_snapshot

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
    # No link on the way, so the directory and its `SKILL.md` are their own resolved paths.
    return SkillLocation(
        SkillRef(ResolvedPath(path.parent), PathComponent.parse(path.value.name)),
        resolves_to=ResolvedPath(path),
        file_resolves_to=ResolvedPath(path / PathComponent.parse('SKILL.md')),
    )


def _linked_skill_location(directory: str, resolves_to: str, file_resolves_to: str) -> SkillLocation:
    """The location of a skill whose directory or `SKILL.md` is a link, with the resolved paths they lead to.

    Args:
        directory: Root-relative path of the skill directory as an agent reaches it.
        resolves_to: Root-relative path the skill directory resolves to.
        file_resolves_to: Root-relative path the skill's `SKILL.md` resolves to.
    """
    path = RootRelativePath.parse(directory)
    return SkillLocation(
        SkillRef(ResolvedPath(path.parent), PathComponent.parse(path.value.name)),
        resolves_to=ResolvedPath(RootRelativePath.parse(resolves_to)),
        file_resolves_to=ResolvedPath(RootRelativePath.parse(file_resolves_to)),
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
    """The namespaces of one corpus's namespace specs in stored order, as strings.

    Args:
        model: Loaded workspace model to read the corpus from.
        corpus: Name of the corpus whose namespace specs are listed; it must be in the model.
    """
    loaded = model.find_corpus(corpus)
    assert loaded is not None, f'the model lists corpus {corpus}'
    return tuple(str(spec.name.namespace) for spec in loaded.namespace_specs)


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
        assert tuple(corpus.name for corpus in model.sorted_corpora) == (CODE, FEAT), (
            'only directories with a spec at their name are corpora; blog/ and schemas/ have none'
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
        assert crate.files == (SPECS_DIR / PathComponent.parse('code-crate.structure.json'),), (
            'a namespace spec with JSON files and no prose still loads'
        )
        assert crate.structure is not None, 'the structure specification is decoded'
        assert crate.structure.frontmatter is not None, 'the frontmatter schema is decoded with it'
        assert crate.structure.frontmatter.path == SPECS_DIR / PathComponent.parse('code-crate.structure.json'), (
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
        assert tuple(corpus.name for corpus in model.sorted_corpora) == (CODE,), (
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
        governance = model.find_governance(ref)
        assert governance is not None, 'the document is in a corpus the model holds'
        assert governance.frontmatter_schemas() == (), 'prose-only specs carry no frontmatter schema'
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
        assert tuple(corpus.name for corpus in model.sorted_corpora) == (CODE,), 'docs/schemas/ has no spec'
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
        assert model.sorted_corpora == (), 'a namespace spec creates no corpus on its own'
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
        assert tuple(corpus.name for corpus in model.sorted_corpora) == (CODE, FEAT), 'docs/assets/ has no spec'
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
        assert [corpus.name for corpus in model.sorted_corpora] == [CorpusName.parse('code')], (
            'only the real corpus loads'
        )

    def test_load_workspace_with_a_namespace_spec_alone_sorting_first_still_loads_the_later_corpora(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository, skills: SkillRepository
    ) -> None:
        #: Given
        # `api` sorts before `code` and has a directory, but only a namespace spec, so it is skipped first
        _write_tree(tmp_path, prose=('api-v1', 'code'), schemas=(), documents=('api/users.md', 'code/logging.md'))

        #: When
        model = load_workspace(schemas, documents, skills)

        #: Then
        assert tuple(corpus.name for corpus in model.sorted_corpora) == (CODE,), (
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
        assert tuple(corpus.name for corpus in model.sorted_corpora) == (CODE,), (
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

    def test_load_workspace_with_a_json_no_file_type_claims_leaves_it_out_and_loads_the_corpus(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository, skills: SkillRepository
    ) -> None:
        #: Given
        _write_tree(tmp_path, prose=('code',), schemas=('code.headers.json',), documents=('code/logging.md',))

        #: When
        model = load_workspace(schemas, documents, skills)

        #: Then
        code = model.find_corpus(CODE)
        assert code is not None, 'the corpus still loads from its prose specification'
        assert code.corpus_spec.files == (SPECS_DIR / PathComponent.parse('code.md'),), (
            'a file no file type claims is not part of the spec'
        )

    def test_load_workspace_with_a_dotted_stem_leaves_it_out_of_the_corpus_spec(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository, skills: SkillRepository
    ) -> None:
        #: Given
        _write_tree(tmp_path, prose=('feat',), schemas=('feat.feature.structure.json',), documents=('feat/admin.md',))

        #: When
        model = load_workspace(schemas, documents, skills)

        #: Then
        feat = model.find_corpus(FEAT)
        assert feat is not None, 'the corpus loads from its prose specification'
        assert feat.corpus_spec.files == (SPECS_DIR / PathComponent.parse('feat.md'),), (
            'feat.feature is not a spec name, so its file is not a spec'
        )

    def test_load_workspace_with_a_dotted_stem_alone_builds_no_corpus(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository, skills: SkillRepository
    ) -> None:
        #: Given
        _write_tree(tmp_path, prose=(), schemas=('feat.feature.structure.json',), documents=('feat/admin.md',))

        #: When
        model = load_workspace(schemas, documents, skills)

        #: Then
        assert model.sorted_corpora == (), 'a file at a dotted stem does not establish a corpus'

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
        assert tuple(corpus.name for corpus in model.sorted_corpora) == (CODE,), (
            'the misnamed JSON file makes no corpus'
        )

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
        assert corpus is not None, 'the corpus still loads from its prose specification'
        assert corpus.corpus_spec.files == (SPECS_DIR / PathComponent.parse('code.md'),), (
            'the header file is not one of the spec files'
        )
        assert corpus.corpus_spec.structure is None, 'and it states no rules'

    def test_load_workspace_with_a_malformed_frontmatter_schema_records_the_structure_as_failed(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository, skills: SkillRepository
    ) -> None:
        #: Given
        _write_tree(tmp_path, prose=('code',), schemas=(), documents=())
        (tmp_path / 'docs' / 'code').mkdir()
        _write(tmp_path, 'docs/__meta__/code.structure.json', '{"frontmatter": {"type": "nonsense"}}')
        path = SPECS_DIR / PathComponent.parse('code.structure.json')

        #: When
        model = load_workspace(schemas, documents, skills)

        #: Then
        corpus = model.find_corpus(CODE)
        assert corpus is not None, 'the corpus still loads'
        failed = corpus.corpus_spec.structure
        assert isinstance(failed, FailedStructure), 'the failed structure stands in the layer'
        assert failed.path == path, 'it names the rejected specification'
        assert isinstance(failed.failure, InvalidFrontmatterSchema), 'with the condition it failed with'
        assert model.load_failures == (LoadFailure(path, failed.failure),), 'and the model lists it once'

    def test_load_workspace_with_a_structure_spec_file_builds_the_structure_spec(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository, skills: SkillRepository
    ) -> None:
        #: Given
        _write_tree(tmp_path, prose=('code',), schemas=('code.structure.json',), documents=('code/logging.md',))

        #: When
        model = load_workspace(schemas, documents, skills)

        #: Then
        ref = model.find_document(RootRelativePath.parse('docs/code/logging.md'))
        assert ref is not None, 'the document is listed'
        governance = model.find_governance(ref)
        assert governance is not None, 'the document is in a corpus the model holds'
        assert tuple(structure_spec.path for structure_spec in governance.structure_specs()) == (
            SPECS_DIR / PathComponent.parse('code.structure.json'),
        ), 'the corpus structure specification governs its document'

    def test_load_workspace_with_a_spec_json_file_builds_the_structure_spec_from_it(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository, skills: SkillRepository
    ) -> None:
        #: Given
        _write_tree(tmp_path, prose=('code',), schemas=('code.spec.json',), documents=('code/logging.md',))

        #: When
        model = load_workspace(schemas, documents, skills)

        #: Then
        corpus = model.find_corpus(CODE)
        assert corpus is not None, 'the corpus loads'
        structure = corpus.corpus_spec.structure
        assert isinstance(structure, StructureSpec), 'code.spec.json is decoded as the structure specification'
        assert structure.file.path == SPECS_DIR / PathComponent.parse('code.spec.json'), 'and it is named by its file'

    def test_load_workspace_with_a_legacy_structure_file_alone_falls_back_to_it(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository, skills: SkillRepository
    ) -> None:
        #: Given
        _write_tree(tmp_path, prose=('code',), schemas=('code.structure.json',), documents=('code/logging.md',))

        #: When
        model = load_workspace(schemas, documents, skills)

        #: Then
        corpus = model.find_corpus(CODE)
        assert corpus is not None, 'the corpus loads'
        structure = corpus.corpus_spec.structure
        assert isinstance(structure, StructureSpec), 'with no code.spec.json, code.structure.json is decoded'
        assert structure.file.path == SPECS_DIR / PathComponent.parse('code.structure.json'), (
            'and it is named by its own file'
        )

    def test_load_workspace_with_both_files_uses_the_spec_json_and_ignores_the_legacy_one(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository, skills: SkillRepository
    ) -> None:
        #: Given
        _write_tree(tmp_path, prose=('code',), schemas=('code.spec.json',), documents=('code/logging.md',))
        # Malformed, so a read of it would be a load failure.
        _write(tmp_path, 'docs/__meta__/code.structure.json', '{"frontmatter": {"type": "nonsense"}}')

        #: When
        model = load_workspace(schemas, documents, skills)

        #: Then
        corpus = model.find_corpus(CODE)
        assert corpus is not None, 'the corpus loads'
        structure = corpus.corpus_spec.structure
        assert isinstance(structure, StructureSpec), 'the structure comes from code.spec.json'
        assert structure.file.path == SPECS_DIR / PathComponent.parse('code.spec.json'), 'and names that file'
        assert model.load_failures == (), 'the legacy file is not read, so it fails nothing'
        assert corpus.corpus_spec.files == (
            SPECS_DIR / PathComponent.parse('code.md'),
            SPECS_DIR / PathComponent.parse('code.spec.json'),
        ), 'and it is not listed among the files of the specification either'

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
        assert code.namespace_specs[0].name == NamespaceSpecName(CODE, AspectNamespace.parse('python')), (
            'the specification name is parsed into corpus and namespace'
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
        assert tuple(corpus.name for corpus in model.sorted_corpora) == (CODE,), 'the symlinked directory is no corpus'

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
        assert model == WorkspaceModel(
            corpora=FrozenMapping({}),
            skills_dirs=frozenset(),
            skill_locations=FrozenMapping({}),
            outside_symlinks=FrozenMapping({}),
            load_failures=(),
        ), 'a root without docs/ is an empty workspace'


def _outside(path: str, target: Path) -> OutsideSymlink:
    """The record of a symlink at `path` that links straight out of the repository to `target`.

    Args:
        path: The root-relative symlink, which is also the link its chain leaves through.
        target: Its absolute target outside the root.
    """
    symlink = RootRelativePath.parse(path)
    return OutsideSymlink(symlink, RootExit(symlink, PurePosixPath(target)))


@pytest.mark.it
class TestLoadWorkspaceSkills:
    def test_load_workspace_with_a_skills_directory_an_entry_and_a_skill_file_leading_outside_records_each(
        self,
        tmp_path: Path,
        tmp_path_factory: pytest.TempPathFactory,
        schemas: SchemaRepository,
        documents: DocumentRepository,
        skills: SkillRepository,
    ) -> None:
        #: Given
        outside = tmp_path_factory.mktemp('outside')
        _write(outside, 'x/SKILL.md')
        _write(outside, 'x.md')
        (tmp_path / '.claude').mkdir()
        (tmp_path / '.claude' / 'skills').symlink_to(outside)
        (tmp_path / '.agents' / 'skills' / 'review').mkdir(parents=True)
        (tmp_path / '.agents' / 'skills' / 'review' / 'SKILL.md').symlink_to(outside / 'x.md')
        (tmp_path / '.agents' / 'skills' / 'x').symlink_to(outside / 'x')

        #: When
        model = load_workspace(schemas, documents, skills)

        #: Then
        assert model.sorted_outside_symlinks == (
            _outside('.agents/skills/review/SKILL.md', outside / 'x.md'),
            _outside('.agents/skills/x', outside / 'x'),
            _outside('.claude/skills', outside),
        ), 'each symlink of the layout leading outside is recorded where an agent reaches it, sorted by path'

    def test_load_workspace_with_an_entry_and_a_skill_file_leading_outside_lists_no_skill(
        self,
        tmp_path: Path,
        tmp_path_factory: pytest.TempPathFactory,
        schemas: SchemaRepository,
        documents: DocumentRepository,
        skills: SkillRepository,
    ) -> None:
        #: Given
        outside = tmp_path_factory.mktemp('outside')
        _write(outside, 'x/SKILL.md')
        _write(outside, 'x.md')
        (tmp_path / '.agents' / 'skills' / 'review').mkdir(parents=True)
        (tmp_path / '.agents' / 'skills' / 'review' / 'SKILL.md').symlink_to(outside / 'x.md')
        (tmp_path / '.agents' / 'skills' / 'x').symlink_to(outside / 'x')

        #: When
        model = load_workspace(schemas, documents, skills)

        #: Then
        assert model.sorted_skill_locations == (), 'neither leads to a skill inside the repository'

    def test_load_workspace_with_one_skills_directory_an_entry_of_another_records_a_shared_link_once(
        self,
        tmp_path: Path,
        tmp_path_factory: pytest.TempPathFactory,
        schemas: SchemaRepository,
        documents: DocumentRepository,
        skills: SkillRepository,
    ) -> None:
        #: Given
        outside = tmp_path_factory.mktemp('outside')
        _write(outside, 'x.md')
        _write(tmp_path, '.agents/skills/review/SKILL.md')
        (tmp_path / '.agents' / 'skills' / 'SKILL.md').symlink_to(outside / 'x.md')
        (tmp_path / '.claude').mkdir()
        (tmp_path / '.claude' / 'skills').symlink_to('../.agents')

        #: When
        model = load_workspace(schemas, documents, skills)

        #: Then
        assert model.sorted_outside_symlinks == (_outside('.agents/skills/SKILL.md', outside / 'x.md'),), (
            "the link is both the outer directory's entry SKILL.md and an entry of the inner one, and recorded once"
        )

    def test_load_workspace_with_skills_in_the_universal_directory_lists_them_by_directory(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository, skills: SkillRepository
    ) -> None:
        #: Given
        _write(tmp_path, '.agents/skills/review/SKILL.md')
        _write(tmp_path, '.agents/skills/commit/SKILL.md')

        #: When
        model = load_workspace(schemas, documents, skills)

        #: Then
        assert model.sorted_skill_locations == (
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
        assert model.sorted_skills_dirs == (
            SkillsDir(agent=CODEX, path=UNIVERSAL_SKILLS_DIR, resolves_to=ResolvedPath(UNIVERSAL_SKILLS_DIR)),
        ), 'only the agent whose skills directory the repository has is recorded'

    def test_load_workspace_with_a_directory_linked_to_another_records_both_agents_at_one_resolved_directory(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository, skills: SkillRepository
    ) -> None:
        #: Given
        _write(tmp_path, '.agents/skills/review/SKILL.md')
        (tmp_path / '.claude').mkdir()
        (tmp_path / '.claude' / 'skills').symlink_to('../.agents/skills')

        #: When
        model = load_workspace(schemas, documents, skills)

        #: Then
        assert model.sorted_skills_dirs == (
            SkillsDir(agent=CLAUDE, path=CLAUDE_SKILLS_DIR, resolves_to=ResolvedPath(UNIVERSAL_SKILLS_DIR)),
            SkillsDir(agent=CODEX, path=UNIVERSAL_SKILLS_DIR, resolves_to=ResolvedPath(UNIVERSAL_SKILLS_DIR)),
        ), 'each agent keeps its own record, and both name the one resolved directory'

    def test_load_workspace_with_skills_in_two_agents_directories_lists_all_of_them(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository, skills: SkillRepository
    ) -> None:
        #: Given
        _write(tmp_path, '.agents/skills/review/SKILL.md')
        _write(tmp_path, '.claude/skills/commit/SKILL.md')

        #: When
        model = load_workspace(schemas, documents, skills)

        #: Then
        assert model.sorted_skill_locations == (
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
        assert model.sorted_skill_locations == (
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
        assert model.sorted_skills_dirs == (), 'an agent whose skills directory is absent is not recorded'


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
        assert model.sorted_skill_locations == (_skill_location('.agents/skills/review'),), (
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
        assert model.sorted_skill_locations == (
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
        assert model.sorted_skill_locations == (
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
        assert model.sorted_skill_locations == (_skill_location('skills/review'),), (
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
        assert model.sorted_skill_locations == (
            _linked_skill_location('.agents/skills/review', 'skills/review', 'skills/review/SKILL.md'),
        ), 'the disk view follows the link, and the ref names the entry under the skills directory'


@pytest.fixture(scope='function')
def lock() -> Iterator[Callable[[Path], None]]:
    """A function that makes a path refuse every access, restoring each path afterwards for pytest's cleanup.

    Paths are restored in the order they were locked, so a locked parent is searchable again before its child.
    """
    locked: list[tuple[Path, int]] = []

    def lock_path(path: Path) -> None:
        locked.append((path, stat.S_IMODE(path.stat().st_mode)))
        path.chmod(0o000)

    yield lock_path
    for path, mode in locked:
        path.chmod(mode)


def _failed_structure(model: WorkspaceModel, corpus: CorpusName) -> FailedStructure:
    """The failed structure standing in the corpus spec's layer of a corpus the model holds.

    Args:
        model: A model whose corpus spec for `corpus` failed to load.
        corpus: The corpus whose spec is read.
    """
    held = model.find_corpus(corpus)
    assert held is not None, f'the corpus {corpus} still loads when its structure file does not'
    structure = held.corpus_spec.structure
    assert isinstance(structure, FailedStructure), 'the structure file failed, so a failed structure stands for it'
    return structure


@pytest.mark.it
class TestLoadWorkspaceFailures:
    """Each unit of the declaration that fails is recorded, and every other unit loads as if it had not failed."""

    @pytest.mark.skipif(os.geteuid() == 0, reason='root ignores file permissions')
    def test_load_workspace_with_an_unreadable_structure_file_records_it_and_loads_every_other_unit(
        self,
        tmp_path: Path,
        schemas: SchemaRepository,
        documents: DocumentRepository,
        skills: SkillRepository,
        lock: Callable[[Path], None],
    ) -> None:
        #: Given
        _write_tree(
            tmp_path,
            prose=('code', 'feat'),
            schemas=('code.structure.json', 'feat.structure.json'),
            documents=('code/logging.md', 'feat/admin.md'),
        )
        lock(tmp_path / 'docs' / '__meta__' / 'code.structure.json')
        path = SPECS_DIR / PathComponent.parse('code.structure.json')

        #: When
        model = load_workspace(schemas, documents, skills)

        #: Then
        failed = _failed_structure(model, CODE)
        assert failed == FailedStructure(
            path, UnreadableStructureFile(CorpusSpecName(CODE), OsRefusal.PERMISSION_DENIED)
        ), 'the failure records the path and the refusal, in the layer where the structure would be'
        assert model.load_failures == (LoadFailure(path, failed.failure),), 'and the model lists it once'
        feat = model.find_corpus(FEAT)
        assert feat is not None, 'the other corpus loads'
        assert isinstance(feat.corpus_spec.structure, StructureSpec), 'with its structure'
        assert tuple(str(ref.path) for ref in model.documents()) == ('docs/code/logging.md', 'docs/feat/admin.md'), (
            'and every document of both corpora is listed'
        )

    def test_load_workspace_with_a_structure_file_that_is_not_json_records_why(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository, skills: SkillRepository
    ) -> None:
        #: Given
        _write_tree(
            tmp_path,
            prose=('code', 'feat'),
            schemas=('feat.structure.json',),
            documents=('code/logging.md', 'feat/admin.md'),
        )
        _write(tmp_path, 'docs/__meta__/code.structure.json', 'not json')
        path = SPECS_DIR / PathComponent.parse('code.structure.json')

        #: When
        model = load_workspace(schemas, documents, skills)

        #: Then
        failed = _failed_structure(model, CODE)
        assert failed.path == path, 'the failure names the structure file'
        assert isinstance(failed.failure, UndecodableStructureSpec), 'the condition is that it does not decode'
        assert failed.failure.problems, 'and it carries the decoder problems'
        assert model.load_failures == (LoadFailure(path, failed.failure),), 'listed once'
        feat = model.find_corpus(FEAT)
        assert feat is not None and isinstance(feat.corpus_spec.structure, StructureSpec), 'the other corpus loads'

    def _assert_structure_failure_recorded(self, tmp_path: Path, content: str, condition: type[object]) -> None:
        """Assert a corpus structure file holding `content` fails with `condition`, the other corpus loading.

        Args:
            tmp_path: Directory the workspace is written under, as the repository root.
            content: Text of the `code` corpus's structure file.
            condition: The record type the failure must be.
        """
        _write_tree(
            tmp_path,
            prose=('code', 'feat'),
            schemas=('feat.structure.json',),
            documents=('code/logging.md', 'feat/admin.md'),
        )
        _write(tmp_path, 'docs/__meta__/code.structure.json', content)
        path = SPECS_DIR / PathComponent.parse('code.structure.json')
        fs = DiskFileSystem(tmp_path)

        model = load_workspace(SchemaRepository(fs, SPECS_DIR), DocumentRepository(fs), SkillRepository(fs))

        failed = _failed_structure(model, CODE)
        assert failed.path == path, 'the failure names the structure file'
        assert isinstance(failed.failure, condition), 'the failure is the record of the condition the file fails with'
        assert model.load_failures == (LoadFailure(path, failed.failure),), 'listed once, with its path and condition'
        feat = model.find_corpus(FEAT)
        assert feat is not None and isinstance(feat.corpus_spec.structure, StructureSpec), 'the other corpus loads'

    def test_load_workspace_with_a_structure_file_stating_states_no_rule_records_it_as_failed(
        self, tmp_path: Path
    ) -> None:
        #: Given
        content = '{}'

        #: When / Then
        self._assert_structure_failure_recorded(tmp_path, content, EmptyStructureSpec)

    def test_load_workspace_with_a_structure_file_stating_a_repeated_outline_section_records_it_as_failed(
        self, tmp_path: Path
    ) -> None:
        #: Given
        content = '{"outline": [{"section": "Usage"}, {"section": "Usage"}]}'

        #: When / Then
        self._assert_structure_failure_recorded(tmp_path, content, RepeatedOutlineSections)

    def test_load_workspace_with_a_structure_file_stating_a_repeated_forbidden_section_records_it_as_failed(
        self, tmp_path: Path
    ) -> None:
        #: Given
        content = '{"forbidden": ["Changelog", "Changelog"]}'

        #: When / Then
        self._assert_structure_failure_recorded(tmp_path, content, RepeatedForbiddenSections)

    def test_load_workspace_with_a_structure_file_stating_a_forbidden_outline_section_records_it_as_failed(
        self, tmp_path: Path
    ) -> None:
        #: Given
        content = '{"outline": [{"section": "Usage"}], "forbidden": ["Usage"]}'

        #: When / Then
        self._assert_structure_failure_recorded(tmp_path, content, ForbiddenOutlineSections)

    def test_load_workspace_with_a_structure_file_stating_adjacent_any_runs_records_it_as_failed(
        self, tmp_path: Path
    ) -> None:
        #: Given
        content = '{"outline": [{"any": true}, {"any": true}]}'

        #: When / Then
        self._assert_structure_failure_recorded(tmp_path, content, AdjacentAnyRuns)

    def test_load_workspace_with_a_structure_file_stating_an_invalid_title_pattern_records_it_as_failed(
        self, tmp_path: Path
    ) -> None:
        #: Given
        content = '{"title": {"pattern": "("}}'

        #: When / Then
        self._assert_structure_failure_recorded(tmp_path, content, InvalidTitlePattern)

    def test_load_workspace_with_a_structure_file_stating_an_invalid_frontmatter_schema_records_it_as_failed(
        self, tmp_path: Path
    ) -> None:
        #: Given
        content = '{"frontmatter": {"type": "nonsense"}}'

        #: When / Then
        self._assert_structure_failure_recorded(tmp_path, content, InvalidFrontmatterSchema)

    def test_load_workspace_with_a_structure_file_stating_an_id_in_the_frontmatter_schema_records_it_as_failed(
        self, tmp_path: Path
    ) -> None:
        #: Given
        content = '{"frontmatter": {"type": "object", "properties": {"a": {"$id": "https://example.com/a"}}}}'

        #: When / Then
        self._assert_structure_failure_recorded(tmp_path, content, FrontmatterSchemaId)

    def test_load_workspace_with_a_structure_file_stating_a_foreign_frontmatter_dialect_records_it_as_failed(
        self, tmp_path: Path
    ) -> None:
        #: Given
        content = '{"frontmatter": {"type": "object", "$schema": "http://json-schema.org/draft-07/schema#"}}'

        #: When / Then
        self._assert_structure_failure_recorded(tmp_path, content, ForeignFrontmatterDialect)

    def test_load_workspace_with_a_structure_file_stating_an_untyped_frontmatter_schema_records_it_as_failed(
        self, tmp_path: Path
    ) -> None:
        #: Given
        content = '{"frontmatter": {"properties": {}}}'

        #: When / Then
        self._assert_structure_failure_recorded(tmp_path, content, UntypedFrontmatterSchema)

    def test_load_workspace_with_a_repeated_outline_section_records_the_sections(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository, skills: SkillRepository
    ) -> None:
        #: Given
        _write_tree(tmp_path, prose=('code',), schemas=(), documents=('code/logging.md',))
        _write(
            tmp_path,
            'docs/__meta__/code.structure.json',
            '{"outline": [{"section": "Usage"}, {"section": "Usage"}, {"section": "Notes"}, {"section": "Notes"}]}',
        )

        #: When
        model = load_workspace(schemas, documents, skills)

        #: Then
        assert _failed_structure(model, CODE).failure == RepeatedOutlineSections(
            (SectionName('Notes'), SectionName('Usage'))
        ), 'the record carries the facts of the error: the repeated names, sorted'

    def test_load_workspace_with_a_foreign_dialect_records_what_the_schema_names(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository, skills: SkillRepository
    ) -> None:
        #: Given
        _write_tree(tmp_path, prose=('code',), schemas=(), documents=('code/logging.md',))
        _write(
            tmp_path,
            'docs/__meta__/code.structure.json',
            '{"frontmatter": {"type": "object", "$schema": "http://json-schema.org/draft-07/schema#"}}',
        )

        #: When
        model = load_workspace(schemas, documents, skills)

        #: Then
        assert _failed_structure(model, CODE).failure == ForeignFrontmatterDialect(
            "'http://json-schema.org/draft-07/schema#'"
        ), 'the record keeps the dialect as the error spelled it, so it is plain data'

    def test_load_workspace_with_a_failed_namespace_structure_file_keeps_the_corpus_layer_loaded(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository, skills: SkillRepository
    ) -> None:
        #: Given
        _write_tree(tmp_path, prose=('code',), schemas=('code.structure.json',), documents=('code/python-typing.md',))
        _write(tmp_path, 'docs/__meta__/code-python.structure.json', 'not json')
        path = SPECS_DIR / PathComponent.parse('code-python.structure.json')

        #: When
        model = load_workspace(schemas, documents, skills)

        #: Then
        ref = model.find_document(RootRelativePath.parse('docs/code/python-typing.md'))
        assert ref is not None, 'the document is listed'
        governance = model.find_governance(ref)
        assert governance is not None, 'its corpus is in the model'
        assert isinstance(governance.corpus_spec.structure, StructureSpec), 'the corpus layer loaded'
        namespace = governance.namespace_specs[0]
        assert isinstance(namespace.structure, FailedStructure), 'the namespace layer failed'
        assert namespace.structure.path == path, 'and names its file'
        assert namespace.name == NamespaceSpecName(CODE, AspectNamespace.parse('python')), 'in its own layer'
        assert governance.failed_layers() == (namespace.structure,), 'the governance lists the failed layer'
        assert governance.structure_specs() == (governance.corpus_spec.structure,), 'and applies only the loaded one'

    def test_load_workspace_with_two_broken_namespace_schemas_lists_the_broader_one_first(
        self, tmp_path: Path, schemas: SchemaRepository, documents: DocumentRepository, skills: SkillRepository
    ) -> None:
        #: Given
        # code-python-errors.structure.json sorts before code-python.structure.json by name, narrower first
        _write_tree(tmp_path, prose=('code',), schemas=('code.structure.json',), documents=('code/logging.md',))
        _write(tmp_path, 'docs/__meta__/code-python.structure.json', 'not json')
        _write(tmp_path, 'docs/__meta__/code-python-errors.structure.json', 'not json')

        #: When
        model = load_workspace(schemas, documents, skills)

        #: Then
        assert [failure.path for failure in model.load_failures] == [
            SPECS_DIR / PathComponent.parse('code-python.structure.json'),
            SPECS_DIR / PathComponent.parse('code-python-errors.structure.json'),
        ], 'both are recorded, the broader first, which is the one a load that raised would have named'

    @pytest.mark.skipif(os.geteuid() == 0, reason='root ignores directory permissions')
    def test_load_workspace_with_an_unlistable_corpus_directory_records_it_and_loads_every_other_corpus(
        self,
        tmp_path: Path,
        schemas: SchemaRepository,
        documents: DocumentRepository,
        skills: SkillRepository,
        lock: Callable[[Path], None],
    ) -> None:
        #: Given
        _write_tree(
            tmp_path,
            prose=('code', 'feat'),
            schemas=('code.structure.json', 'feat.structure.json'),
            documents=('code/logging.md', 'feat/admin.md'),
        )
        lock(tmp_path / 'docs' / 'code')

        #: When
        model = load_workspace(schemas, documents, skills)

        #: Then
        assert model.load_failures == (
            LoadFailure(
                RootRelativePath.parse('docs/code'), UnlistableCorpusDirectory(CODE, OsRefusal.PERMISSION_DENIED)
            ),
        ), 'the directory is recorded with its path and the refusal'
        assert tuple(str(ref.path) for ref in model.documents()) == ('docs/feat/admin.md',), (
            'the corpus holds no document, and the other corpus lists its own'
        )
        code = model.find_corpus(CODE)
        assert code is not None, 'the corpus is still known'
        assert isinstance(code.corpus_spec.structure, StructureSpec), 'with the structure its spec states'

    @pytest.mark.skipif(os.geteuid() == 0, reason='root ignores directory permissions')
    def test_load_workspace_with_an_unlistable_docs_directory_records_it_and_the_specification_directory(
        self,
        tmp_path: Path,
        schemas: SchemaRepository,
        documents: DocumentRepository,
        skills: SkillRepository,
        lock: Callable[[Path], None],
    ) -> None:
        #: Given
        _write_tree(tmp_path, prose=('code',), schemas=('code.structure.json',), documents=('code/logging.md',))
        lock(tmp_path / 'docs')

        #: When
        model = load_workspace(schemas, documents, skills)

        #: Then
        refusal = OsRefusal.PERMISSION_DENIED
        assert model.load_failures == (
            LoadFailure(SPECS_DIR, UnlistableDirectory(refusal)),
            LoadFailure(RootRelativePath.parse('docs'), UnlistableDirectory(refusal)),
        ), 'each directory that cannot be listed is a failure at its own path, the specification directory first'
        assert model.sorted_corpora == (), 'and no corpus is known from either'

    @pytest.mark.skipif(os.geteuid() == 0, reason='root ignores directory permissions')
    def test_load_workspace_with_an_unlistable_specification_directory_records_it(
        self,
        tmp_path: Path,
        schemas: SchemaRepository,
        documents: DocumentRepository,
        skills: SkillRepository,
        lock: Callable[[Path], None],
    ) -> None:
        #: Given
        _write_tree(tmp_path, prose=('code',), schemas=('code.structure.json',), documents=('code/logging.md',))
        lock(tmp_path / 'docs' / '__meta__')

        #: When
        model = load_workspace(schemas, documents, skills)

        #: Then
        assert model.load_failures == (LoadFailure(SPECS_DIR, UnlistableDirectory(OsRefusal.PERMISSION_DENIED)),), (
            'the specification directory is recorded as a value'
        )
        assert model.sorted_corpora == (), 'and with no specification no corpus is known'

    @pytest.mark.skipif(os.geteuid() == 0, reason='root ignores directory permissions')
    def test_load_workspace_with_an_unlistable_skills_directory_records_it_and_loads_the_other_skills(
        self,
        tmp_path: Path,
        schemas: SchemaRepository,
        documents: DocumentRepository,
        skills: SkillRepository,
        lock: Callable[[Path], None],
    ) -> None:
        #: Given
        _write(tmp_path, '.claude/skills/review/SKILL.md')
        (tmp_path / '.agents' / 'skills').mkdir(parents=True)
        lock(tmp_path / '.agents' / 'skills')

        #: When
        model = load_workspace(schemas, documents, skills)

        #: Then
        assert model.load_failures == (
            LoadFailure(
                UNIVERSAL_SKILLS_DIR, UnlistableSkillsDirectory(UNIVERSAL_SKILLS_DIR, OsRefusal.PERMISSION_DENIED)
            ),
        ), 'the skills directory is recorded with its path and the refusal'
        assert model.sorted_skill_locations == (_skill_location('.claude/skills/review'),), (
            'the other directory is listed'
        )

    @pytest.mark.skipif(os.geteuid() == 0, reason='root ignores directory permissions')
    def test_load_workspace_with_a_skills_directory_that_cannot_be_resolved_records_it_once(
        self,
        tmp_path: Path,
        schemas: SchemaRepository,
        documents: DocumentRepository,
        skills: SkillRepository,
        lock: Callable[[Path], None],
    ) -> None:
        #: Given
        _write(tmp_path, 'shared/skills/review/SKILL.md')
        _write(tmp_path, '.agents/skills/commit/SKILL.md')
        (tmp_path / '.claude').mkdir()
        (tmp_path / '.claude' / 'skills').symlink_to('../shared/skills')
        lock(tmp_path / 'shared')

        #: When
        model = load_workspace(schemas, documents, skills)

        #: Then
        assert model.load_failures == (
            LoadFailure(CLAUDE_SKILLS_DIR, UnresolvableSkillsDirectory(OsRefusal.PERMISSION_DENIED)),
        ), 'the link that cannot be followed is recorded at the path the agent declares it'
        assert model.sorted_skill_locations == (_skill_location('.agents/skills/commit'),), 'the other skills load'

    @pytest.mark.skipif(os.geteuid() == 0, reason='root ignores directory permissions')
    def test_load_workspace_with_a_skill_entry_that_cannot_be_resolved_records_it_and_lists_the_other_entries(
        self,
        tmp_path: Path,
        schemas: SchemaRepository,
        documents: DocumentRepository,
        skills: SkillRepository,
        lock: Callable[[Path], None],
    ) -> None:
        #: Given
        _write(tmp_path, 'shared/review/SKILL.md')
        _write(tmp_path, '.agents/skills/audit/SKILL.md')
        _write(tmp_path, '.agents/skills/commit/SKILL.md')
        (tmp_path / '.agents' / 'skills' / 'broken').symlink_to('../../shared/review')
        lock(tmp_path / 'shared')

        #: When
        model = load_workspace(schemas, documents, skills)

        #: Then
        assert model.load_failures == (
            LoadFailure(
                RootRelativePath.parse('.agents/skills/broken'), UnresolvableSkillEntry(OsRefusal.PERMISSION_DENIED)
            ),
        ), 'the entry is recorded with its path and the refusal'
        assert model.sorted_skill_locations == (
            _skill_location('.agents/skills/audit'),
            _skill_location('.agents/skills/commit'),
        ), 'the entries on both sides of it are listed'

    @pytest.mark.skipif(os.geteuid() == 0, reason='root ignores directory permissions')
    def test_load_workspace_with_a_skill_file_that_cannot_be_resolved_records_it_and_lists_the_other_skills(
        self,
        tmp_path: Path,
        schemas: SchemaRepository,
        documents: DocumentRepository,
        skills: SkillRepository,
        lock: Callable[[Path], None],
    ) -> None:
        #: Given
        _write(tmp_path, 'texts/REVIEW.md')
        _write(tmp_path, '.agents/skills/commit/SKILL.md')
        (tmp_path / '.agents' / 'skills' / 'review').mkdir()
        (tmp_path / '.agents' / 'skills' / 'review' / 'SKILL.md').symlink_to('../../../texts/REVIEW.md')
        lock(tmp_path / 'texts')

        #: When
        model = load_workspace(schemas, documents, skills)

        #: Then
        assert model.load_failures == (
            LoadFailure(
                RootRelativePath.parse('.agents/skills/review/SKILL.md'),
                UnresolvableSkillFile(
                    RootRelativePath.parse('.agents/skills/review/SKILL.md'), OsRefusal.PERMISSION_DENIED
                ),
            ),
        ), 'the SKILL.md is recorded with its path and the refusal'
        assert model.sorted_skill_locations == (_skill_location('.agents/skills/commit'),), 'the other skill is listed'

    @pytest.mark.skipif(os.geteuid() == 0, reason='root ignores directory permissions')
    def test_load_workspace_with_an_unlistable_skill_directory_records_it_and_lists_the_other_skills(
        self,
        tmp_path: Path,
        schemas: SchemaRepository,
        documents: DocumentRepository,
        skills: SkillRepository,
        lock: Callable[[Path], None],
    ) -> None:
        #: Given
        _write(tmp_path, '.agents/skills/commit/SKILL.md')
        (tmp_path / '.agents' / 'skills' / 'review').mkdir()
        lock(tmp_path / '.agents' / 'skills' / 'review')

        #: When
        model = load_workspace(schemas, documents, skills)

        #: Then
        assert model.load_failures == (
            LoadFailure(
                RootRelativePath.parse('.agents/skills/review'),
                UnlistableSkillDirectory(RootRelativePath.parse('.agents/skills/review'), OsRefusal.PERMISSION_DENIED),
            ),
        ), 'the skill directory is recorded with its path and the refusal'
        assert model.sorted_skill_locations == (_skill_location('.agents/skills/commit'),), 'the other skill is listed'

    @pytest.mark.skipif(os.geteuid() == 0, reason='root ignores directory permissions')
    def test_load_workspace_with_two_skill_entries_linked_to_one_unlistable_directory_records_each_entry(
        self,
        tmp_path: Path,
        schemas: SchemaRepository,
        documents: DocumentRepository,
        skills: SkillRepository,
        lock: Callable[[Path], None],
    ) -> None:
        #: Given
        (tmp_path / 'shared' / 'review').mkdir(parents=True)
        (tmp_path / '.agents' / 'skills').mkdir(parents=True)
        (tmp_path / '.agents' / 'skills' / 'first').symlink_to('../../shared/review')
        (tmp_path / '.agents' / 'skills' / 'second').symlink_to('../../shared/review')
        lock(tmp_path / 'shared' / 'review')
        target = RootRelativePath.parse('shared/review')
        refusal = OsRefusal.PERMISSION_DENIED

        #: When
        model = load_workspace(schemas, documents, skills)

        #: Then
        assert model.load_failures == (
            LoadFailure(RootRelativePath.parse('.agents/skills/first'), UnlistableSkillDirectory(target, refusal)),
            LoadFailure(RootRelativePath.parse('.agents/skills/second'), UnlistableSkillDirectory(target, refusal)),
        ), 'each entry is a failure at the entry an agent reaches, and the place its link leads to is kept apart'

    @pytest.mark.skipif(os.geteuid() == 0, reason='root ignores directory permissions')
    def test_load_workspace_with_a_linked_skills_directory_that_cannot_be_listed_records_it_at_the_declared_path(
        self,
        tmp_path: Path,
        schemas: SchemaRepository,
        documents: DocumentRepository,
        skills: SkillRepository,
        lock: Callable[[Path], None],
    ) -> None:
        #: Given
        (tmp_path / 'shared' / 'skills').mkdir(parents=True)
        (tmp_path / '.claude').mkdir()
        (tmp_path / '.claude' / 'skills').symlink_to('../shared/skills')
        lock(tmp_path / 'shared' / 'skills')

        #: When
        model = load_workspace(schemas, documents, skills)

        #: Then
        assert model.load_failures == (
            LoadFailure(
                CLAUDE_SKILLS_DIR,
                UnlistableSkillsDirectory(RootRelativePath.parse('shared/skills'), OsRefusal.PERMISSION_DENIED),
            ),
        ), 'the failure is filed at the directory the agent declares, with the directory its link leads to kept'

    def test_load_model_with_equal_failures_in_two_workspaces_gives_equal_governances(
        self, tmp_path: Path, tmp_path_factory: pytest.TempPathFactory
    ) -> None:
        #: Given
        other = tmp_path_factory.mktemp('other')
        for root in (tmp_path, other):
            _write_tree(root, prose=('code',), schemas=(), documents=('code/logging.md',))
            _write(root, 'docs/__meta__/code.structure.json', 'not json')
        ref = DocumentRef(CODE, AspectFilename.parse('logging'))

        #: When
        first = load_model(DiskFileSystem(tmp_path)).find_governance(ref)
        second = load_model(DiskFileSystem(other)).find_governance(ref)

        #: Then
        assert first is not None, 'the document is governed'
        assert first == second, 'a failure compares by its path and condition, so the governances are equal'

    def test_load_model_with_different_failures_gives_unequal_governances(
        self, tmp_path: Path, tmp_path_factory: pytest.TempPathFactory
    ) -> None:
        #: Given
        other = tmp_path_factory.mktemp('other')
        for root, content in ((tmp_path, 'not json'), (other, '{}')):
            _write_tree(root, prose=('code',), schemas=(), documents=('code/logging.md',))
            _write(root, 'docs/__meta__/code.structure.json', content)
        ref = DocumentRef(CODE, AspectFilename.parse('logging'))

        #: When
        first = load_model(DiskFileSystem(tmp_path)).find_governance(ref)
        second = load_model(DiskFileSystem(other)).find_governance(ref)

        #: Then
        assert first != second, 'a changed condition changes the governance, so what it governs is judged again'
