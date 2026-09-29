"""Workspace model queries and invariants over hand-built in-memory models.

Nothing here touches the disk: every spec, corpus and ref is constructed directly, with the
header schema paths standing in for the files the loader would have read.
"""

from typing import Final

import pytest

from lorecraft_project.aspect import AspectFilename, AspectNamespace
from lorecraft_project.corpus import CorpusName
from lorecraft_project.document.ref import DocumentRef
from lorecraft_project.layout import SPECS_DIR
from lorecraft_project.schemas import (
    HeaderAspect,
    HeaderSchema,
    StructureAspect,
    parse_schema_name,
    schema_name_stem,
)
from lorecraft_vfs import RootRelativePath

from ..model import Corpus, Governance, Spec, WorkspaceModel, namespace_order_key

CODE: Final[CorpusName] = CorpusName.parse('code')
FEAT: Final[CorpusName] = CorpusName.parse('feat')


def _spec(stem: str, header: bool = True, structure: bool = False) -> Spec:
    """A spec at ``docs/__meta__/<stem>.md``, with ``<stem>.header.json`` beside it when ``header`` is set and
    ``<stem>.structure.json`` when ``structure`` is."""
    files = [SPECS_DIR / f'{stem}.md']
    header_aspect: HeaderAspect | None = None
    if header:
        header_aspect = HeaderAspect(path=SPECS_DIR / f'{stem}.header.json', schema=HeaderSchema({}))
        files.append(header_aspect.path)
    structure_aspect: StructureAspect | None = None
    if structure:
        structure_aspect = StructureAspect(
            path=SPECS_DIR / f'{stem}.structure.json',
            authority=f'{stem}.md',
            title=None,
            forbid_empty_sections=True,
            outline=(),
            forbidden=(),
        )
        files.append(structure_aspect.path)
    return Spec(
        name=parse_schema_name(stem),
        files=tuple(sorted(files, key=str)),
        header=header_aspect,
        structure=structure_aspect,
    )


def _ref(corpus: str, filename: str) -> DocumentRef:
    return DocumentRef(CorpusName.parse(corpus), AspectFilename.parse(filename))


def _code_model(specs: tuple[Spec, ...], filenames: tuple[str, ...]) -> WorkspaceModel:
    """A model with the single corpus ``code``: ``specs[0]`` is its corpus spec, the rest its namespace specs."""
    corpus = Corpus(
        name=CODE,
        spec=specs[0],
        namespace_specs=specs[1:],
        documents=tuple(_ref('code', filename) for filename in filenames),
    )
    return WorkspaceModel(corpora=(corpus,))


@pytest.mark.unit
class TestGovernance:
    def test_governance_with_the_corpus_spec_alone_returns_the_corpus_spec(self) -> None:
        #: Given
        specs = (_spec('code'),)
        filename = 'logging'
        model = _code_model(specs, (filename,))
        ref = _ref('code', filename)

        #: When
        governance = model.governance(ref)

        #: Then
        assert governance.ref == ref, 'the governance names the logging document it was asked about'
        assert tuple(schema_name_stem(spec.name) for spec in governance.specs) == ('code',), (
            'the corpus spec alone governs a document when the corpus has no namespace spec'
        )

    def test_governance_with_nested_namespaces_returns_the_matching_namespaces_broad_to_narrow(self) -> None:
        #: Given
        specs = (_spec('code'), _spec('code-pattern'), _spec('code-python'), _spec('code-python-errors'))
        filename = 'python-errors-reporting'
        model = _code_model(specs, (filename,))
        ref = _ref('code', filename)

        #: When
        governance = model.governance(ref)

        #: Then
        assert governance.ref == ref, 'the governance names the python-errors-reporting document it was asked about'
        assert tuple(schema_name_stem(spec.name) for spec in governance.specs) == (
            'code',
            'code-python',
            'code-python-errors',
        ), 'the corpus spec comes first, then python and python-errors broad to narrow, and pattern does not match'

    def test_governance_with_a_namespace_equal_to_the_filename_includes_that_namespace(self) -> None:
        #: Given
        specs = (_spec('code'), _spec('code-python'))
        filename = 'python'
        model = _code_model(specs, (filename,))
        ref = _ref('code', filename)

        #: When
        governance = model.governance(ref)

        #: Then
        assert governance.ref == ref, 'the governance names the python document it was asked about'
        assert tuple(schema_name_stem(spec.name) for spec in governance.specs) == ('code', 'code-python'), (
            'a namespace equal to the whole filename governs the document after the corpus spec'
        )

    def test_governance_with_a_namespace_that_is_only_a_prefix_excludes_that_namespace(self) -> None:
        #: Given
        specs = (_spec('code'), _spec('code-python'))
        filename = 'pythonic'
        model = _code_model(specs, (filename,))
        ref = _ref('code', filename)

        #: When
        governance = model.governance(ref)

        #: Then
        assert governance.ref == ref, 'the governance names the pythonic document it was asked about'
        assert tuple(schema_name_stem(spec.name) for spec in governance.specs) == ('code',), (
            'python is not a hyphen-delimited prefix of pythonic, so only the corpus spec governs'
        )

    def test_governance_with_a_corpus_spec_without_a_header_still_lists_the_corpus_spec_first(self) -> None:
        #: Given
        specs = (_spec('code', header=False), _spec('code-python'))
        filename = 'python-typing'
        model = _code_model(specs, (filename,))
        ref = _ref('code', filename)

        #: When
        governance = model.governance(ref)

        #: Then
        assert governance.ref == ref, 'the governance names the python-typing document it was asked about'
        assert tuple(schema_name_stem(spec.name) for spec in governance.specs) == ('code', 'code-python'), (
            'the corpus spec still governs first even without a header aspect, then the python namespace'
        )

    def test_governance_with_a_prose_only_namespace_includes_the_prose_only_namespace(self) -> None:
        #: Given
        specs = (_spec('code'), _spec('code-python', header=False))
        filename = 'python-typing'
        model = _code_model(specs, (filename,))
        ref = _ref('code', filename)

        #: When
        governance = model.governance(ref)

        #: Then
        assert governance.ref == ref, 'the governance names the python-typing document it was asked about'
        assert tuple(schema_name_stem(spec.name) for spec in governance.specs) == ('code', 'code-python'), (
            'a prose-only namespace spec still governs the document after the corpus spec'
        )

    def test_header_schemas_with_the_corpus_spec_alone_returns_the_corpus_header(self) -> None:
        #: Given
        specs = (_spec('code'),)
        filename = 'logging'
        model = _code_model(specs, (filename,))
        governance = model.governance(_ref('code', filename))

        #: When
        aspects = governance.header_schemas()

        #: Then
        assert tuple(aspect.path for aspect in aspects) == (SPECS_DIR / 'code.header.json',), (
            'the corpus header aspect is the only one when the corpus spec governs alone'
        )

    def test_header_schemas_with_nested_namespaces_returns_the_headers_broad_to_narrow(self) -> None:
        #: Given
        specs = (_spec('code'), _spec('code-pattern'), _spec('code-python'), _spec('code-python-errors'))
        filename = 'python-errors-reporting'
        model = _code_model(specs, (filename,))
        governance = model.governance(_ref('code', filename))

        #: When
        aspects = governance.header_schemas()

        #: Then
        assert tuple(aspect.path for aspect in aspects) == (
            SPECS_DIR / 'code.header.json',
            SPECS_DIR / 'code-python.header.json',
            SPECS_DIR / 'code-python-errors.header.json',
        ), 'the header aspects follow the corpus, python and python-errors specs, broad to narrow'

    def test_header_schemas_with_a_namespace_equal_to_the_filename_includes_the_namespace_header(self) -> None:
        #: Given
        specs = (_spec('code'), _spec('code-python'))
        filename = 'python'
        model = _code_model(specs, (filename,))
        governance = model.governance(_ref('code', filename))

        #: When
        aspects = governance.header_schemas()

        #: Then
        assert tuple(aspect.path for aspect in aspects) == (
            SPECS_DIR / 'code.header.json',
            SPECS_DIR / 'code-python.header.json',
        ), 'the namespace header follows the corpus header when the namespace equals the filename'

    def test_header_schemas_with_a_namespace_that_is_only_a_prefix_excludes_the_namespace_header(self) -> None:
        #: Given
        specs = (_spec('code'), _spec('code-python'))
        filename = 'pythonic'
        model = _code_model(specs, (filename,))
        governance = model.governance(_ref('code', filename))

        #: When
        aspects = governance.header_schemas()

        #: Then
        assert tuple(aspect.path for aspect in aspects) == (SPECS_DIR / 'code.header.json',), (
            'the python namespace header does not apply to pythonic, only the corpus header does'
        )

    def test_header_schemas_with_a_corpus_spec_without_a_header_returns_no_headers(self) -> None:
        #: Given
        specs = (_spec('code', header=False), _spec('code-python'))
        filename = 'python-typing'
        model = _code_model(specs, (filename,))
        governance = model.governance(_ref('code', filename))

        #: When
        aspects = governance.header_schemas()

        #: Then
        assert tuple(aspect.path for aspect in aspects) == (), (
            'a namespace never governs alone: no header applies when the corpus spec has no header aspect'
        )

    def test_header_schemas_with_a_prose_only_namespace_adds_no_namespace_header(self) -> None:
        #: Given
        specs = (_spec('code'), _spec('code-python', header=False))
        filename = 'python-typing'
        model = _code_model(specs, (filename,))
        governance = model.governance(_ref('code', filename))

        #: When
        aspects = governance.header_schemas()

        #: Then
        assert tuple(aspect.path for aspect in aspects) == (SPECS_DIR / 'code.header.json',), (
            'a prose-only namespace adds no header schema, so only the corpus header applies'
        )

    def test_structure_specs_with_nested_namespaces_returns_the_structures_broad_to_narrow(self) -> None:
        #: Given
        specs = (_spec('code', structure=True), _spec('code-python', structure=True))
        filename = 'python-typing'
        model = _code_model(specs, (filename,))
        governance = model.governance(_ref('code', filename))

        #: When
        aspects = governance.structure_specs()

        #: Then
        assert tuple(aspect.path for aspect in aspects) == (
            SPECS_DIR / 'code.structure.json',
            SPECS_DIR / 'code-python.structure.json',
        ), 'the structure aspects follow the corpus and python specs, broad to narrow'

    def test_structure_specs_with_a_corpus_spec_without_a_structure_returns_no_structures(self) -> None:
        #: Given
        specs = (_spec('code'), _spec('code-python', structure=True))
        filename = 'python-typing'
        model = _code_model(specs, (filename,))
        governance = model.governance(_ref('code', filename))

        #: When
        aspects = governance.structure_specs()

        #: Then
        assert aspects == (), (
            'a namespace never governs alone: no structure applies when the corpus spec has no structure aspect'
        )

    def test_structure_specs_with_a_namespace_without_a_structure_returns_the_corpus_structure(self) -> None:
        #: Given
        specs = (_spec('code', structure=True), _spec('code-python'))
        filename = 'python-typing'
        model = _code_model(specs, (filename,))
        governance = model.governance(_ref('code', filename))

        #: When
        aspects = governance.structure_specs()

        #: Then
        assert tuple(aspect.path for aspect in aspects) == (SPECS_DIR / 'code.structure.json',), (
            'a namespace spec without a structure file adds nothing, so only the corpus structure applies'
        )

    def test_governance_with_a_ref_of_a_corpus_the_model_lacks_raises_key_error(self) -> None:
        #: Given
        model = _code_model((_spec('code'),), ('logging',))
        foreign_ref = _ref('feat', 'cli-check')

        #: When
        with pytest.raises(KeyError):
            model.governance(foreign_ref)

        #: Then
        assert model.corpus(FEAT) is None, 'the model has no feat corpus to answer for'


@pytest.mark.unit
class TestCorpus:
    def test_governance_with_a_ref_of_another_corpus_raises_value_error(self) -> None:
        #: Given
        corpus = Corpus(name=CODE, spec=_spec('code'), namespace_specs=(), documents=())
        foreign_ref = _ref('feat', 'cli-check')

        #: When
        with pytest.raises(ValueError):
            corpus.governance(foreign_ref)

        #: Then
        assert corpus.name != foreign_ref.corpus, 'the rejected ref belongs to another corpus'

    def test_governance_with_a_matching_namespace_returns_a_governance_value(self) -> None:
        #: Given
        corpus = Corpus(
            name=CODE,
            spec=_spec('code'),
            namespace_specs=(_spec('code-python'),),
            documents=(),
        )
        ref = _ref('code', 'python-typing')

        #: When
        governance = corpus.governance(ref)

        #: Then
        assert governance == Governance(ref, (_spec('code'), _spec('code-python'))), (
            'the governance carries the ref and the corpus spec followed by the matching namespace spec'
        )

    def test_construct_with_a_namespace_stem_as_the_corpus_spec_raises_value_error(self) -> None:
        #: Given
        namespace_stem = _spec('code-python')

        #: When
        with pytest.raises(ValueError):
            Corpus(name=CODE, spec=namespace_stem, namespace_specs=(), documents=())

        #: Then
        assert namespace_stem.namespace is not None, 'the rejected spec is a namespace stem, not a corpus stem'

    def test_construct_with_the_corpus_spec_of_another_corpus_raises_value_error(self) -> None:
        #: Given
        feat_spec = _spec('feat')

        #: When
        with pytest.raises(ValueError):
            Corpus(name=CODE, spec=feat_spec, namespace_specs=(), documents=())

        #: Then
        assert feat_spec.corpus == FEAT, 'the rejected spec belongs to another corpus'

    def test_construct_with_a_corpus_stem_among_namespace_specs_raises_value_error(self) -> None:
        #: Given
        corpus_stem = _spec('code')

        #: When
        with pytest.raises(ValueError):
            Corpus(name=CODE, spec=corpus_stem, namespace_specs=(corpus_stem,), documents=())

        #: Then
        assert corpus_stem.namespace is None, 'the rejected namespace spec has no namespace'

    def test_construct_with_a_namespace_spec_of_another_corpus_raises_value_error(self) -> None:
        #: Given
        feat_namespace = _spec('feat-cli')

        #: When
        with pytest.raises(ValueError):
            Corpus(name=CODE, spec=_spec('code'), namespace_specs=(feat_namespace,), documents=())

        #: Then
        assert feat_namespace.corpus == FEAT, 'the rejected namespace spec belongs to another corpus'

    def test_construct_with_a_narrower_namespace_before_a_broader_one_raises_value_error(self) -> None:
        #: Given
        broad_to_narrow = (_spec('code-python'), _spec('code-python-errors'))
        narrow_first = (broad_to_narrow[1], broad_to_narrow[0])

        #: When
        with pytest.raises(ValueError):
            Corpus(name=CODE, spec=_spec('code'), namespace_specs=narrow_first, documents=())

        #: Then
        assert narrow_first != broad_to_narrow, 'the rejected order is the accepted order reversed'

    def test_construct_with_sibling_namespaces_out_of_value_order_raises_value_error(self) -> None:
        #: Given
        value_order = (_spec('code-pattern'), _spec('code-python'))
        unsorted_siblings = (value_order[1], value_order[0])

        #: When
        with pytest.raises(ValueError):
            Corpus(name=CODE, spec=_spec('code'), namespace_specs=unsorted_siblings, documents=())

        #: Then
        assert unsorted_siblings != value_order, 'siblings with the same segment count are accepted in value order'

    def test_construct_with_a_document_of_another_corpus_raises_value_error(self) -> None:
        #: Given
        foreign_ref = _ref('feat', 'cli-check')

        #: When
        with pytest.raises(ValueError):
            Corpus(name=CODE, spec=_spec('code'), namespace_specs=(), documents=(foreign_ref,))

        #: Then
        assert foreign_ref.corpus == FEAT, 'the rejected ref belongs to another corpus'


@pytest.mark.unit
class TestGovernanceConstruction:
    def test_construct_with_no_specs_raises_value_error(self) -> None:
        #: Given
        ref = _ref('code', 'logging')

        #: When
        with pytest.raises(ValueError):
            Governance(ref, ())

        #: Then
        assert Governance(ref, (_spec('code'),)).specs != (), 'the corpus spec alone is the smallest governance'


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
        spec=_spec('code'),
        namespace_specs=(),
        documents=(_ref('code', 'logging'), _ref('code', 'python-typing')),
    )
    feat = Corpus(
        name=FEAT,
        spec=_spec('feat'),
        namespace_specs=(),
        documents=(_ref('feat', 'cli-check'),),
    )
    return WorkspaceModel(corpora=(code, feat))


@pytest.mark.unit
class TestWorkspaceModel:
    def test_corpus_with_a_listed_name_returns_that_corpus(self, two_corpora_model: WorkspaceModel) -> None:
        #: Given
        name = FEAT

        #: When
        corpus = two_corpora_model.corpus(name)

        #: Then
        assert corpus is not None and corpus.name == FEAT, 'the corpus is found by name'

    def test_corpus_with_an_unlisted_name_returns_none(self, two_corpora_model: WorkspaceModel) -> None:
        #: Given
        name = CorpusName.parse('blog')

        #: When
        corpus = two_corpora_model.corpus(name)

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

    def test_locate_with_the_path_of_a_listed_document_returns_its_ref(self, two_corpora_model: WorkspaceModel) -> None:
        #: Given
        path = RootRelativePath.parse('docs/feat/cli-check.md')

        #: When
        ref = two_corpora_model.locate(path)

        #: Then
        assert ref == _ref('feat', 'cli-check'), 'the ref whose path equals the argument is returned'

    def test_locate_with_a_path_the_model_does_not_list_returns_none(self, two_corpora_model: WorkspaceModel) -> None:
        #: Given
        path = RootRelativePath.parse('docs/code/cli-check.md')

        #: When
        ref = two_corpora_model.locate(path)

        #: Then
        assert ref is None, 'a filename listed under another corpus does not match'


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
