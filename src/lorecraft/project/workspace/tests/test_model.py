"""Workspace model queries and invariants over hand-built in-memory models.

Nothing here touches the disk: every spec, corpus and ref is constructed directly, with the
structure specification paths standing in for the files the loader would have read.
"""

from dataclasses import replace
from pathlib import PurePosixPath
from typing import Final

import pytest

from lorecraft.agents import AgentName
from lorecraft.core.path import RootRelativePath
from lorecraft.project.aspect import AspectFilename, AspectNamespace
from lorecraft.project.corpus import CorpusName
from lorecraft.project.document.ref import DocumentRef
from lorecraft.project.layout import SPECS_DIR
from lorecraft.project.schemas import (
    CorpusSpecName,
    FrontmatterSchema,
    NamespaceSpecName,
    StructureSpec,
    parse_spec_name,
)
from lorecraft.project.skill import NamedDir, OutsideSymlink, SkillLocation, SkillRef, SkillsDir
from lorecraft.vfs import ResolvedPath, RootExit

from ..model import Corpus, CorpusSpec, Governance, NamespaceSpec, WorkspaceModel, namespace_order_key

CODE: Final[CorpusName] = CorpusName.parse('code')
FEAT: Final[CorpusName] = CorpusName.parse('feat')


def _corpus_spec(name: str, *, frontmatter: bool = True, structure: bool = False) -> CorpusSpec:
    """A corpus spec at `docs/__meta__/<name>.md`, with `<name>.structure.json` beside it when either flag is set.

    Args:
        name: Corpus name, such as `code`, which is the specification name.
        frontmatter: Whether the structure file states a frontmatter schema.
        structure: Whether the structure file forbids empty sections.
    """
    spec_name = parse_spec_name(name)
    assert isinstance(spec_name, CorpusSpecName), f'{name} is not a corpus spec name'
    files, structure_spec = _spec_files(name, frontmatter=frontmatter, structure=structure)
    return CorpusSpec(name=spec_name, files=files, structure=structure_spec)


def _namespace_spec(name: str, *, frontmatter: bool = True, structure: bool = False) -> NamespaceSpec:
    """A namespace spec at `docs/__meta__/<name>.md`, with `<name>.structure.json` beside it when either flag is set.

    Args:
        name: Specification name, such as `code-python`: the corpus, a hyphen, then the namespace.
        frontmatter: Whether the structure file states a frontmatter schema.
        structure: Whether the structure file forbids empty sections.
    """
    spec_name = parse_spec_name(name)
    assert isinstance(spec_name, NamespaceSpecName), f'{name} is not a namespace spec name'
    files, structure_spec = _spec_files(name, frontmatter=frontmatter, structure=structure)
    return NamespaceSpec(name=spec_name, files=files, structure=structure_spec)


def _spec_files(
    name: str, *, frontmatter: bool, structure: bool
) -> tuple[tuple[RootRelativePath, ...], StructureSpec | None]:
    """The files at a specification name and the structure specification decoded from them.

    The files are `<name>.md`, and `<name>.structure.json` when either flag is set. Its `frontmatter` key states a
    schema when `frontmatter` is set, and it forbids empty sections when `structure` is.

    Args:
        name: Specification name, such as `code` or `code-python`.
        frontmatter: Whether the structure file states a frontmatter schema.
        structure: Whether the structure file forbids empty sections.
    """
    files = [SPECS_DIR / f'{name}.md']
    structure_spec: StructureSpec | None = None
    if frontmatter or structure:
        path = SPECS_DIR / f'{name}.structure.json'
        frontmatter_schema: FrontmatterSchema | None = None
        if frontmatter:
            frontmatter_schema = FrontmatterSchema(path=path, schema={'type': 'object'})
        structure_spec = StructureSpec(
            path=path,
            title=None,
            forbid_empty_sections=structure,
            outline=(),
            forbidden=(),
            tokens=None,
            frontmatter=frontmatter_schema,
        )
        files.append(path)
    return tuple(sorted(files, key=str)), structure_spec


def _ref(corpus: str, filename: str) -> DocumentRef:
    return DocumentRef(CorpusName.parse(corpus), AspectFilename.parse(filename))


def _code_model(
    corpus_spec: CorpusSpec, namespace_specs: tuple[NamespaceSpec, ...], filenames: tuple[str, ...]
) -> WorkspaceModel:
    """A model with the single corpus `code`, its corpus spec and its namespace specs.

    Args:
        corpus_spec: The spec of the `code` corpus.
        namespace_specs: The namespace specs narrowing it, which must already be broad to narrow.
        filenames: Stems of the documents the corpus lists, each parsed as a `code` document.
    """
    corpus = Corpus(
        name=CODE,
        corpus_spec=corpus_spec,
        namespace_specs=namespace_specs,
        documents=tuple(_ref('code', filename) for filename in filenames),
    )
    return WorkspaceModel(corpora=(corpus,), skills_dirs=(), skill_locations=(), named_dirs=(), outside_symlinks=())


@pytest.mark.unit
class TestGovernance:
    def test_governance_with_the_corpus_spec_alone_returns_the_corpus_spec(self) -> None:
        #: Given
        corpus_spec = _corpus_spec('code')
        namespace_specs = ()
        filename = 'logging'
        model = _code_model(corpus_spec, namespace_specs, (filename,))
        ref = _ref('code', filename)

        #: When
        governance = model.governance(ref)

        #: Then
        assert governance.ref == ref, 'the governance names the logging document it was asked about'
        assert tuple(str(spec.name) for spec in governance.specs()) == ('code',), (
            'the corpus spec alone governs a document when the corpus has no namespace spec'
        )

    def test_governance_with_nested_namespaces_returns_the_matching_namespaces_broad_to_narrow(self) -> None:
        #: Given
        corpus_spec = _corpus_spec('code')
        namespace_specs = (
            _namespace_spec('code-pattern'),
            _namespace_spec('code-python'),
            _namespace_spec('code-python-errors'),
        )
        filename = 'python-errors-reporting'
        model = _code_model(corpus_spec, namespace_specs, (filename,))
        ref = _ref('code', filename)

        #: When
        governance = model.governance(ref)

        #: Then
        assert governance.ref == ref, 'the governance names the python-errors-reporting document it was asked about'
        assert tuple(str(spec.name) for spec in governance.specs()) == (
            'code',
            'code-python',
            'code-python-errors',
        ), 'the corpus spec comes first, then python and python-errors broad to narrow, and pattern does not match'

    def test_governance_with_a_namespace_equal_to_the_filename_includes_that_namespace(self) -> None:
        #: Given
        corpus_spec = _corpus_spec('code')
        namespace_specs = (_namespace_spec('code-python'),)
        filename = 'python'
        model = _code_model(corpus_spec, namespace_specs, (filename,))
        ref = _ref('code', filename)

        #: When
        governance = model.governance(ref)

        #: Then
        assert governance.ref == ref, 'the governance names the python document it was asked about'
        assert tuple(str(spec.name) for spec in governance.specs()) == ('code', 'code-python'), (
            'a namespace equal to the whole filename governs the document after the corpus spec'
        )

    def test_governance_with_a_namespace_that_is_only_a_prefix_excludes_that_namespace(self) -> None:
        #: Given
        corpus_spec = _corpus_spec('code')
        namespace_specs = (_namespace_spec('code-python'),)
        filename = 'pythonic'
        model = _code_model(corpus_spec, namespace_specs, (filename,))
        ref = _ref('code', filename)

        #: When
        governance = model.governance(ref)

        #: Then
        assert governance.ref == ref, 'the governance names the pythonic document it was asked about'
        assert tuple(str(spec.name) for spec in governance.specs()) == ('code',), (
            'python is not a hyphen-delimited prefix of pythonic, so only the corpus spec governs'
        )

    def test_governance_with_a_prose_only_corpus_spec_still_lists_the_corpus_spec_first(self) -> None:
        #: Given
        corpus_spec = _corpus_spec('code', frontmatter=False)
        namespace_specs = (_namespace_spec('code-python'),)
        filename = 'python-typing'
        model = _code_model(corpus_spec, namespace_specs, (filename,))
        ref = _ref('code', filename)

        #: When
        governance = model.governance(ref)

        #: Then
        assert governance.ref == ref, 'the governance names the python-typing document it was asked about'
        assert tuple(str(spec.name) for spec in governance.specs()) == ('code', 'code-python'), (
            'the corpus spec still governs first even without a structure specification, then the python namespace'
        )

    def test_governance_with_a_prose_only_namespace_includes_the_prose_only_namespace(self) -> None:
        #: Given
        corpus_spec = _corpus_spec('code')
        namespace_specs = (_namespace_spec('code-python', frontmatter=False),)
        filename = 'python-typing'
        model = _code_model(corpus_spec, namespace_specs, (filename,))
        ref = _ref('code', filename)

        #: When
        governance = model.governance(ref)

        #: Then
        assert governance.ref == ref, 'the governance names the python-typing document it was asked about'
        assert tuple(str(spec.name) for spec in governance.specs()) == ('code', 'code-python'), (
            'a prose-only namespace spec still governs the document after the corpus spec'
        )

    def test_frontmatter_schemas_with_the_corpus_spec_alone_returns_the_corpus_schema(self) -> None:
        #: Given
        corpus_spec = _corpus_spec('code')
        namespace_specs = ()
        filename = 'logging'
        model = _code_model(corpus_spec, namespace_specs, (filename,))
        governance = model.governance(_ref('code', filename))

        #: When
        schemas = governance.frontmatter_schemas()

        #: Then
        assert tuple(schema.path for schema in schemas) == (SPECS_DIR / 'code.structure.json',), (
            'the corpus frontmatter schema is the only one when the corpus spec governs alone'
        )

    def test_frontmatter_schemas_with_nested_namespaces_returns_the_schemas_broad_to_narrow(self) -> None:
        #: Given
        corpus_spec = _corpus_spec('code')
        namespace_specs = (
            _namespace_spec('code-pattern'),
            _namespace_spec('code-python'),
            _namespace_spec('code-python-errors'),
        )
        filename = 'python-errors-reporting'
        model = _code_model(corpus_spec, namespace_specs, (filename,))
        governance = model.governance(_ref('code', filename))

        #: When
        schemas = governance.frontmatter_schemas()

        #: Then
        assert tuple(schema.path for schema in schemas) == (
            SPECS_DIR / 'code.structure.json',
            SPECS_DIR / 'code-python.structure.json',
            SPECS_DIR / 'code-python-errors.structure.json',
        ), 'the frontmatter schemas follow the corpus, python and python-errors specs, broad to narrow'

    def test_frontmatter_schemas_with_a_namespace_equal_to_the_filename_includes_the_namespace_schema(self) -> None:
        #: Given
        corpus_spec = _corpus_spec('code')
        namespace_specs = (_namespace_spec('code-python'),)
        filename = 'python'
        model = _code_model(corpus_spec, namespace_specs, (filename,))
        governance = model.governance(_ref('code', filename))

        #: When
        schemas = governance.frontmatter_schemas()

        #: Then
        assert tuple(schema.path for schema in schemas) == (
            SPECS_DIR / 'code.structure.json',
            SPECS_DIR / 'code-python.structure.json',
        ), 'the namespace schema follows the corpus schema when the namespace equals the filename'

    def test_frontmatter_schemas_with_a_namespace_that_is_only_a_prefix_excludes_the_namespace_schema(self) -> None:
        #: Given
        corpus_spec = _corpus_spec('code')
        namespace_specs = (_namespace_spec('code-python'),)
        filename = 'pythonic'
        model = _code_model(corpus_spec, namespace_specs, (filename,))
        governance = model.governance(_ref('code', filename))

        #: When
        schemas = governance.frontmatter_schemas()

        #: Then
        assert tuple(schema.path for schema in schemas) == (SPECS_DIR / 'code.structure.json',), (
            'the python namespace schema does not apply to pythonic, only the corpus schema does'
        )

    def test_frontmatter_schemas_with_a_prose_only_corpus_spec_returns_no_schemas(self) -> None:
        #: Given
        corpus_spec = _corpus_spec('code', frontmatter=False)
        namespace_specs = (_namespace_spec('code-python'),)
        filename = 'python-typing'
        model = _code_model(corpus_spec, namespace_specs, (filename,))
        governance = model.governance(_ref('code', filename))

        #: When
        schemas = governance.frontmatter_schemas()

        #: Then
        assert schemas == (), (
            'a namespace never governs alone: no frontmatter schema applies without a corpus structure specification'
        )

    def test_frontmatter_schemas_with_a_corpus_structure_without_a_schema_returns_no_schemas(self) -> None:
        #: Given
        corpus_spec = _corpus_spec('code', frontmatter=False, structure=True)
        namespace_specs = (_namespace_spec('code-python'),)
        filename = 'python-typing'
        model = _code_model(corpus_spec, namespace_specs, (filename,))
        governance = model.governance(_ref('code', filename))

        #: When
        schemas = governance.frontmatter_schemas()

        #: Then
        assert schemas == (), (
            'a namespace never governs alone: no frontmatter schema applies when the corpus structure states none'
        )

    def test_frontmatter_schemas_with_a_namespace_structure_without_a_schema_adds_no_namespace_schema(self) -> None:
        #: Given
        corpus_spec = _corpus_spec('code')
        namespace_specs = (_namespace_spec('code-python', frontmatter=False, structure=True),)
        filename = 'python-typing'
        model = _code_model(corpus_spec, namespace_specs, (filename,))
        governance = model.governance(_ref('code', filename))

        #: When
        schemas = governance.frontmatter_schemas()

        #: Then
        assert tuple(schema.path for schema in schemas) == (SPECS_DIR / 'code.structure.json',), (
            'a namespace structure stating no frontmatter schema adds none, so only the corpus schema applies'
        )

    def test_structure_specs_with_nested_namespaces_returns_the_structures_broad_to_narrow(self) -> None:
        #: Given
        corpus_spec = _corpus_spec('code', structure=True)
        namespace_specs = (_namespace_spec('code-python', structure=True),)
        filename = 'python-typing'
        model = _code_model(corpus_spec, namespace_specs, (filename,))
        governance = model.governance(_ref('code', filename))

        #: When
        structure_specs = governance.structure_specs()

        #: Then
        assert tuple(structure_spec.path for structure_spec in structure_specs) == (
            SPECS_DIR / 'code.structure.json',
            SPECS_DIR / 'code-python.structure.json',
        ), 'the structure specifications follow the corpus and python specs, broad to narrow'

    def test_structure_specs_with_a_corpus_spec_without_a_structure_returns_no_structures(self) -> None:
        #: Given
        corpus_spec = _corpus_spec('code', frontmatter=False)
        namespace_specs = (_namespace_spec('code-python', structure=True),)
        filename = 'python-typing'
        model = _code_model(corpus_spec, namespace_specs, (filename,))
        governance = model.governance(_ref('code', filename))

        #: When
        structure_specs = governance.structure_specs()

        #: Then
        assert structure_specs == (), (
            'a namespace never governs alone: no structure applies when the corpus spec has no structure specification'
        )

    def test_structure_specs_with_a_namespace_without_a_structure_returns_the_corpus_structure(self) -> None:
        #: Given
        corpus_spec = _corpus_spec('code', structure=True)
        namespace_specs = (_namespace_spec('code-python', frontmatter=False),)
        filename = 'python-typing'
        model = _code_model(corpus_spec, namespace_specs, (filename,))
        governance = model.governance(_ref('code', filename))

        #: When
        structure_specs = governance.structure_specs()

        #: Then
        assert tuple(structure_spec.path for structure_spec in structure_specs) == (
            SPECS_DIR / 'code.structure.json',
        ), 'a namespace spec without a structure file adds nothing, so only the corpus structure applies'

    def test_structure_specs_with_a_corpus_structure_stating_only_frontmatter_returns_both_structures(self) -> None:
        #: Given
        # the corpus file states only a frontmatter schema; the namespace file states only an outline rule
        corpus_spec = _corpus_spec('code')
        namespace_specs = (_namespace_spec('code-python', frontmatter=False, structure=True),)
        filename = 'python-typing'
        model = _code_model(corpus_spec, namespace_specs, (filename,))
        governance = model.governance(_ref('code', filename))

        #: When
        structure_specs = governance.structure_specs()

        #: Then
        assert tuple(structure_spec.path for structure_spec in structure_specs) == (
            SPECS_DIR / 'code.structure.json',
            SPECS_DIR / 'code-python.structure.json',
        ), 'a structure file is a base whatever rule it states, as a tokens-only file is, so the namespace applies'

    def test_governance_with_a_ref_of_a_corpus_the_model_lacks_raises_value_error(self) -> None:
        #: Given
        model = _code_model(_corpus_spec('code'), (), ('logging',))
        foreign_ref = _ref('feat', 'cli-check')

        #: When
        with pytest.raises(ValueError, match='cli-check'):
            model.governance(foreign_ref)

        #: Then
        assert model.find_corpus(FEAT) is None, 'the model has no feat corpus to answer for'


@pytest.mark.unit
class TestCorpus:
    def test_directory_of_a_corpus_returns_its_directory_under_docs(self) -> None:
        #: Given
        corpus = Corpus(name=CODE, corpus_spec=_corpus_spec('code'), namespace_specs=(), documents=())

        #: When
        directory = corpus.directory

        #: Then
        assert directory == RootRelativePath.parse('docs/code'), 'a corpus is the directory under docs/ at its name'

    def test_governance_with_a_ref_of_another_corpus_raises_value_error(self) -> None:
        #: Given
        corpus = Corpus(name=CODE, corpus_spec=_corpus_spec('code'), namespace_specs=(), documents=())
        foreign_ref = _ref('feat', 'cli-check')

        #: When
        with pytest.raises(ValueError, match='cli-check'):
            corpus.governance(foreign_ref)

        #: Then
        assert corpus.name != foreign_ref.corpus, 'the rejected ref belongs to another corpus'

    def test_governance_with_a_matching_namespace_returns_a_governance_value(self) -> None:
        #: Given
        corpus = Corpus(
            name=CODE,
            corpus_spec=_corpus_spec('code'),
            namespace_specs=(_namespace_spec('code-python'),),
            documents=(),
        )
        ref = _ref('code', 'python-typing')

        #: When
        governance = corpus.governance(ref)

        #: Then
        assert governance == Governance(ref, _corpus_spec('code'), (_namespace_spec('code-python'),)), (
            'the governance carries the ref and the corpus spec followed by the matching namespace spec'
        )

    def test_construct_with_the_corpus_spec_of_another_corpus_raises_value_error(self) -> None:
        #: Given
        feat_spec = _corpus_spec('feat')

        #: When
        with pytest.raises(ValueError, match='code'):
            Corpus(name=CODE, corpus_spec=feat_spec, namespace_specs=(), documents=())

        #: Then
        assert feat_spec.name.corpus == FEAT, 'the rejected spec belongs to another corpus'

    def test_construct_with_a_namespace_spec_of_another_corpus_raises_value_error(self) -> None:
        #: Given
        feat_namespace = _namespace_spec('feat-cli')

        #: When
        with pytest.raises(ValueError, match='code'):
            Corpus(name=CODE, corpus_spec=_corpus_spec('code'), namespace_specs=(feat_namespace,), documents=())

        #: Then
        assert feat_namespace.name.corpus == FEAT, 'the rejected namespace spec belongs to another corpus'

    def test_construct_with_a_narrower_namespace_before_a_broader_one_raises_value_error(self) -> None:
        #: Given
        broad_to_narrow = (_namespace_spec('code-python'), _namespace_spec('code-python-errors'))
        narrow_first = (broad_to_narrow[1], broad_to_narrow[0])

        #: When
        with pytest.raises(ValueError, match='code'):
            Corpus(name=CODE, corpus_spec=_corpus_spec('code'), namespace_specs=narrow_first, documents=())

        #: Then
        assert narrow_first != broad_to_narrow, 'the rejected order is the accepted order reversed'

    def test_construct_with_sibling_namespaces_out_of_value_order_raises_value_error(self) -> None:
        #: Given
        value_order = (_namespace_spec('code-pattern'), _namespace_spec('code-python'))
        unsorted_siblings = (value_order[1], value_order[0])

        #: When
        with pytest.raises(ValueError, match='code'):
            Corpus(name=CODE, corpus_spec=_corpus_spec('code'), namespace_specs=unsorted_siblings, documents=())

        #: Then
        assert unsorted_siblings != value_order, 'siblings with the same segment count are accepted in value order'

    def test_construct_with_a_document_of_another_corpus_raises_value_error(self) -> None:
        #: Given
        foreign_ref = _ref('feat', 'cli-check')

        #: When
        with pytest.raises(ValueError, match='cli-check'):
            Corpus(name=CODE, corpus_spec=_corpus_spec('code'), namespace_specs=(), documents=(foreign_ref,))

        #: Then
        assert foreign_ref.corpus == FEAT, 'the rejected ref belongs to another corpus'


@pytest.mark.unit
class TestNamespaceSpec:
    def test_is_governing_with_a_filename_its_namespace_prefixes_returns_true(self) -> None:
        #: Given
        namespace_spec = _namespace_spec('code-python')
        filename = AspectFilename.parse('python-typing')

        #: When
        governs = namespace_spec.is_governing(filename)

        #: Then
        assert governs, 'python is a hyphen-delimited prefix of python-typing, so the namespace spec governs it'

    def test_is_governing_with_a_filename_its_namespace_does_not_prefix_returns_false(self) -> None:
        #: Given
        namespace_spec = _namespace_spec('code-python')
        filename = AspectFilename.parse('logging')

        #: When
        governs = namespace_spec.is_governing(filename)

        #: Then
        assert not governs, 'python is no prefix of logging, so the namespace spec does not govern it'


@pytest.mark.unit
class TestNamespaceOrderKey:
    def test_namespace_order_key_with_a_one_word_namespace_returns_zero_then_value(self) -> None:
        #: Given
        namespace = AspectNamespace.parse('python')

        #: When
        key = namespace_order_key(namespace)

        #: Then
        assert key == (0, 'python'), 'a one-word namespace has no hyphen and sorts by its value'

    def test_namespace_order_key_with_a_two_word_namespace_returns_one_then_value(self) -> None:
        #: Given
        namespace = AspectNamespace.parse('python-errors')

        #: When
        key = namespace_order_key(namespace)

        #: Then
        assert key == (1, 'python-errors'), 'the key is the hyphen count of the namespace, then its value'


@pytest.fixture(scope='function')
def two_corpora_model() -> WorkspaceModel:
    """Corpora ``code`` (two documents) and ``feat`` (one document)."""
    code = Corpus(
        name=CODE,
        corpus_spec=_corpus_spec('code'),
        namespace_specs=(),
        documents=(_ref('code', 'logging'), _ref('code', 'python-typing')),
    )
    feat = Corpus(
        name=FEAT,
        corpus_spec=_corpus_spec('feat'),
        namespace_specs=(),
        documents=(_ref('feat', 'cli-check'),),
    )
    return WorkspaceModel(corpora=(code, feat), skills_dirs=(), skill_locations=(), named_dirs=(), outside_symlinks=())


def _regular_skill(directory: str) -> SkillLocation:
    """The location of a skill whose directory and `SKILL.md` are no links.

    Args:
        directory: Root-relative skill directory, such as `.agents/skills/audit`.
    """
    path = RootRelativePath.parse(directory)
    # No link on the way, so the directory and its `SKILL.md` are their own resolved paths.
    return SkillLocation(
        SkillRef(path), resolves_to=ResolvedPath(path), file_resolves_to=ResolvedPath(path / 'SKILL.md')
    )


AUDIT: Final[SkillLocation] = SkillLocation(
    SkillRef(RootRelativePath.parse('.agents/skills/audit')),
    resolves_to=ResolvedPath(RootRelativePath.parse('skills/audit')),
    file_resolves_to=ResolvedPath(RootRelativePath.parse('shared/audit.md')),
)
"""A skill linked to ``skills/audit/``, whose ``SKILL.md`` is a link to ``shared/audit.md``."""

REVIEW: Final[SkillLocation] = _regular_skill('.agents/skills/review')
"""A skill in a regular directory."""

REVIEW_ALIAS: Final[SkillLocation] = SkillLocation(
    SkillRef(RootRelativePath.parse('.agents/skills/reviewer')),
    resolves_to=ResolvedPath(RootRelativePath.parse('.agents/skills/review')),
    file_resolves_to=ResolvedPath(RootRelativePath.parse('.agents/skills/review/SKILL.md')),
)
"""A second entry linked to the ``review`` skill's directory."""

GAMMA: Final[SkillLocation] = _regular_skill('skills/gamma')
"""A skill in `skills/`, a directory no agent reads, which a command names."""


@pytest.fixture(scope='function')
def skills_model() -> WorkspaceModel:
    """No corpus, two agents reading `.agents/skills`, the three skills above in it, and `skills/` named.

    One of the agents reads it through the `.claude/skills` link. A command names `skills`, which holds `gamma`.
    """
    universal = ResolvedPath(RootRelativePath.parse('.agents/skills'))
    return WorkspaceModel(
        corpora=(),
        skills_dirs=(
            SkillsDir(
                agent=AgentName('claude-code'), path=RootRelativePath.parse('.claude/skills'), resolves_to=universal
            ),
            SkillsDir(agent=AgentName('codex'), path=universal, resolves_to=universal),
        ),
        skill_locations=(AUDIT, REVIEW, REVIEW_ALIAS),
        named_dirs=(NamedDir(RootRelativePath.parse('skills'), skills=(GAMMA,), outside_symlinks=()),),
        outside_symlinks=(),
    )


@pytest.mark.unit
class TestWorkspaceModel:
    def test_find_corpus_with_a_listed_name_returns_that_corpus(self, two_corpora_model: WorkspaceModel) -> None:
        #: Given
        name = FEAT

        #: When
        corpus = two_corpora_model.find_corpus(name)

        #: Then
        assert corpus is not None and corpus.name == FEAT, 'the corpus is found by name'

    def test_find_corpus_with_an_unlisted_name_returns_none(self, two_corpora_model: WorkspaceModel) -> None:
        #: Given
        name = CorpusName.parse('blog')

        #: When
        corpus = two_corpora_model.find_corpus(name)

        #: Then
        assert corpus is None, 'a name the model does not list has no corpus'

    def test_documents_with_two_corpora_returns_refs_in_corpus_then_filename_order(
        self, two_corpora_model: WorkspaceModel
    ) -> None:
        #: Given
        model = two_corpora_model

        #: When
        refs = model.documents()

        #: Then
        assert refs == (_ref('code', 'logging'), _ref('code', 'python-typing'), _ref('feat', 'cli-check')), (
            'every code ref precedes every feat ref, each corpus in its stored filename order'
        )

    def test_find_document_with_the_path_of_a_listed_document_returns_its_ref(
        self, two_corpora_model: WorkspaceModel
    ) -> None:
        #: Given
        path = RootRelativePath.parse('docs/feat/cli-check.md')

        #: When
        ref = two_corpora_model.find_document(path)

        #: Then
        assert ref == _ref('feat', 'cli-check'), 'the ref whose path equals the argument is returned'

    def test_find_document_with_a_path_the_model_does_not_list_returns_none(
        self, two_corpora_model: WorkspaceModel
    ) -> None:
        #: Given
        path = RootRelativePath.parse('docs/code/cli-check.md')

        #: When
        ref = two_corpora_model.find_document(path)

        #: Then
        assert ref is None, 'a filename listed under another corpus does not match'

    def test_skills_with_three_skills_returns_their_refs_in_directory_order(self, skills_model: WorkspaceModel) -> None:
        #: Given
        model = skills_model

        #: When
        refs = model.skills()

        #: Then
        assert refs == (AUDIT.ref, REVIEW.ref, REVIEW_ALIAS.ref), (
            "one ref per location of the agents' skills, in the stored order, and none of a named directory"
        )

    def test_eq_with_a_skill_link_retargeted_under_the_same_ref_returns_false(
        self, skills_model: WorkspaceModel
    ) -> None:
        #: Given
        retargeted = SkillLocation(
            AUDIT.ref,
            resolves_to=ResolvedPath(RootRelativePath.parse('skills/review')),
            file_resolves_to=ResolvedPath(RootRelativePath.parse('skills/review/SKILL.md')),
        )
        other = replace(skills_model, skill_locations=(retargeted, REVIEW, REVIEW_ALIAS))

        #: When
        equal = other == skills_model

        #: Then
        assert equal is False, 'the skill keeps its ref, and the model still changes with where its link leads'

    def test_skill_location_with_a_listed_skill_returns_where_its_files_live(
        self, skills_model: WorkspaceModel
    ) -> None:
        #: Given
        ref = AUDIT.ref

        #: When
        location = skills_model.skill_location(ref)

        #: Then
        assert location == AUDIT, 'the location the model records for the ref is returned'

    def test_skill_location_with_a_skill_in_a_named_directory_returns_where_its_files_live(
        self, skills_model: WorkspaceModel
    ) -> None:
        #: Given
        ref = GAMMA.ref

        #: When
        location = skills_model.skill_location(ref)

        #: Then
        assert location == GAMMA, 'the location a named directory records for the ref is returned'

    def test_skill_location_with_a_skill_the_model_lacks_raises_value_error(self, skills_model: WorkspaceModel) -> None:
        #: Given
        ref = SkillRef(RootRelativePath.parse('.agents/skills/commit'))

        #: When
        with pytest.raises(ValueError) as exc_info:
            skills_model.skill_location(ref)

        #: Then
        assert '.agents/skills/commit' in str(exc_info.value), 'the error names the skill the model does not list'

    def test_find_skill_with_the_entry_of_a_regular_skill_returns_its_ref(self, skills_model: WorkspaceModel) -> None:
        #: Given
        directory = RootRelativePath.parse('.agents/skills/review')

        #: When
        ref = skills_model.find_skill(directory)

        #: Then
        assert ref == REVIEW.ref, 'the skill listed at the entry is returned, not the entry linked to it'

    def test_find_skill_with_the_entry_of_a_linked_skill_returns_its_ref(self, skills_model: WorkspaceModel) -> None:
        #: Given
        directory = RootRelativePath.parse('.agents/skills/reviewer')

        #: When
        ref = skills_model.find_skill(directory)

        #: Then
        assert ref == REVIEW_ALIAS.ref, 'a linked entry is found by its own name'

    def test_find_skill_with_the_resolved_directory_a_linked_skill_leads_to_returns_none(
        self, skills_model: WorkspaceModel
    ) -> None:
        #: Given
        directory = RootRelativePath.parse('skills/audit')

        #: When
        ref = skills_model.find_skill(directory)

        #: Then
        assert ref is None, 'the directory a link leads to is no entry of a skills directory'

    def test_find_skill_with_a_skill_in_a_named_directory_returns_none(self, skills_model: WorkspaceModel) -> None:
        #: Given
        directory = RootRelativePath.parse('skills/gamma')

        #: When
        ref = skills_model.find_skill(directory)

        #: Then
        assert ref is None, "only the agents' skills are found by their entry"

    def test_find_skill_with_a_path_that_is_no_skill_returns_none(self, skills_model: WorkspaceModel) -> None:
        #: Given
        directory = RootRelativePath.parse('.agents/skills')

        #: When
        ref = skills_model.find_skill(directory)

        #: Then
        assert ref is None, 'the skills directory itself is no skill'

    def test_has_skills_dir_with_the_resolved_directory_agents_read_returns_true(
        self, skills_model: WorkspaceModel
    ) -> None:
        #: Given
        resolved_path = ResolvedPath(RootRelativePath.parse('.agents/skills'))

        #: When
        listed = skills_model.has_skills_dir(resolved_path)

        #: Then
        assert listed is True, 'a skills directory leads to the resolved directory, directly or through a link'

    def test_has_skills_dir_with_a_linked_skills_directory_returns_false(self, skills_model: WorkspaceModel) -> None:
        #: Given
        # Typed as resolved only to be asked: the method compares lexically and never checks the claim.
        path = ResolvedPath(RootRelativePath.parse('.claude/skills'))

        #: When
        listed = skills_model.has_skills_dir(path)

        #: Then
        assert listed is False, 'a link is no resolved path, so no skills directory resolves to it'

    def test_has_skills_dir_with_a_directory_no_agent_reads_returns_false(self, skills_model: WorkspaceModel) -> None:
        #: Given
        path = ResolvedPath(RootRelativePath.parse('skills'))

        #: When
        listed = skills_model.has_skills_dir(path)

        #: Then
        assert listed is False, 'a directory skills link into is no skills directory'

    def test_skills_in_with_a_skills_directory_returns_every_skill_listed_there(
        self, skills_model: WorkspaceModel
    ) -> None:
        #: Given
        resolved_path = ResolvedPath(RootRelativePath.parse('.agents/skills'))

        #: When
        refs = skills_model.skills_in(resolved_path)

        #: Then
        assert refs == (AUDIT.ref, REVIEW.ref, REVIEW_ALIAS.ref), (
            'every entry of the resolved directory, linked or not, in the model order'
        )

    def test_skills_in_with_a_skills_directory_holding_no_skill_returns_empty(
        self, skills_model: WorkspaceModel
    ) -> None:
        #: Given
        model = replace(skills_model, skill_locations=())
        resolved_path = ResolvedPath(RootRelativePath.parse('.agents/skills'))

        #: When
        refs = model.skills_in(resolved_path)

        #: Then
        assert refs == (), 'no skill is listed in a skills directory that holds none'

    def test_find_named_dir_with_a_named_directory_returns_its_record(self, skills_model: WorkspaceModel) -> None:
        #: Given
        path = RootRelativePath.parse('skills')

        #: When
        named_dir = skills_model.find_named_dir(path)

        #: Then
        assert named_dir == NamedDir(path, skills=(GAMMA,), outside_symlinks=()), (
            'the record of the directory named there is returned'
        )

    def test_find_named_dir_with_a_skill_in_a_named_directory_returns_none(self, skills_model: WorkspaceModel) -> None:
        #: Given
        path = RootRelativePath.parse('skills/gamma')

        #: When
        named_dir = skills_model.find_named_dir(path)

        #: Then
        assert named_dir is None, 'only the directory named is found, never a skill inside it'

    def test_has_outside_symlink_with_the_path_an_agent_reaches_it_at_returns_true(
        self, skills_model: WorkspaceModel
    ) -> None:
        #: Given
        entry = RootRelativePath.parse('.agents/skills/x')
        outside = OutsideSymlink(entry, RootExit(entry, PurePosixPath('/opt/team-skills/x')))
        model = replace(skills_model, outside_symlinks=(outside,))

        #: When
        found = model.has_outside_symlink(entry)

        #: Then
        assert found, 'the symlink is found at the path an agent reaches it at'

    def test_has_outside_symlink_with_a_path_below_a_symlink_leading_outside_returns_false(
        self, skills_model: WorkspaceModel
    ) -> None:
        #: Given
        entry = RootRelativePath.parse('.agents/skills/x')
        outside = OutsideSymlink(entry, RootExit(entry, PurePosixPath('/opt/team-skills/x')))
        model = replace(skills_model, outside_symlinks=(outside,))

        #: When
        found = model.has_outside_symlink(entry / 'SKILL.md')

        #: Then
        assert not found, 'a path is compared whole: one below a symlink leading outside is not that symlink'

    def test_locate_skill_files_with_the_file_of_a_regular_skill_returns_every_entry_leading_there(
        self, skills_model: WorkspaceModel
    ) -> None:
        #: Given
        path = ResolvedPath(RootRelativePath.parse('.agents/skills/review/SKILL.md'))

        #: When
        refs = skills_model.locate_skill_files(path)

        #: Then
        assert refs == (REVIEW.ref, REVIEW_ALIAS.ref), (
            'the skill holding the file and the entry linked to it both read it, in the model order'
        )

    def test_locate_skill_files_with_the_file_a_linked_skill_file_leads_to_returns_its_ref(
        self, skills_model: WorkspaceModel
    ) -> None:
        #: Given
        path = ResolvedPath(RootRelativePath.parse('shared/audit.md'))

        #: When
        refs = skills_model.locate_skill_files(path)

        #: Then
        assert refs == (AUDIT.ref,), 'a skill whose SKILL.md is a link is at the file the link leads to'

    def test_locate_skill_files_with_the_file_of_a_skill_in_a_named_directory_returns_its_ref(
        self, skills_model: WorkspaceModel
    ) -> None:
        #: Given
        path = ResolvedPath(RootRelativePath.parse('skills/gamma/SKILL.md'))

        #: When
        refs = skills_model.locate_skill_files(path)

        #: Then
        assert refs == (GAMMA.ref,), 'a skill a named directory holds is located by its SKILL.md too'

    def test_locate_skill_files_with_the_directory_of_a_skill_returns_empty(self, skills_model: WorkspaceModel) -> None:
        #: Given
        path = ResolvedPath(RootRelativePath.parse('skills/audit'))

        #: When
        refs = skills_model.locate_skill_files(path)

        #: Then
        assert refs == (), 'a directory is no SKILL.md, even where a linked skill keeps its files'

    def test_skill_agents_with_two_directories_leading_to_the_skill_returns_both_agents(
        self, skills_model: WorkspaceModel
    ) -> None:
        #: Given
        ref = REVIEW.ref

        #: When
        agents = skills_model.skill_agents(ref)

        #: Then
        assert agents == (AgentName('claude-code'), AgentName('codex')), (
            'an agent reads the skill whether its skills directory is the resolved one or a link to it'
        )

    def test_skill_agents_with_a_skill_no_skills_directory_leads_to_returns_empty(
        self, skills_model: WorkspaceModel
    ) -> None:
        #: Given
        ref = SkillRef(RootRelativePath.parse('skills/review'))

        #: When
        agents = skills_model.skill_agents(ref)

        #: Then
        assert agents == (), 'no agent reads a skill outside every skills directory'


@pytest.mark.unit
class TestDocumentRef:
    def test_path_with_a_code_ref_returns_root_relative_docs_corpus_filename_md(self) -> None:
        #: Given
        ref = _ref('code', 'python-errors-handling')

        #: When
        path = ref.path

        #: Then
        assert path == RootRelativePath.parse('docs/code/python-errors-handling.md'), (
            'the path is root-relative docs/<corpus>/<filename>.md'
        )
