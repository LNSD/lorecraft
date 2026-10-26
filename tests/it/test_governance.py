"""The `governance` query, and that a run computes a document's governance once.

The query reads the model, so it is tested over a database opened on an in-memory snapshot: a document a corpus and
a namespace specification govern, and one in a corpus the model lacks. That a run computes the governance once is
counted at the one place it is computed, `Corpus.governance`, while every reader of it runs: the runner's facet gate,
the rules' queries, `frontmatter_schema_problems` and `outline_divergences`.
"""

from dataclasses import replace
from typing import Final

import pytest

from lib.tree import from_tree
from lorecraft import rules
from lorecraft.core.mapping import FrozenMapping
from lorecraft.core.path import RootRelativePath
from lorecraft.engine import check_subjects
from lorecraft.project.aspect import AspectFilename, AspectNamespace
from lorecraft.project.corpus import CorpusName
from lorecraft.project.database import Database
from lorecraft.project.document import DocumentRef
from lorecraft.project.item import ItemRef
from lorecraft.project.schemas.name import CorpusSpecName, NamespaceSpecName
from lorecraft.project.workspace import Corpus, CorpusNamespace, Governance
from lorecraft.project.workspace.builtin import AGENT_SKILLS_SPEC_LAYER as SKILLS_LAYER
from lorecraft.rules.registry import Registry
from lorecraft.rules.selection import AllRules, RuleSelection
from lorecraft.rules.table import RuleTable
from lorecraft.vfs import Snapshot

TYPING: Final[ItemRef] = ItemRef(RootRelativePath.parse('docs/code/python-typing.md'))
TYPING_DOCUMENT: Final[DocumentRef] = DocumentRef(CorpusName.parse('code'), AspectFilename.parse('python-typing'))
"""A document of corpus `code` its `python` namespace governs too."""

ASYNC: Final[ItemRef] = ItemRef(RootRelativePath.parse('docs/code/python-async.md'))
ASYNC_DOCUMENT: Final[DocumentRef] = DocumentRef(CorpusName.parse('code'), AspectFilename.parse('python-async'))
"""A second document of corpus `code`, its `python` namespace governing it too."""

UNLISTED: Final[ItemRef] = ItemRef(RootRelativePath.parse('docs/blog/launch.md'))
"""A document of a corpus the snapshot holds no specification of."""

CORPUS_SPEC: Final[bytes] = (
    b'{"frontmatter": {"type": "object", "required": ["name"]},'
    b' "outline": [{"section": "Rule"}, {"any": true}],'
    b' "tokens": 1000,'
    b' "empty_sections": "forbidden"}'
)
"""A corpus structure specification that governs every facet: frontmatter, outline, budget and structure."""

NAMESPACE_SPEC: Final[bytes] = b'{"frontmatter": {"type": "object", "required": ["description"]}}'
"""A `python` namespace structure specification that narrows the frontmatter schema."""

DOCUMENT: Final[bytes] = b'---\nname: python-typing\n---\n\n# Typing\n\n## Rule\n\nAnnotate every signature.\n'
"""A document with a frontmatter block, a title and the section `Rule`."""


def _snapshot() -> Snapshot:
    """A snapshot of corpus `code`, with a `python` namespace, holding the documents `TYPING` and `ASYNC`."""
    return from_tree(
        {
            'docs': {
                '__meta__': {
                    'code.md': b'# Code\n',
                    'code.spec.json': CORPUS_SPEC,
                    'code-python.md': b'# Code Python\n',
                    'code-python.spec.json': NAMESPACE_SPEC,
                },
                'code': {'python-typing.md': DOCUMENT, 'python-async.md': DOCUMENT},
            }
        }
    )


def _spec_names(governance: Governance) -> list[CorpusSpecName | NamespaceSpecName]:
    """The name of every structure specification that governs a document, in the governance's order.

    Args:
        governance: Governance of the document whose specifications are listed.
    """
    return [spec.name for spec in governance.specs()]


@pytest.mark.it
class TestGovernance:
    def test_governance_with_a_document_in_a_corpus_holds_the_corpus_and_matching_namespace_specs(self) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot(), builtin_layers=(SKILLS_LAYER,))

        #: When
        governance = database.item_governance(ItemRef(TYPING.path))

        #: Then
        assert governance is not None, 'the corpus `code` is one the model holds'
        code = CorpusName.parse('code')
        assert _spec_names(governance) == [
            CorpusSpecName(code),
            NamespaceSpecName(code, AspectNamespace.parse('python')),
        ], 'the corpus spec and the `python` namespace spec govern the document'
        assert governance == database.model().find_governance(TYPING_DOCUMENT), 'the query answers what the model finds'

    def test_governance_with_a_document_in_a_corpus_the_model_lacks_holds_none(self) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot(), builtin_layers=(SKILLS_LAYER,))

        #: When
        governance = database.item_governance(ItemRef(UNLISTED.path))

        #: Then
        assert governance is None, 'no specification governs a document in a corpus the model does not hold'

    def test_governance_called_twice_returns_the_first_answer(self) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot(), builtin_layers=(SKILLS_LAYER,))
        first = database.item_governance(ItemRef(TYPING.path))

        #: When
        second = database.item_governance(ItemRef(TYPING.path))

        #: Then
        assert second is first, 'the governance is found once per database, then shared by every reader'

    def test_governance_across_corpora_differing_only_in_an_unrelated_filename_is_equal(self) -> None:
        #: Given
        corpus = (
            Database.from_snapshot(_snapshot(), builtin_layers=(SKILLS_LAYER,))
            .model()
            .find_corpus(CorpusName.parse('code'))
        )
        assert corpus is not None, 'the snapshot declares corpus `code`'
        other_filename = AspectFilename.parse('other')
        with_other_document = replace(corpus, filenames=corpus.filenames | {other_filename})
        filename = TYPING_DOCUMENT.filename

        #: When
        governance = corpus.governance(filename)
        governance_with_other_document = with_other_document.governance(filename)

        #: Then
        assert governance == governance_with_other_document, 'a document that is not governed leaves it unchanged'
        assert hash(governance) == hash(governance_with_other_document), 'equal governances hash alike'

    def test_governance_across_corpora_differing_only_in_a_non_matching_namespace_is_equal(self) -> None:
        #: Given
        corpus = (
            Database.from_snapshot(_snapshot(), builtin_layers=(SKILLS_LAYER,))
            .model()
            .find_corpus(CorpusName.parse('code'))
        )
        assert corpus is not None, 'the snapshot declares corpus `code`'
        namespace = AspectNamespace.parse('rust')
        other_namespaces = FrozenMapping({**corpus.namespaces, namespace: CorpusNamespace(files=(), structure=None)})
        with_other_namespace = replace(corpus, namespaces=other_namespaces)
        filename = TYPING_DOCUMENT.filename

        #: When
        governance = corpus.governance(filename)
        governance_with_other_namespace = with_other_namespace.governance(filename)

        #: Then
        assert governance == governance_with_other_namespace, (
            'a spec that does not govern the document is no part of it'
        )


@pytest.mark.it
class TestRunComputesGovernanceOnce:
    def test_check_subjects_with_two_documents_computes_each_governance_once(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        #: Given
        table = RuleTable.from_registry(
            Registry.load(rules), RuleSelection(select=frozenset({AllRules()}), ignore=frozenset())
        )
        database = Database.from_snapshot(_snapshot(), builtin_layers=(SKILLS_LAYER,))
        computed: list[AspectFilename] = []
        original = Corpus.governance

        def counting_governance(corpus: Corpus, filename: AspectFilename) -> Governance:
            computed.append(filename)
            return original(corpus, filename)

        monkeypatch.setattr(Corpus, 'governance', counting_governance)

        #: When
        reports = check_subjects(database, (ItemRef(TYPING.path), ItemRef(ASYNC.path)), table)

        #: Then
        assert len(reports) == 2, 'both documents are checked'
        assert computed == [TYPING_DOCUMENT.filename, ASYNC_DOCUMENT.filename], (
            'the facet gate, the queries and the schema and outline analyses all read the one query, so each '
            'document is governed once however many readers ask'
        )
