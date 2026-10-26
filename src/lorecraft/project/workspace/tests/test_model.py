"""Workspace model queries and invariants over hand-built in-memory models.

Nothing here touches the disk: every spec, corpus and ref is constructed directly, with the
structure specification paths standing in for the files the loader would have read.
"""

from dataclasses import replace
from pathlib import PurePosixPath
from typing import Final

import pytest

from lorecraft.agents import AgentName
from lorecraft.core.mapping import FrozenMapping
from lorecraft.core.num import NonZeroUnsignedInt
from lorecraft.core.path import PathComponent, RootRelativePath
from lorecraft.project.aspect import AspectFilename, AspectNamespace
from lorecraft.project.corpus import CorpusName
from lorecraft.project.document import (
    DocumentRef,
    InvalidSpecificationNameError,
    MisplacedSpecificationError,
    SpecRef,
)
from lorecraft.project.item import (
    DocumentOrigin,
    ItemRef,
    ItemType,
    SkillEntrypointOrigin,
    SpecOrigin,
    SpecPart,
)
from lorecraft.project.layout import SPECS_DIR
from lorecraft.project.link_target import DocumentDirectory, SkillRoot
from lorecraft.project.schemas import (
    CorpusSpecName,
    FrontmatterSchema,
    NamespaceSpecName,
    SectionEntry,
    SectionName,
    SpecFileType,
    StructureSpec,
    StructureSpecFile,
    parse_spec_name,
    spec_filename,
)
from lorecraft.project.skill import OutsideSymlink, SkillLocation, SkillRef, SkillsDir
from lorecraft.schemas import (
    BuiltinOrigin,
    DuplicateSchemaRefError,
    RepositoryOrigin,
    RepositorySchemaInput,
    SchemaInput,
    SchemaKind,
    SchemaRef,
)
from lorecraft.vfs import ResolvedPath, RootExit
from lorecraft.vfs.view import AbsoluteSymlinkTarget, RelativeSymlinkTarget, SymlinkTarget

from ..failure import FailedStructure
from ..model import (
    BuiltinSpecLayer,
    Corpus,
    CorpusNamespace,
    CorpusSpec,
    DuplicateCorpusNameError,
    DuplicateOutsideSymlinkPathError,
    DuplicateSkillLocationRefError,
    InvalidBuiltinFrontmatterSchemaError,
    MetaCorpusNameMismatchError,
    NamespaceSpec,
    WorkspaceModel,
    namespace_order_key,
)

CODE: Final[CorpusName] = CorpusName.parse('code')
FEAT: Final[CorpusName] = CorpusName.parse('feat')


def _target(raw: str) -> SymlinkTarget:
    """Wrap a target written as it would be by `os.readlink`."""
    target = PurePosixPath(raw)
    if target.is_absolute():
        return AbsoluteSymlinkTarget(target)
    return RelativeSymlinkTarget(target)


def _corpus_spec(name: str, *, frontmatter: bool = True, structure: bool = False) -> CorpusSpec:
    """A corpus spec at `docs/__meta__/<name>.md`, with `<name>.spec.json` beside it when either flag is set.

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
    """A namespace spec at `docs/__meta__/<name>.md`, with `<name>.spec.json` beside it when either flag is set.

    Args:
        name: Specification name, such as `code-python`: the corpus, a hyphen, then the namespace.
        frontmatter: Whether the structure file states a frontmatter schema.
        structure: Whether the structure file forbids empty sections.
    """
    spec_name = parse_spec_name(name)
    assert isinstance(spec_name, NamespaceSpecName), f'{name} is not a namespace spec name'
    files, structure_spec = _spec_files(name, frontmatter=frontmatter, structure=structure)
    return NamespaceSpec(name=spec_name, files=files, structure=structure_spec)


type _NamespaceEntry = tuple[AspectNamespace, CorpusNamespace]
"""A namespace of a corpus and the record the corpus holds for it, as `Corpus.namespaces` keys it."""


def _code_namespace(namespace: str, *, frontmatter: bool = True, structure: bool = False) -> _NamespaceEntry:
    """A namespace of the `code` corpus, with the files `_namespace_spec` gives `code-<namespace>`.

    Args:
        namespace: Namespace after the corpus, such as `python`.
        frontmatter: Whether the structure file states a frontmatter schema.
        structure: Whether the structure file forbids empty sections.
    """
    files, structure_spec = _spec_files(f'code-{namespace}', frontmatter=frontmatter, structure=structure)
    return AspectNamespace.parse(namespace), CorpusNamespace(files=files, structure=structure_spec)


def _spec_files(
    name: str, *, frontmatter: bool, structure: bool
) -> tuple[tuple[RootRelativePath, ...], StructureSpec | None]:
    """The files at a specification name and the structure specification decoded from them.

    The files are `<name>.md`, and `<name>.spec.json` when either flag is set. Its `frontmatter` key states a
    schema when `frontmatter` is set, and it forbids empty sections when `structure` is.

    Args:
        name: Specification name, such as `code` or `code-python`.
        frontmatter: Whether the structure file states a frontmatter schema.
        structure: Whether the structure file forbids empty sections.
    """
    spec_name = parse_spec_name(name)
    files = [SPECS_DIR / PathComponent.parse(spec_filename(spec_name, SpecFileType.PROSE))]
    structure_spec: StructureSpec | None = None
    if frontmatter or structure:
        path = SPECS_DIR / PathComponent.parse(spec_filename(spec_name, SpecFileType.SPEC))
        frontmatter_schema: FrontmatterSchema | None = None
        if frontmatter:
            frontmatter_schema = FrontmatterSchema(schema=FrozenMapping({'type': 'object'}))
        structure_spec = StructureSpec(
            file=StructureSpecFile(path=path, name=spec_name),
            title=None,
            forbid_empty_sections=structure,
            outline=(),
            forbidden=(),
            tokens=None,
            lines=None,
            frontmatter=frontmatter_schema,
            frontmatter_schema_ref=(SchemaRef(SchemaKind.FRONTMATTER, str(spec_name)) if frontmatter else None),
        )
        files.append(path)
    return tuple(sorted(files, key=str)), structure_spec


def _outlined(structure_spec: StructureSpec | FailedStructure | None) -> StructureSpec:
    """The structure specification given, stating an outline of one required section, `Usage`.

    Args:
        structure_spec: A structure specification; only one can state an outline.
    """
    assert isinstance(structure_spec, StructureSpec), 'only a structure specification states an outline'
    return replace(structure_spec, outline=(SectionEntry(name=SectionName('Usage')),))


def _ref(corpus: str, filename: str) -> DocumentRef:
    return DocumentRef(CorpusName.parse(corpus), AspectFilename.parse(filename))


def _code_corpus(corpus_spec: CorpusSpec, namespaces: tuple[_NamespaceEntry, ...]) -> Corpus:
    """The corpus `code`, with its corpus spec and its namespaces, and no document.

    Args:
        corpus_spec: The spec of the `code` corpus.
        namespaces: The namespace specs narrowing it, each without its corpus.
    """
    return Corpus(corpus_spec=corpus_spec, namespaces=FrozenMapping(dict(namespaces)), filenames=frozenset())


@pytest.mark.unit
class TestGovernance:
    def test_frontmatter_schemas_with_the_corpus_spec_alone_returns_the_corpus_schema(self) -> None:
        #: Given
        corpus_spec = _corpus_spec('code')
        namespaces = ()
        filename = AspectFilename.parse('logging')
        corpus = _code_corpus(corpus_spec, namespaces)
        governance = corpus.governance(filename)

        #: When
        schemas = governance.frontmatter_schemas()

        #: Then
        assert tuple(schema.spec for schema in schemas) == (SPECS_DIR / PathComponent.parse('code.spec.json'),), (
            'the corpus frontmatter schema is the only one when the corpus spec governs alone'
        )

    def test_frontmatter_schemas_with_nested_namespaces_returns_the_schemas_broad_to_narrow(self) -> None:
        #: Given
        corpus_spec = _corpus_spec('code')
        namespaces = (
            _code_namespace('pattern'),
            _code_namespace('python'),
            _code_namespace('python-errors'),
        )
        filename = AspectFilename.parse('python-errors-reporting')
        corpus = _code_corpus(corpus_spec, namespaces)
        governance = corpus.governance(filename)

        #: When
        schemas = governance.frontmatter_schemas()

        #: Then
        assert tuple(schema.spec for schema in schemas) == (
            SPECS_DIR / PathComponent.parse('code.spec.json'),
            SPECS_DIR / PathComponent.parse('code-python.spec.json'),
            SPECS_DIR / PathComponent.parse('code-python-errors.spec.json'),
        ), 'the frontmatter schemas follow the corpus, python and python-errors specs, broad to narrow'

    def test_frontmatter_schemas_with_a_namespace_equal_to_the_filename_includes_the_namespace_schema(self) -> None:
        #: Given
        corpus_spec = _corpus_spec('code')
        namespaces = (_code_namespace('python'),)
        filename = AspectFilename.parse('python')
        corpus = _code_corpus(corpus_spec, namespaces)
        governance = corpus.governance(filename)

        #: When
        schemas = governance.frontmatter_schemas()

        #: Then
        assert tuple(schema.spec for schema in schemas) == (
            SPECS_DIR / PathComponent.parse('code.spec.json'),
            SPECS_DIR / PathComponent.parse('code-python.spec.json'),
        ), 'the namespace schema follows the corpus schema when the namespace equals the filename'

    def test_frontmatter_schemas_with_a_namespace_that_is_only_a_prefix_excludes_the_namespace_schema(self) -> None:
        #: Given
        corpus_spec = _corpus_spec('code')
        namespaces = (_code_namespace('python'),)
        filename = AspectFilename.parse('pythonic')
        corpus = _code_corpus(corpus_spec, namespaces)
        governance = corpus.governance(filename)

        #: When
        schemas = governance.frontmatter_schemas()

        #: Then
        assert tuple(schema.spec for schema in schemas) == (SPECS_DIR / PathComponent.parse('code.spec.json'),), (
            'the python namespace schema does not apply to pythonic, only the corpus schema does'
        )

    def test_frontmatter_schemas_with_a_prose_only_corpus_spec_returns_no_schemas(self) -> None:
        #: Given
        corpus_spec = _corpus_spec('code', frontmatter=False)
        namespaces = (_code_namespace('python'),)
        filename = AspectFilename.parse('python-typing')
        corpus = _code_corpus(corpus_spec, namespaces)
        governance = corpus.governance(filename)

        #: When
        schemas = governance.frontmatter_schemas()

        #: Then
        assert schemas == (), (
            'a namespace never governs alone: no frontmatter schema applies without a corpus structure specification'
        )

    def test_frontmatter_schemas_with_a_corpus_structure_without_a_schema_returns_no_schemas(self) -> None:
        #: Given
        corpus_spec = _corpus_spec('code', frontmatter=False, structure=True)
        namespaces = (_code_namespace('python'),)
        filename = AspectFilename.parse('python-typing')
        corpus = _code_corpus(corpus_spec, namespaces)
        governance = corpus.governance(filename)

        #: When
        schemas = governance.frontmatter_schemas()

        #: Then
        assert schemas == (), (
            'a namespace never governs alone: no frontmatter schema applies when the corpus structure states none'
        )

    def test_frontmatter_schemas_with_a_namespace_structure_without_a_schema_adds_no_namespace_schema(self) -> None:
        #: Given
        corpus_spec = _corpus_spec('code')
        namespaces = (_code_namespace('python', frontmatter=False, structure=True),)
        filename = AspectFilename.parse('python-typing')
        corpus = _code_corpus(corpus_spec, namespaces)
        governance = corpus.governance(filename)

        #: When
        schemas = governance.frontmatter_schemas()

        #: Then
        assert tuple(schema.spec for schema in schemas) == (SPECS_DIR / PathComponent.parse('code.spec.json'),), (
            'a namespace structure stating no frontmatter schema adds none, so only the corpus schema applies'
        )

    def test_structure_specs_with_nested_namespaces_returns_the_structures_broad_to_narrow(self) -> None:
        #: Given
        corpus_spec = _corpus_spec('code', structure=True)
        namespaces = (_code_namespace('python', structure=True),)
        filename = AspectFilename.parse('python-typing')
        corpus = _code_corpus(corpus_spec, namespaces)
        governance = corpus.governance(filename)

        #: When
        structure_specs = governance.structure_specs()

        #: Then
        assert tuple(structure_spec.path for structure_spec in structure_specs) == (
            SPECS_DIR / PathComponent.parse('code.spec.json'),
            SPECS_DIR / PathComponent.parse('code-python.spec.json'),
        ), 'the structure specifications follow the corpus and python specs, broad to narrow'

    def test_structure_specs_with_a_corpus_spec_without_a_structure_returns_no_structures(self) -> None:
        #: Given
        corpus_spec = _corpus_spec('code', frontmatter=False)
        namespaces = (_code_namespace('python', structure=True),)
        filename = AspectFilename.parse('python-typing')
        corpus = _code_corpus(corpus_spec, namespaces)
        governance = corpus.governance(filename)

        #: When
        structure_specs = governance.structure_specs()

        #: Then
        assert structure_specs == (), (
            'a namespace never governs alone: no structure applies when the corpus spec has no structure specification'
        )

    def test_structure_specs_with_a_namespace_without_a_structure_returns_the_corpus_structure(self) -> None:
        #: Given
        corpus_spec = _corpus_spec('code', structure=True)
        namespaces = (_code_namespace('python', frontmatter=False),)
        filename = AspectFilename.parse('python-typing')
        corpus = _code_corpus(corpus_spec, namespaces)
        governance = corpus.governance(filename)

        #: When
        structure_specs = governance.structure_specs()

        #: Then
        assert tuple(structure_spec.path for structure_spec in structure_specs) == (
            SPECS_DIR / PathComponent.parse('code.spec.json'),
        ), 'a namespace spec without a structure file adds nothing, so only the corpus structure applies'

    def test_structure_specs_with_a_corpus_structure_stating_only_frontmatter_returns_both_structures(self) -> None:
        #: Given
        # the corpus file states only a frontmatter schema; the namespace file states only an outline rule
        corpus_spec = _corpus_spec('code')
        namespaces = (_code_namespace('python', frontmatter=False, structure=True),)
        filename = AspectFilename.parse('python-typing')
        corpus = _code_corpus(corpus_spec, namespaces)
        governance = corpus.governance(filename)

        #: When
        structure_specs = governance.structure_specs()

        #: Then
        assert tuple(structure_spec.path for structure_spec in structure_specs) == (
            SPECS_DIR / PathComponent.parse('code.spec.json'),
            SPECS_DIR / PathComponent.parse('code-python.spec.json'),
        ), 'a structure file is a base whatever rule it states, as a tokens-only file is, so the namespace applies'

    def test_outline_specs_with_an_outline_in_the_namespace_alone_returns_the_namespace_structure(self) -> None:
        #: Given
        corpus_spec = _corpus_spec('code', structure=True)
        python_namespace, python = _code_namespace('python', structure=True)
        namespaces = ((python_namespace, replace(python, structure=_outlined(python.structure))),)
        filename = AspectFilename.parse('python-typing')
        corpus = _code_corpus(corpus_spec, namespaces)
        governance = corpus.governance(filename)

        #: When
        outline_specs = governance.outline_specs()

        #: Then
        assert tuple(structure_spec.path for structure_spec in outline_specs) == (
            SPECS_DIR / PathComponent.parse('code-python.spec.json'),
        ), 'the corpus structure states no outline, so only the namespace structure is matched against one'

    def test_outline_specs_with_no_structure_stating_an_outline_returns_no_structures(self) -> None:
        #: Given
        corpus_spec = _corpus_spec('code', structure=True)
        namespaces = (_code_namespace('python', structure=True),)
        filename = AspectFilename.parse('python-typing')
        corpus = _code_corpus(corpus_spec, namespaces)
        governance = corpus.governance(filename)

        #: When
        outline_specs = governance.outline_specs()

        #: Then
        assert outline_specs == (), 'no outline governs a document when no governing structure states one'


@pytest.mark.unit
class TestCorpus:
    def test_name_of_a_corpus_returns_the_corpus_its_spec_names(self) -> None:
        #: Given
        corpus = _code_corpus(_corpus_spec('code'), ())

        #: When
        name = corpus.name

        #: Then
        assert name == CODE, 'a corpus is the one its corpus spec names'

    def test_documents_of_a_corpus_returns_a_ref_in_it_per_filename(self) -> None:
        #: Given
        filenames = frozenset({AspectFilename.parse('logging'), AspectFilename.parse('python-typing')})
        corpus = Corpus(corpus_spec=_corpus_spec('code'), namespaces=FrozenMapping({}), filenames=filenames)

        #: When
        documents = corpus.documents

        #: Then
        assert documents == (_ref('code', 'logging'), _ref('code', 'python-typing')), (
            'each filename is a document of the corpus, in filename order'
        )

    def test_document_base_with_a_missing_intermediate_name_returns_the_nearest_existing_ancestor(self) -> None:
        #: Given
        filenames = frozenset(AspectFilename.parse(name) for name in ('python', 'python-fn-unchecked', 'python-fn-x'))
        corpus = Corpus(corpus_spec=_corpus_spec('code'), namespaces=FrozenMapping({}), filenames=filenames)

        #: When
        base = corpus.document_base(AspectFilename.parse('python-fn-unchecked'))

        #: Then
        assert base == _ref('code', 'python'), 'the nearest ancestor the corpus holds is the base, a gap skipped'

    def test_document_base_with_the_narrowest_of_two_ancestors_returns_it(self) -> None:
        #: Given
        filenames = frozenset(AspectFilename.parse(name) for name in ('python', 'python-fn', 'python-fn-names'))
        corpus = Corpus(corpus_spec=_corpus_spec('code'), namespaces=FrozenMapping({}), filenames=filenames)

        #: When
        base = corpus.document_base(AspectFilename.parse('python-fn-names'))

        #: Then
        assert base == _ref('code', 'python-fn'), 'of the ancestors, the one with the most segments is the base'

    def test_document_base_with_no_ancestor_returns_none(self) -> None:
        #: Given
        filenames = frozenset(AspectFilename.parse(name) for name in ('python', 'pythonic', 'logging'))
        corpus = Corpus(corpus_spec=_corpus_spec('code'), namespaces=FrozenMapping({}), filenames=filenames)

        #: When
        base = corpus.document_base(AspectFilename.parse('pythonic'))

        #: Then
        assert base is None, 'a name that only shares letters with another has no base'

    def test_documents_with_filenames_out_of_order_returns_them_sorted_by_filename(self) -> None:
        #: Given
        filenames = frozenset({AspectFilename.parse('python-typing'), AspectFilename.parse('logging')})
        corpus = Corpus(corpus_spec=_corpus_spec('code'), namespaces=FrozenMapping({}), filenames=filenames)

        #: When
        documents = corpus.documents

        #: Then
        assert documents == (_ref('code', 'logging'), _ref('code', 'python-typing')), (
            'the corpus lists its documents by filename, whatever order it was given them in'
        )

    def test_corpus_built_from_one_filename_given_twice_holds_one_document(self) -> None:
        #: Given
        filenames = frozenset([AspectFilename.parse('logging'), AspectFilename.parse('logging')])
        corpus = Corpus(corpus_spec=_corpus_spec('code'), namespaces=FrozenMapping({}), filenames=filenames)

        #: When
        documents = corpus.documents

        #: Then
        assert documents == (_ref('code', 'logging'),), 'a filename is a document once, however often it is given'

    def test_directory_of_a_corpus_returns_its_directory_under_docs(self) -> None:
        #: Given
        corpus = _code_corpus(_corpus_spec('code'), ())

        #: When
        directory = corpus.directory

        #: Then
        assert directory == RootRelativePath.parse('docs/code'), 'a corpus is the directory under docs/ at its name'

    def test_governance_with_the_corpus_spec_alone_returns_the_corpus_spec(self) -> None:
        #: Given
        corpus_spec = _corpus_spec('code')
        namespaces = ()
        filename = AspectFilename.parse('logging')
        corpus = _code_corpus(corpus_spec, namespaces)
        ref = DocumentRef(CODE, filename)

        #: When
        governance = corpus.governance(filename)

        #: Then
        assert governance.ref == ref, 'the governance names the logging document it was asked about'
        assert tuple(str(spec.name) for spec in governance.specs()) == ('code',), (
            'the corpus spec alone governs a document when the corpus has no namespace spec'
        )

    def test_governance_with_nested_namespaces_returns_the_matching_namespaces_broad_to_narrow(self) -> None:
        #: Given
        corpus_spec = _corpus_spec('code')
        namespaces = (
            _code_namespace('pattern'),
            _code_namespace('python'),
            _code_namespace('python-errors'),
        )
        filename = AspectFilename.parse('python-errors-reporting')
        corpus = _code_corpus(corpus_spec, namespaces)
        ref = DocumentRef(CODE, filename)

        #: When
        governance = corpus.governance(filename)

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
        namespaces = (_code_namespace('python'),)
        filename = AspectFilename.parse('python')
        corpus = _code_corpus(corpus_spec, namespaces)
        ref = DocumentRef(CODE, filename)

        #: When
        governance = corpus.governance(filename)

        #: Then
        assert governance.ref == ref, 'the governance names the python document it was asked about'
        assert tuple(str(spec.name) for spec in governance.specs()) == ('code', 'code-python'), (
            'a namespace equal to the whole filename governs the document after the corpus spec'
        )

    def test_governance_with_a_namespace_that_is_only_a_prefix_excludes_that_namespace(self) -> None:
        #: Given
        corpus_spec = _corpus_spec('code')
        namespaces = (_code_namespace('python'),)
        filename = AspectFilename.parse('pythonic')
        corpus = _code_corpus(corpus_spec, namespaces)
        ref = DocumentRef(CODE, filename)

        #: When
        governance = corpus.governance(filename)

        #: Then
        assert governance.ref == ref, 'the governance names the pythonic document it was asked about'
        assert tuple(str(spec.name) for spec in governance.specs()) == ('code',), (
            'python is not a hyphen-delimited prefix of pythonic, so only the corpus spec governs'
        )

    def test_governance_with_a_prose_only_corpus_spec_still_lists_the_corpus_spec_first(self) -> None:
        #: Given
        corpus_spec = _corpus_spec('code', frontmatter=False)
        namespaces = (_code_namespace('python'),)
        filename = AspectFilename.parse('python-typing')
        corpus = _code_corpus(corpus_spec, namespaces)
        ref = DocumentRef(CODE, filename)

        #: When
        governance = corpus.governance(filename)

        #: Then
        assert governance.ref == ref, 'the governance names the python-typing document it was asked about'
        assert tuple(str(spec.name) for spec in governance.specs()) == ('code', 'code-python'), (
            'the corpus spec still governs first even without a structure specification, then the python namespace'
        )

    def test_governance_with_a_prose_only_namespace_includes_the_prose_only_namespace(self) -> None:
        #: Given
        corpus_spec = _corpus_spec('code')
        namespaces = (_code_namespace('python', frontmatter=False),)
        filename = AspectFilename.parse('python-typing')
        corpus = _code_corpus(corpus_spec, namespaces)
        ref = DocumentRef(CODE, filename)

        #: When
        governance = corpus.governance(filename)

        #: Then
        assert governance.ref == ref, 'the governance names the python-typing document it was asked about'
        assert tuple(str(spec.name) for spec in governance.specs()) == ('code', 'code-python'), (
            'a prose-only namespace spec still governs the document after the corpus spec'
        )

    def test_namespace_specs_with_a_narrower_namespace_before_a_broader_one_returns_them_broad_to_narrow(self) -> None:
        #: Given
        namespaces = (_code_namespace('python-errors'), _code_namespace('python'))
        corpus = _code_corpus(_corpus_spec('code'), namespaces)

        #: When
        namespace_specs = corpus.namespace_specs

        #: Then
        assert namespace_specs == (_namespace_spec('code-python'), _namespace_spec('code-python-errors')), (
            'each namespace is a spec of the corpus, the broader one first'
        )

    def test_namespace_specs_with_sibling_namespaces_out_of_value_order_returns_them_by_value(self) -> None:
        #: Given
        namespaces = (_code_namespace('python'), _code_namespace('pattern'))
        corpus = _code_corpus(_corpus_spec('code'), namespaces)

        #: When
        namespace_specs = corpus.namespace_specs

        #: Then
        assert namespace_specs == (_namespace_spec('code-pattern'), _namespace_spec('code-python')), (
            'namespace specs with the same segment count are listed in value order'
        )


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
    """Corpora `code` (two documents) and `feat` (one document)."""
    code = Corpus(
        corpus_spec=_corpus_spec('code'),
        namespaces=FrozenMapping({}),
        filenames=frozenset({AspectFilename.parse('logging'), AspectFilename.parse('python-typing')}),
    )
    feat = Corpus(
        corpus_spec=_corpus_spec('feat'),
        namespaces=FrozenMapping({}),
        filenames=frozenset({AspectFilename.parse('cli-check')}),
    )
    return WorkspaceModel(
        corpus_values=frozenset({code, feat}),
        skills_dirs=frozenset(),
        skill_location_values=frozenset(),
        outside_symlink_values=frozenset(),
        load_failures=(),
        repository_schema_inputs=_schema_inputs(code, feat),
    )


def _schema_inputs(*corpora: Corpus) -> tuple[RepositorySchemaInput, ...]:
    """The registry inputs for every frontmatter schema stated by the given corpus layers."""
    inputs: dict[SchemaRef, RepositorySchemaInput] = {}
    for corpus in corpora:
        for filename in corpus.filenames:
            governance = corpus.governance(filename)
            for reference, schema in zip(
                governance.applicable_frontmatter_schema_refs(), governance.frontmatter_schemas(), strict=True
            ):
                inputs[reference] = RepositorySchemaInput(
                    reference, RepositoryOrigin(schema.spec, str(schema.spec)), schema.schema.schema
                )
    return tuple(inputs.values())


def _model_of_corpora(*names: str) -> WorkspaceModel:
    """A model of corpora with the names, each holding a corpus specification and no document.

    Args:
        names: The corpus names, such as `code` and `code_`.
    """
    corpora = [
        Corpus(corpus_spec=_corpus_spec(name), namespaces=FrozenMapping({}), filenames=frozenset()) for name in names
    ]
    return WorkspaceModel(
        corpus_values=frozenset(corpora),
        skills_dirs=frozenset(),
        skill_location_values=frozenset(),
        outside_symlink_values=frozenset(),
        load_failures=(),
    )


def _regular_skill(directory: str) -> SkillLocation:
    """The location of a skill whose directory and `SKILL.md` are no links.

    Args:
        directory: Root-relative skill directory, such as `.agents/skills/audit`.
    """
    path = RootRelativePath.parse(directory)
    # No link on the way, so the directory and its `SKILL.md` are their own resolved paths.
    return SkillLocation(
        SkillRef(ResolvedPath(path.parent), PathComponent.parse(path.value.name)),
        resolves_to=ResolvedPath(path),
        file_resolves_to=ResolvedPath(path / PathComponent.parse('SKILL.md')),
    )


AUDIT: Final[SkillLocation] = SkillLocation(
    SkillRef(ResolvedPath(RootRelativePath.parse('.agents/skills')), PathComponent.parse('audit')),
    resolves_to=ResolvedPath(RootRelativePath.parse('skills/audit')),
    file_resolves_to=ResolvedPath(RootRelativePath.parse('shared/audit.md')),
)
"""A skill linked to `skills/audit/`, whose `SKILL.md` is a link to `shared/audit.md`."""

REVIEW: Final[SkillLocation] = _regular_skill('.agents/skills/review')
"""A skill in a regular directory."""

REVIEW_ALIAS: Final[SkillLocation] = SkillLocation(
    SkillRef(ResolvedPath(RootRelativePath.parse('.agents/skills')), PathComponent.parse('reviewer')),
    resolves_to=ResolvedPath(RootRelativePath.parse('.agents/skills/review')),
    file_resolves_to=ResolvedPath(RootRelativePath.parse('.agents/skills/review/SKILL.md')),
)
"""A second entry linked to the `review` skill's directory."""


@pytest.fixture(scope='function')
def skills_model() -> WorkspaceModel:
    """No corpus, two agents reading `.agents/skills`, and the three skills above in it.

    One of the agents reads it through the `.claude/skills` link.
    """
    universal = ResolvedPath(RootRelativePath.parse('.agents/skills'))
    return WorkspaceModel(
        corpus_values=frozenset(),
        skills_dirs=frozenset(
            {
                SkillsDir(
                    agent=AgentName('claude-code'),
                    path=RootRelativePath.parse('.claude/skills'),
                    resolves_to=universal,
                ),
                SkillsDir(agent=AgentName('codex'), path=universal, resolves_to=universal),
            }
        ),
        skill_location_values=frozenset({AUDIT, REVIEW, REVIEW_ALIAS}),
        outside_symlink_values=frozenset(),
        load_failures=(),
    )


@pytest.mark.unit
class TestWorkspaceModel:
    def test_corpus_values_derive_the_lookup_by_name(self, two_corpora_model: WorkspaceModel) -> None:
        #: Given
        model = two_corpora_model

        #: When
        corpora = model.corpora

        #: Then
        assert model.corpus_values == frozenset({corpora[CODE], corpora[FEAT]}), (
            'the model stores each corpus value once without an order'
        )
        assert corpora == FrozenMapping({CODE: corpora[CODE], FEAT: corpora[FEAT]}), (
            'the lookup is keyed by each corpus value name'
        )

    def test_replacing_corpus_values_rebuilds_the_lookup(self, two_corpora_model: WorkspaceModel) -> None:
        #: Given
        feat = two_corpora_model.corpora[FEAT]

        #: When
        model = replace(two_corpora_model, corpus_values=frozenset({feat}))

        #: Then
        assert model.find_corpus(FEAT) == feat, 'the replacement corpus is available under its own name'
        assert model.find_corpus(CODE) is None, 'the replaced corpus is absent from the derived lookup'

    def test_corpus_values_with_the_same_name_raise_duplicate_corpus_name(self) -> None:
        #: Given
        first = Corpus(corpus_spec=_corpus_spec('code'), namespaces=FrozenMapping({}), filenames=frozenset())
        second = replace(first, filenames=frozenset({AspectFilename.parse('python-typing')}))

        #: When
        with pytest.raises(DuplicateCorpusNameError) as exc_info:
            replace(_model_of_corpora('code'), corpus_values=frozenset({first, second}))

        #: Then
        assert exc_info.value.name == CODE, 'the typed failure identifies the repeated corpus name'

    def test_corpus_values_with_the_same_members_compare_equal_regardless_of_construction_order(
        self, two_corpora_model: WorkspaceModel
    ) -> None:
        #: Given
        model = two_corpora_model
        reversed_corpora = frozenset(reversed(tuple(model.corpus_values)))

        #: When
        reordered_model = replace(model, corpus_values=reversed_corpora)

        #: Then
        assert reordered_model == model, 'corpus construction order does not affect workspace model equality'

    def test_corpora_lookup_order_is_sorted_for_differently_ordered_values(
        self, two_corpora_model: WorkspaceModel
    ) -> None:
        #: Given
        model = two_corpora_model
        reordered_values = frozenset(reversed(tuple(model.corpus_values)))

        #: When
        reordered_model = replace(model, corpus_values=reordered_values)

        #: Then
        assert tuple(model.corpora) == (CODE, FEAT), 'corpora keys are inserted in sorted name order'
        assert tuple(reordered_model.corpora) == tuple(model.corpora), (
            'the derived corpus lookup order is independent of input set iteration'
        )

    def test_construction_with_a_non_meta_corpus_in_the_meta_slot_raises_meta_corpus_name_mismatch(
        self, two_corpora_model: WorkspaceModel
    ) -> None:
        #: Given
        code = two_corpora_model.corpora[CODE]

        #: When
        with pytest.raises(MetaCorpusNameMismatchError) as exc_info:
            replace(two_corpora_model, meta_corpus=code)

        #: Then
        assert exc_info.value.value == CODE, 'the error retains the name held in the reserved meta slot'

    def test_skill_location_values_derive_the_lookup_by_ref(self, skills_model: WorkspaceModel) -> None:
        #: Given
        model = skills_model

        #: When
        locations = model.skill_locations

        #: Then
        assert model.skill_location_values == frozenset({AUDIT, REVIEW, REVIEW_ALIAS}), (
            'the model stores each location once without an order'
        )
        assert locations == FrozenMapping({location.ref: location for location in model.skill_location_values}), (
            'the lookup is keyed by each location ref'
        )

    def test_skill_locations_with_the_same_ref_raise_duplicate_skill_location_ref(self) -> None:
        #: Given
        alternate = replace(AUDIT, resolves_to=ResolvedPath(RootRelativePath.parse('skills/another-audit')))

        #: When
        with pytest.raises(DuplicateSkillLocationRefError) as exc_info:
            replace(_model_of_corpora(), skill_location_values=frozenset({AUDIT, alternate}))

        #: Then
        assert exc_info.value.ref == AUDIT.ref, 'the typed failure identifies the repeated skill ref'

    def test_skill_locations_with_the_same_members_compare_equal_regardless_of_construction_order(
        self, skills_model: WorkspaceModel
    ) -> None:
        #: Given
        model = skills_model
        reversed_locations = frozenset(reversed(tuple(model.skill_location_values)))

        #: When
        reordered_model = replace(model, skill_location_values=reversed_locations)

        #: Then
        assert reordered_model == model, 'skill location construction order does not affect model equality'

    def test_replacing_skill_location_values_rebuilds_the_lookup(self, skills_model: WorkspaceModel) -> None:
        #: Given
        model = replace(skills_model, skill_location_values=frozenset({AUDIT}))

        #: When
        locations = model.skill_locations

        #: Then
        assert locations == FrozenMapping({AUDIT.ref: AUDIT}), 'replacement locations are indexed by their own refs'

    def test_outside_symlink_values_derive_the_lookup_by_path(self, skills_model: WorkspaceModel) -> None:
        #: Given
        entry = RootRelativePath.parse('.agents/skills/x')
        outside = OutsideSymlink(entry, RootExit(ResolvedPath(entry), _target('/opt/team-skills/x')))
        model = replace(skills_model, outside_symlink_values=frozenset({outside}))

        #: When
        symlinks = model.outside_symlinks

        #: Then
        assert model.outside_symlink_values == frozenset({outside}), (
            'the model stores outside symlink values once without an order'
        )
        assert symlinks == FrozenMapping({entry: outside}), 'the lookup is keyed by each symlink path'

    def test_outside_symlinks_with_the_same_path_raise_duplicate_outside_symlink_path(self) -> None:
        #: Given
        entry = RootRelativePath.parse('.agents/skills/x')
        first = OutsideSymlink(entry, RootExit(ResolvedPath(entry), _target('/opt/team-skills/x')))
        second = OutsideSymlink(entry, RootExit(ResolvedPath(entry), _target('/opt/other-skills/x')))

        #: When
        with pytest.raises(DuplicateOutsideSymlinkPathError) as exc_info:
            replace(_model_of_corpora(), outside_symlink_values=frozenset({first, second}))

        #: Then
        assert exc_info.value.path == entry, 'the typed failure identifies the repeated symlink path'

    def test_outside_symlinks_with_the_same_members_compare_equal_regardless_of_construction_order(
        self, skills_model: WorkspaceModel
    ) -> None:
        #: Given
        entry = RootRelativePath.parse('.agents/skills/x')
        outside = OutsideSymlink(entry, RootExit(ResolvedPath(entry), _target('/opt/team-skills/x')))
        model = replace(skills_model, outside_symlink_values=frozenset({outside}))
        reversed_symlinks = frozenset(reversed(tuple(model.outside_symlink_values)))

        #: When
        reordered_model = replace(model, outside_symlink_values=reversed_symlinks)

        #: Then
        assert reordered_model == model, 'outside symlink construction order does not affect model equality'

    def test_derived_lookup_iteration_is_sorted_for_differently_ordered_values(
        self, skills_model: WorkspaceModel, two_corpora_model: WorkspaceModel
    ) -> None:
        #: Given
        first_path = RootRelativePath.parse('.agents/skills/a')
        second_path = RootRelativePath.parse('.agents/skills/z')
        first = OutsideSymlink(first_path, RootExit(ResolvedPath(first_path), _target('/outside/a')))
        second = OutsideSymlink(second_path, RootExit(ResolvedPath(second_path), _target('/outside/z')))
        model = replace(
            skills_model,
            corpus_values=two_corpora_model.corpus_values,
            repository_schema_inputs=two_corpora_model.repository_schema_inputs,
            outside_symlink_values=frozenset({second, first}),
        )

        #: When
        reordered = replace(
            model,
            corpus_values=frozenset(reversed(tuple(model.corpus_values))),
            skill_location_values=frozenset(reversed(tuple(model.skill_location_values))),
            outside_symlink_values=frozenset(reversed(tuple(model.outside_symlink_values))),
        )

        #: Then
        assert tuple(reordered.corpora) == (CODE, FEAT), 'corpus keys are inserted in sorted name order'
        assert tuple(reordered.skill_locations) == tuple(sorted(model.skill_locations)), (
            'skill location keys are inserted in sorted ref order'
        )
        assert tuple(reordered.outside_symlinks) == (first_path, second_path), (
            'outside symlink keys are inserted in sorted path order'
        )

    def test_replacing_outside_symlink_values_rebuilds_the_lookup(self, skills_model: WorkspaceModel) -> None:
        #: Given
        entry = RootRelativePath.parse('.agents/skills/x')
        outside = OutsideSymlink(entry, RootExit(ResolvedPath(entry), _target('/opt/team-skills/x')))

        #: When
        model = replace(skills_model, outside_symlink_values=frozenset({outside}))

        #: Then
        assert model.outside_symlinks == FrozenMapping({entry: outside}), 'replacement symlinks use their own paths'

    def test_find_corpus_with_a_listed_name_returns_that_corpus(self, two_corpora_model: WorkspaceModel) -> None:
        #: Given
        name = FEAT

        #: When
        corpus = two_corpora_model.find_corpus(name)

        #: Then
        assert corpus is not None, 'a listed name has a corpus'
        assert corpus.name == FEAT, 'the corpus is found by name'

    def test_find_corpus_with_an_unlisted_name_returns_none(self, two_corpora_model: WorkspaceModel) -> None:
        #: Given
        name = CorpusName.parse('blog')

        #: When
        corpus = two_corpora_model.find_corpus(name)

        #: Then
        assert corpus is None, 'a name the model does not list has no corpus'

    def test_find_governance_with_a_ref_in_a_listed_corpus_returns_its_corpus_governance(
        self, two_corpora_model: WorkspaceModel
    ) -> None:
        #: Given
        ref = _ref('feat', 'cli-check')

        #: When
        governance = two_corpora_model.find_governance(ref)

        #: Then
        assert governance is not None, 'the model lists the feat corpus'
        assert governance.ref == ref, 'the governance is of the document asked'
        assert governance.corpus_spec == _corpus_spec('feat'), 'the feat corpus spec governs it'
        assert governance.namespace_specs == (), 'no namespace of the feat corpus matches `cli-check`'

    def test_find_governance_with_a_ref_of_a_corpus_the_model_lacks_returns_none(
        self, two_corpora_model: WorkspaceModel
    ) -> None:
        #: Given
        ref = _ref('blog', 'launch')

        #: When
        governance = two_corpora_model.find_governance(ref)

        #: Then
        assert governance is None, 'no specification governs a document in a corpus the model does not hold'

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

    def test_describe_item_for_a_document_separates_report_and_read_paths(
        self, two_corpora_model: WorkspaceModel
    ) -> None:
        #: Given
        ref = _ref('code', 'logging')

        #: When
        descriptor = two_corpora_model.describe_item(ref)

        #: Then
        assert descriptor.ref == ItemRef(ref.path), 'the logical ref is also the report path'
        assert descriptor.read_location == ResolvedPath(ref.path), 'regular corpus documents read from their path'
        assert descriptor.link_base == DocumentDirectory(RootRelativePath.parse('docs/code')), (
            'document links use their directory'
        )
        assert descriptor.corpus == CorpusName.parse('code'), (
            'the model derives document governance from the corpus path'
        )
        assert descriptor.name == AspectFilename.parse('logging'), 'the model derives the aspect from the filename'
        assert isinstance(descriptor.origin, DocumentOrigin), 'the descriptor retains document provenance'
        assert descriptor.frontmatter_schema_refs == (SchemaRef(SchemaKind.FRONTMATTER, 'code'),), (
            'the descriptor retains the loader identity used for frontmatter governance and diagnostics'
        )
        assert descriptor.governed_parts == frozenset({SpecPart.FRONTMATTER, SpecPart.STRUCTURE}), (
            'a corpus structure specification activates structure and its frontmatter alongside Markdown checks'
        )

    def test_describe_item_derives_builtin_frontmatter_governance_from_its_schema(self) -> None:
        #: Given
        location = _regular_skill('.agents/skills/audit')
        origin = BuiltinOrigin('builtin:test-layer')
        reference = SchemaRef(SchemaKind.FRONTMATTER, origin.identity)
        schema_input = SchemaInput(reference, origin, FrozenMapping.from_plain({'type': 'object'}))
        layer = BuiltinSpecLayer(origin, frozenset({ItemType.SKILL_ENTRYPOINT}), schema_input)
        model = WorkspaceModel(
            corpus_values=frozenset(),
            skills_dirs=frozenset(),
            skill_location_values=frozenset({location}),
            outside_symlink_values=frozenset(),
            load_failures=(),
            builtin_layers=(layer,),
        )

        #: When
        descriptor = model.describe_item(location.ref)

        #: Then
        assert descriptor.governed_parts == frozenset({SpecPart.FRONTMATTER}), (
            'a builtin frontmatter schema governs the frontmatter part'
        )

    def test_builtin_layer_rejects_a_non_frontmatter_schema_input(self) -> None:
        #: Given
        origin = BuiltinOrigin('builtin:test-layer')
        reference = SchemaRef(SchemaKind.STRUCTURE, origin.identity)
        schema_input = SchemaInput(reference, origin, FrozenMapping.from_plain({'lines': 50}))

        #: When
        with pytest.raises(InvalidBuiltinFrontmatterSchemaError) as exc_info:
            BuiltinSpecLayer(
                origin,
                frozenset({ItemType.DOCUMENT}),
                frontmatter_schema=schema_input,
            )

        #: Then
        assert exc_info.value.reference == reference, 'the error identifies the schema kind the layer cannot hold'

    def test_describe_item_with_a_line_budget_marks_the_budget_governed(
        self, two_corpora_model: WorkspaceModel
    ) -> None:
        #: Given
        corpus = two_corpora_model.corpora[CODE]
        assert isinstance(corpus.corpus_spec.structure, StructureSpec), 'the corpus has a parsed structure spec'
        structured = replace(
            corpus.corpus_spec, structure=replace(corpus.corpus_spec.structure, lines=NonZeroUnsignedInt(1))
        )
        model = replace(
            two_corpora_model,
            corpus_values=frozenset({replace(corpus, corpus_spec=structured), two_corpora_model.corpora[FEAT]}),
        )

        #: When
        descriptor = model.describe_item(_ref('code', 'logging'))

        #: Then
        assert SpecPart.BUDGET in descriptor.governed_parts, 'a declared line cap governs the budget part'

    def test_describe_item_places_builtin_frontmatter_before_repository_layers(
        self, two_corpora_model: WorkspaceModel
    ) -> None:
        #: Given
        origin = BuiltinOrigin('builtin:test-layer')
        reference = SchemaRef(SchemaKind.FRONTMATTER, origin.identity)
        schema_input = SchemaInput(reference, origin, FrozenMapping.from_plain({'type': 'object'}))
        layer = BuiltinSpecLayer(
            origin,
            frozenset({ItemType.DOCUMENT}),
            frontmatter_schema=schema_input,
        )
        model = replace(two_corpora_model, builtin_layers=(layer,))

        #: When
        descriptor = model.describe_item(_ref('code', 'logging'))

        #: Then
        governance = model.find_governance(_ref('code', 'logging'))
        assert model.builtin_layers_for(ItemType.DOCUMENT) == (layer,), 'the item kind selects its builtin layer'
        assert model.schema_inputs[reference] == schema_input, 'the registry derives builtin inputs from its layers'
        assert governance is not None, 'the repository corpus governs the document'
        assert descriptor.frontmatter_schema_refs == (reference, *governance.applicable_frontmatter_schema_refs()), (
            'the builtin frontmatter schema precedes the repository layers'
        )
        assert SpecPart.BUDGET not in descriptor.governed_parts, 'a builtin layer without lines has no budget part'

    def test_model_rejects_a_schema_ref_repeated_by_builtin_layers(self, two_corpora_model: WorkspaceModel) -> None:
        #: Given
        origin = BuiltinOrigin('builtin:test-layer')
        reference = SchemaRef(SchemaKind.FRONTMATTER, origin.identity)
        schema_input = SchemaInput(reference, origin, FrozenMapping.from_plain({'type': 'object'}))
        layer = BuiltinSpecLayer(
            origin,
            frozenset({ItemType.DOCUMENT}),
            frontmatter_schema=schema_input,
        )

        #: When
        with pytest.raises(DuplicateSchemaRefError) as exc_info:
            replace(two_corpora_model, builtin_layers=(layer, layer))

        #: Then
        assert exc_info.value.reference == reference, 'the refusal identifies the repeated builtin schema'

    def test_model_rejects_a_repository_schema_that_shadows_a_builtin_layer(
        self, two_corpora_model: WorkspaceModel
    ) -> None:
        #: Given
        origin = BuiltinOrigin('builtin:test-layer')
        reference = SchemaRef(SchemaKind.FRONTMATTER, origin.identity)
        schema_input = SchemaInput(reference, origin, FrozenMapping.from_plain({'type': 'object'}))
        repository_input = RepositorySchemaInput(
            reference,
            RepositoryOrigin(RootRelativePath.parse('docs/test.json'), 'test'),
            FrozenMapping.from_plain({'type': 'object'}),
        )
        layer = BuiltinSpecLayer(
            origin,
            frozenset({ItemType.DOCUMENT}),
            frontmatter_schema=schema_input,
        )

        #: When
        with pytest.raises(DuplicateSchemaRefError) as exc_info:
            replace(
                two_corpora_model,
                builtin_layers=(layer,),
                repository_schema_inputs=(repository_input,),
            )

        #: Then
        assert exc_info.value.reference == reference, 'the refusal identifies the conflicting schema'

    def test_describe_item_for_a_layered_document_keeps_every_schema_in_order(self) -> None:
        #: Given
        code = _code_corpus(_corpus_spec('code'), (_code_namespace('python'),))
        code = replace(code, filenames=frozenset({AspectFilename.parse('python-typing')}))
        model = WorkspaceModel(
            corpus_values=frozenset({code}),
            skills_dirs=frozenset(),
            skill_location_values=frozenset(),
            outside_symlink_values=frozenset(),
            load_failures=(),
            repository_schema_inputs=_schema_inputs(code),
        )

        #: When
        descriptor = model.describe_item(_ref('code', 'python-typing'))

        #: Then
        assert isinstance(descriptor.origin, DocumentOrigin), 'the descriptor retains document provenance'
        assert descriptor.frontmatter_schema_refs == (
            SchemaRef(SchemaKind.FRONTMATTER, 'code'),
            SchemaRef(SchemaKind.FRONTMATTER, 'code-python'),
        ), 'the same registry refs carry the corpus and namespace schema order'

    def test_describe_item_for_a_linked_skill_keeps_logical_identity_when_read_target_changes(
        self, skills_model: WorkspaceModel
    ) -> None:
        #: Given
        moved = SkillLocation(
            AUDIT.ref,
            resolves_to=ResolvedPath(RootRelativePath.parse('skills/new-audit')),
            file_resolves_to=ResolvedPath(RootRelativePath.parse('skills/new-audit/entry.md')),
        )
        retargeted = replace(
            skills_model,
            skill_location_values=frozenset({moved, REVIEW, REVIEW_ALIAS}),
        )

        #: When
        before = skills_model.describe_item(AUDIT.ref)
        after = retargeted.describe_item(AUDIT.ref)

        #: Then
        assert before.ref == after.ref == ItemRef(AUDIT.ref.path), 'the listed path owns stable identity'
        assert before.read_location != after.read_location, 'the descriptor records the changed read target'
        assert before.link_base == after.link_base == SkillRoot(AUDIT.ref.directory), (
            'skill links use the listed skill root'
        )
        assert isinstance(after.origin, SkillEntrypointOrigin), 'the descriptor retains skill-specific origin facts'
        assert after.type is ItemType.SKILL_ENTRYPOINT
        assert after.type.value == 'skill-entrypoint', 'the serialized item type remains unchanged'
        assert after.name == AspectFilename.parse('audit'), 'the descriptor retains the typed skill name'
        assert after.origin.link_target == moved.resolves_to, 'the retargeted directory remains available for notes'

    def test_describe_item_for_a_skill_with_an_invalid_aspect_name_keeps_its_listed_name(self) -> None:
        #: Given
        location = _regular_skill('.agents/skills/1skill')
        model = WorkspaceModel(
            corpus_values=frozenset(),
            skills_dirs=frozenset(),
            skill_location_values=frozenset({location}),
            outside_symlink_values=frozenset(),
            load_failures=(),
        )

        #: When
        descriptor = model.describe_item(location.ref)

        #: Then
        assert descriptor.name is None, 'a skill directory need not follow the aspect-name format'
        assert descriptor.listed_name == '1skill', 'the model keeps the original skill directory name'

    def test_skills_with_three_skills_returns_their_refs_in_directory_order(self, skills_model: WorkspaceModel) -> None:
        #: Given
        model = skills_model

        #: When
        refs = model.skills()

        #: Then
        assert refs == (AUDIT.ref, REVIEW.ref, REVIEW_ALIAS.ref), (
            "one ref per location of the agents' skills, in the stored order"
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
        other = replace(
            skills_model,
            skill_location_values=frozenset({retargeted, REVIEW, REVIEW_ALIAS}),
        )

        #: When
        equal = other == skills_model

        #: Then
        assert equal is False, 'the skill keeps its ref, and the model still changes with where its link leads'

    def test_find_skill_location_with_the_entry_of_a_regular_skill_returns_its_location(
        self, skills_model: WorkspaceModel
    ) -> None:
        #: Given
        directory = RootRelativePath.parse('.agents/skills/review')

        #: When
        location = skills_model.find_skill_location(directory)

        #: Then
        assert location == REVIEW, 'the skill listed at the entry is returned, not the entry linked to it'

    def test_find_skill_location_with_the_entry_of_a_linked_skill_returns_its_location(
        self, skills_model: WorkspaceModel
    ) -> None:
        #: Given
        directory = RootRelativePath.parse('.agents/skills/reviewer')

        #: When
        location = skills_model.find_skill_location(directory)

        #: Then
        assert location == REVIEW_ALIAS, 'a linked entry is found by its own name, with where it leads'

    def test_find_skill_location_with_the_resolved_directory_a_linked_skill_leads_to_returns_none(
        self, skills_model: WorkspaceModel
    ) -> None:
        #: Given
        directory = RootRelativePath.parse('skills/audit')

        #: When
        location = skills_model.find_skill_location(directory)

        #: Then
        assert location is None, 'the directory a link leads to is no entry of a skills directory'

    def test_find_skill_location_with_a_path_that_is_no_skill_returns_none(self, skills_model: WorkspaceModel) -> None:
        #: Given
        directory = RootRelativePath.parse('.agents/skills')

        #: When
        location = skills_model.find_skill_location(directory)

        #: Then
        assert location is None, 'the skills directory itself is no skill'

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

    def test_skill_locations_in_with_a_skills_directory_returns_every_skill_listed_there(
        self, skills_model: WorkspaceModel
    ) -> None:
        #: Given
        resolved_path = ResolvedPath(RootRelativePath.parse('.agents/skills'))

        #: When
        locations = skills_model.skill_locations_in(resolved_path)

        #: Then
        assert locations == (AUDIT, REVIEW, REVIEW_ALIAS), (
            'every entry of the resolved directory, linked or not, in the model order'
        )

    def test_skill_locations_in_with_a_skills_directory_holding_no_skill_returns_empty(
        self, skills_model: WorkspaceModel
    ) -> None:
        #: Given
        model = replace(skills_model, skill_location_values=frozenset())
        resolved_path = ResolvedPath(RootRelativePath.parse('.agents/skills'))

        #: When
        locations = model.skill_locations_in(resolved_path)

        #: Then
        assert locations == (), 'no skill is listed in a skills directory that holds none'

    def test_has_outside_symlink_with_the_path_an_agent_reaches_it_at_returns_true(
        self, skills_model: WorkspaceModel
    ) -> None:
        #: Given
        entry = RootRelativePath.parse('.agents/skills/x')
        outside = OutsideSymlink(entry, RootExit(ResolvedPath(entry), _target('/opt/team-skills/x')))
        model = replace(skills_model, outside_symlink_values=frozenset({outside}))

        #: When
        found = model.has_outside_symlink(entry)

        #: Then
        assert found, 'the symlink is found at the path an agent reaches it at'

    def test_has_outside_symlink_with_a_path_below_a_symlink_leading_outside_returns_false(
        self, skills_model: WorkspaceModel
    ) -> None:
        #: Given
        entry = RootRelativePath.parse('.agents/skills/x')
        outside = OutsideSymlink(entry, RootExit(ResolvedPath(entry), _target('/opt/team-skills/x')))
        model = replace(skills_model, outside_symlink_values=frozenset({outside}))
        below = entry / PathComponent.parse('SKILL.md')

        #: When
        found = model.has_outside_symlink(below)

        #: Then
        assert not found, 'a path is compared whole: one below a symlink leading outside is not that symlink'

    def test_locate_skill_files_with_the_file_of_a_regular_skill_returns_every_entry_leading_there(
        self, skills_model: WorkspaceModel
    ) -> None:
        #: Given
        path = ResolvedPath(RootRelativePath.parse('.agents/skills/review/SKILL.md'))

        #: When
        locations = skills_model.locate_skill_files(path)

        #: Then
        assert locations == (REVIEW, REVIEW_ALIAS), (
            'the skill holding the file and the entry linked to it both read it, in the model order'
        )

    def test_locate_skill_files_with_the_file_a_linked_skill_file_leads_to_returns_its_location(
        self, skills_model: WorkspaceModel
    ) -> None:
        #: Given
        path = ResolvedPath(RootRelativePath.parse('shared/audit.md'))

        #: When
        locations = skills_model.locate_skill_files(path)

        #: Then
        assert locations == (AUDIT,), 'a skill whose SKILL.md is a link is at the file the link leads to'

    def test_locate_skill_files_with_the_directory_of_a_skill_returns_empty(self, skills_model: WorkspaceModel) -> None:
        #: Given
        path = ResolvedPath(RootRelativePath.parse('skills/audit'))

        #: When
        locations = skills_model.locate_skill_files(path)

        #: Then
        assert locations == (), 'a directory is no SKILL.md, even where a linked skill keeps its files'

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
        ref = SkillRef(ResolvedPath(RootRelativePath.parse('skills')), PathComponent.parse('review'))

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


def _spec_ref(name: str) -> SpecRef:
    return SpecRef(SPECS_DIR / PathComponent.parse(f'{name}.md'))


@pytest.mark.unit
class TestSpecifications:
    def test_specifications_lists_every_markdown_file_of_a_spec_sorted_and_no_json(self) -> None:
        #: Given
        code = Corpus(
            corpus_spec=_corpus_spec('code'),
            namespaces=FrozenMapping(dict((_code_namespace('python'),))),
            filenames=frozenset(),
        )
        feat = Corpus(corpus_spec=_corpus_spec('feat'), namespaces=FrozenMapping({}), filenames=frozenset())
        model = WorkspaceModel(
            corpus_values=frozenset({feat, code}),
            skills_dirs=frozenset(),
            skill_location_values=frozenset(),
            outside_symlink_values=frozenset(),
            load_failures=(),
        )

        #: When
        specifications = model.specifications()

        #: Then
        assert specifications == (_spec_ref('code-python'), _spec_ref('code'), _spec_ref('feat')), (
            'the prose of each corpus and namespace spec, by path, and none of the structure files'
        )

    def test_find_specification_base_returns_the_narrowest_specification_the_name_continues(self) -> None:
        #: Given
        code = Corpus(
            corpus_spec=_corpus_spec('code'),
            namespaces=FrozenMapping(dict((_code_namespace('python'), _code_namespace('python-typing')))),
            filenames=frozenset(),
        )
        model = WorkspaceModel(
            corpus_values=frozenset({code}),
            skills_dirs=frozenset(),
            skill_location_values=frozenset(),
            outside_symlink_values=frozenset(),
            load_failures=(),
        )
        extension = _spec_ref('code-python-typing')
        expected = _spec_ref('code-python')

        #: When
        base = model.find_specification_base(extension)

        #: Then
        assert base == expected, 'the base is the narrowest specification whose name is continued'

    def test_find_specification_base_of_a_corpus_specification_returns_none(self) -> None:
        #: Given
        code = Corpus(corpus_spec=_corpus_spec('code'), namespaces=FrozenMapping({}), filenames=frozenset())
        model = WorkspaceModel(
            corpus_values=frozenset({code}),
            skills_dirs=frozenset(),
            skill_location_values=frozenset(),
            outside_symlink_values=frozenset(),
            load_failures=(),
        )
        corpus_specification = _spec_ref('code')

        #: When
        base = model.find_specification_base(corpus_specification)

        #: Then
        assert base is None, 'a corpus specification continues no other name, so it has no base'

    def test_find_specification_base_with_a_corpus_named_with_a_trailing_underscore_returns_none(self) -> None:
        #: Given
        model = _model_of_corpora('code', 'code_')
        specification = _spec_ref('code_')

        #: When
        base = model.find_specification_base(specification)

        #: Then
        assert base is None, (
            'a trailing underscore is no aspect name, and the lookup neither breaks nor takes `code` as its base'
        )

    def test_find_specification_base_with_a_corpus_named_with_a_leading_underscore_returns_none(self) -> None:
        #: Given
        model = _model_of_corpora('code', '_code')
        specification = _spec_ref('_code')

        #: When
        base = model.find_specification_base(specification)

        #: Then
        assert base is None, (
            'a leading underscore is no aspect name, and the lookup neither breaks nor takes `code` as its base'
        )

    def test_find_specification_base_with_a_corpus_named_with_a_repeated_underscore_returns_none(self) -> None:
        #: Given
        model = _model_of_corpora('code', 'a__b')
        specification = _spec_ref('a__b')

        #: When
        base = model.find_specification_base(specification)

        #: Then
        assert base is None, 'a repeated underscore is no aspect name, and the lookup neither breaks nor finds a base'

    def test_specifications_lists_the_prose_of_the_skills_spec(self) -> None:
        #: Given
        skills = Corpus(corpus_spec=_corpus_spec('skills'), namespaces=FrozenMapping({}), filenames=frozenset())
        model = WorkspaceModel(
            corpus_values=frozenset(),
            skills_dirs=frozenset(),
            skill_location_values=frozenset(),
            outside_symlink_values=frozenset(),
            load_failures=(),
            skills_corpus=skills,
        )

        #: When
        specifications = model.specifications()

        #: Then
        assert specifications == (_spec_ref('skills'),), 'the reserved skills corpus states specifications too'

    def test_skill_governance_with_a_skills_corpus_returns_matching_layers(self) -> None:
        #: Given
        skills = Corpus(
            corpus_spec=_corpus_spec('skills'),
            namespaces=FrozenMapping(
                {
                    AspectNamespace.parse('code'): CorpusNamespace(
                        files=(RootRelativePath.parse('docs/__meta__/skills-code.md'),),
                        structure=_namespace_spec('skills-code').structure,
                    )
                }
            ),
            filenames=frozenset(),
        )
        location = _regular_skill('.agents/skills/code-rules')
        model = WorkspaceModel(
            corpus_values=frozenset(),
            skills_dirs=frozenset(),
            skill_location_values=frozenset({location}),
            outside_symlink_values=frozenset(),
            load_failures=(),
            skills_corpus=skills,
        )

        #: When
        governance = model.skill_governance(location.ref)

        #: Then
        assert governance is not None, 'the reserved skills corpus governs its listed skill'
        assert tuple(str(spec.name) for spec in governance.specs()) == ('skills', 'skills-code'), (
            'matching namespace specifications layer after the skills corpus specification'
        )

    def test_spec_ref_outside_the_meta_directory_raises_misplaced_specification_error(self) -> None:
        #: When
        with pytest.raises(MisplacedSpecificationError) as exc_info:
            SpecRef(RootRelativePath.parse('docs/code/logging.md'))

        #: Then
        assert exc_info.value.path == RootRelativePath.parse('docs/code/logging.md'), 'the error names the path refused'

    def test_spec_ref_with_a_readme_raises_invalid_specification_name_error(self) -> None:
        #: When
        with pytest.raises(InvalidSpecificationNameError) as exc_info:
            SpecRef(SPECS_DIR / PathComponent.parse('README.md'))

        #: Then
        assert exc_info.value.path == SPECS_DIR / PathComponent.parse('README.md'), (
            'the readme is no specification, and the error names it'
        )

    def test_spec_ref_with_a_dotted_name_raises_invalid_specification_name_error(self) -> None:
        #: When
        with pytest.raises(InvalidSpecificationNameError) as exc_info:
            SpecRef(SPECS_DIR / PathComponent.parse('code.bad.md'))

        #: Then
        assert 'code.bad.md' in str(exc_info.value), (
            'a dot in the stem is no specification name, and the error names it'
        )

    def test_spec_ref_with_a_trailing_hyphen_raises_invalid_specification_name_error(self) -> None:
        #: When
        with pytest.raises(InvalidSpecificationNameError) as exc_info:
            SpecRef(SPECS_DIR / PathComponent.parse('code-.md'))

        #: Then
        assert exc_info.value.path == SPECS_DIR / PathComponent.parse('code-.md'), (
            'an empty namespace is no specification name, and the error names it'
        )

    def test_spec_ref_with_an_uppercase_namespace_raises_invalid_specification_name_error(self) -> None:
        #: When
        with pytest.raises(InvalidSpecificationNameError) as exc_info:
            SpecRef(SPECS_DIR / PathComponent.parse('code-Upper.md'))

        #: Then
        assert 'code-Upper.md' in str(exc_info.value), (
            'an uppercase namespace is no specification name, and the error names it'
        )

    def test_describe_item_for_a_specification_reads_links_from_the_meta_directory(
        self, two_corpora_model: WorkspaceModel
    ) -> None:
        #: Given
        ref = _spec_ref('feat-cli')

        #: When
        descriptor = two_corpora_model.describe_item(ref)

        #: Then
        assert descriptor.type is ItemType.SPEC, 'the origin makes it a specification'
        assert descriptor.type.value == 'spec', 'the serialized item type uses the glossary name'
        assert descriptor.origin == SpecOrigin('feat'), 'the origin records the specification subject category'
        assert descriptor.ref == ItemRef(ref.path), 'the logical ref is also the report path'
        assert descriptor.read_location == ResolvedPath(ref.path), 'the file is read where it is listed'
        assert descriptor.link_base == DocumentDirectory(SPECS_DIR), 'links are read from docs/__meta__'
        assert descriptor.governed_parts == frozenset(), 'an absent meta corpus leaves the item ungoverned'

    def test_describe_item_for_a_specification_applies_builtin_layers_before_meta_layers(self) -> None:
        #: Given
        meta_spec = _corpus_spec('meta', structure=True)
        meta_corpus = Corpus(
            corpus_spec=meta_spec,
            namespaces=FrozenMapping({}),
            filenames=frozenset(),
        )
        ref = _spec_ref('feat-cli')
        builtin_reference = SchemaRef(SchemaKind.FRONTMATTER, 'builtin:spec-floor')
        builtin_input = SchemaInput(
            builtin_reference,
            BuiltinOrigin(builtin_reference.identity),
            FrozenMapping({}),
        )
        layer = BuiltinSpecLayer(
            BuiltinOrigin('builtin:spec-layer'),
            frozenset({ItemType.SPEC}),
            frontmatter_schema=builtin_input,
            lines=NonZeroUnsignedInt(500),
        )
        model = replace(
            WorkspaceModel(
                corpus_values=frozenset(),
                skills_dirs=frozenset(),
                skill_location_values=frozenset(),
                outside_symlink_values=frozenset(),
                load_failures=(),
                meta_corpus=meta_corpus,
                listed_specifications=(ref,),
            ),
            builtin_layers=(layer,),
        )

        #: When
        descriptor = model.describe_item(ref)

        #: Then
        assert descriptor.frontmatter_schema_refs == (
            builtin_reference,
            SchemaRef(SchemaKind.FRONTMATTER, 'meta'),
        ), 'the builtin schema is first, followed by the meta corpus schema'
        assert descriptor.governed_parts == frozenset({SpecPart.FRONTMATTER, SpecPart.STRUCTURE, SpecPart.BUDGET}), (
            'the builtin line budget and meta structure govern their corresponding parts'
        )

    def test_describe_item_for_a_specification_resolves_the_reserved_meta_corpus(
        self, two_corpora_model: WorkspaceModel
    ) -> None:
        #: Given
        meta_spec = _corpus_spec('meta', structure=True)
        namespace = _namespace_spec('meta-feat')
        meta_corpus = Corpus(
            corpus_spec=meta_spec,
            namespaces=FrozenMapping(
                {namespace.name.namespace: CorpusNamespace(files=namespace.files, structure=namespace.structure)}
            ),
            filenames=frozenset(),
        )
        ref = _spec_ref('feat-cli')
        model = replace(two_corpora_model, meta_corpus=meta_corpus, listed_specifications=(ref,))

        #: When
        resolved = model.resolve_item(ref)

        #: Then
        assert resolved.governance is not None, 'the reserved meta corpus governs specs'
        assert tuple(str(spec.name) for spec in resolved.governance.specs()) == ('meta', 'meta-feat'), (
            'the corpus and matching namespace layers apply broad to narrow'
        )
        assert resolved.descriptor.corpus == CorpusName.parse('meta'), 'the descriptor records the governing corpus'
        assert resolved.descriptor.governed_parts == frozenset({SpecPart.FRONTMATTER, SpecPart.STRUCTURE}), (
            'the shared governed-parts function resolves the layers active parts'
        )
        assert resolved.descriptor.origin == SpecOrigin('feat'), 'origin records the spec subject category'

    def test_find_item_with_a_listed_specification_returns_its_descriptor(
        self, two_corpora_model: WorkspaceModel
    ) -> None:
        #: Given
        ref = _spec_ref('feat')

        #: When
        found = two_corpora_model.find_item(ItemRef(ref.path))

        #: Then
        assert found is not None, 'the model lists the specification'
        assert found.descriptor == two_corpora_model.describe_item(ref), 'a lookup by path resolves it as the ref does'
        assert found.governance is None, 'no corpus specification governs a specification'
