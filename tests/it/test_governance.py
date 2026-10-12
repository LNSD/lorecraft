"""The `governance` query, and that a run computes a document's governance once.

The query reads the model, so it is tested over a database opened on an in-memory snapshot: a document a corpus and
a namespace specification govern, and one in a corpus the model lacks. That a run computes the governance once is
counted at the one place it is computed, `Corpus.governance`, while every reader of it runs: the runner's facet gate,
the context's `specifications()` and `corpus_structure()`, `schema_problems` and `outline_divergences`.
"""

from typing import Final

import pytest

from lorecraft import rules
from lorecraft.checks import check_subjects
from lorecraft.project.aspect import AspectFilename
from lorecraft.project.corpus import CorpusName
from lorecraft.project.database import Database
from lorecraft.project.document import DocumentRef
from lorecraft.project.workspace import Corpus, Governance
from lorecraft.rules.registry import Registry
from lorecraft.rules.selection import AllRules, RuleSelection
from lorecraft.rules.table import RuleTable
from lorecraft.vfs import Snapshot

TYPING: Final[DocumentRef] = DocumentRef(CorpusName.parse('code'), AspectFilename.parse('python-typing'))
"""A document of corpus `code` its `python` namespace governs too."""

ASYNC: Final[DocumentRef] = DocumentRef(CorpusName.parse('code'), AspectFilename.parse('python-async'))
"""A second document of corpus `code`, its `python` namespace governing it too."""

UNLISTED: Final[DocumentRef] = DocumentRef(CorpusName.parse('blog'), AspectFilename.parse('launch'))
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
    return Snapshot.from_tree(
        {
            'docs': {
                '__meta__': {
                    'code.md': b'# Code\n',
                    'code.structure.json': CORPUS_SPEC,
                    'code-python.md': b'# Code Python\n',
                    'code-python.structure.json': NAMESPACE_SPEC,
                },
                'code': {'python-typing.md': DOCUMENT, 'python-async.md': DOCUMENT},
            }
        }
    )


@pytest.mark.it
class TestGovernance:
    def test_governance_with_a_document_in_a_corpus_holds_the_corpus_and_matching_namespace_specs(self) -> None:
        #: Given
        database = Database.open(_snapshot())

        #: When
        governance = database.governance(TYPING)

        #: Then
        assert governance is not None, 'the corpus `code` is one the model holds'
        assert [spec.name.corpus for spec in governance.specs()] == [CorpusName.parse('code')] * 2, (
            'the corpus spec and the `python` namespace spec govern the document'
        )
        assert governance == database.model().find_governance(TYPING), 'the query answers what the model finds'

    def test_governance_with_a_document_in_a_corpus_the_model_lacks_holds_none(self) -> None:
        #: Given
        database = Database.open(_snapshot())

        #: When
        governance = database.governance(UNLISTED)

        #: Then
        assert governance is None, 'no specification governs a document in a corpus the model does not hold'

    def test_governance_called_twice_returns_the_first_answer(self) -> None:
        #: Given
        database = Database.open(_snapshot())
        first = database.governance(TYPING)

        #: When
        second = database.governance(TYPING)

        #: Then
        assert second is first, 'the governance is found once per database, then shared by every reader'


@pytest.mark.it
class TestRunComputesGovernanceOnce:
    def test_check_subjects_with_two_documents_computes_each_governance_once(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        #: Given
        table = RuleTable.from_registry(
            Registry.load(rules), RuleSelection(select=frozenset({AllRules()}), ignore=frozenset())
        )
        database = Database.open(_snapshot())
        computed: list[AspectFilename] = []
        original = Corpus.governance

        def counting_governance(corpus: Corpus, filename: AspectFilename) -> Governance:
            computed.append(filename)
            return original(corpus, filename)

        monkeypatch.setattr(Corpus, 'governance', counting_governance)

        #: When
        reports = check_subjects(database, (TYPING, ASYNC), table)

        #: Then
        assert len(reports) == 2, 'both documents are checked'
        assert computed == [TYPING.filename, ASYNC.filename], (
            'the facet gate, the context and the schema and outline analyses all read the one query, so each '
            'document is governed once however many readers ask'
        )
