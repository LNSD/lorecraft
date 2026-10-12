"""The check run's entry point over the shared runner: it adds no judgment of its own to a decoded document."""

from typing import Final

import pytest

from lorecraft import rules
from lorecraft.project.aspect import AspectFilename
from lorecraft.project.corpus import CorpusName
from lorecraft.project.database import Database, DocumentText
from lorecraft.project.document import DocumentRef
from lorecraft.rules.registry import Registry
from lorecraft.rules.selection import AllRules, RuleSelection
from lorecraft.rules.table import RuleTable
from lorecraft.vfs import Snapshot

from ..runner import judge_document
from ..skip import check_subjects

TYPING: Final[DocumentRef] = DocumentRef(CorpusName.parse('code'), AspectFilename.parse('python-typing'))
"""A document of corpus `code`, whose structure file governs its frontmatter and its outline."""

CORPUS_SPEC: Final[bytes] = (
    b'{"frontmatter": {"type": "object", "required": ["name"]}, "outline": [{"section": "Rule"}, {"any": true}]}'
)
"""A corpus structure specification that governs the frontmatter and the outline."""

DOCUMENT: Final[bytes] = b'---\nname: python-typing\n---\n\n# Typing\n\n## Rule\n\nAnnotate every signature.\n'
"""A document with a frontmatter block, a title and the section `Rule`."""


def _database() -> Database:
    """A database over a snapshot of corpus `code`, with its structure file, holding the document `TYPING`."""
    snapshot = Snapshot.from_tree(
        {
            'docs': {
                '__meta__': {'code.md': b'# Code\n', 'code.structure.json': CORPUS_SPEC},
                'code': {'python-typing.md': DOCUMENT},
            }
        }
    )
    return Database.open(snapshot)


@pytest.mark.unit
class TestCheckSubjects:
    def test_check_subjects_with_a_document_no_layer_failed_for_reports_what_the_shared_runner_judges(self) -> None:
        #: Given
        database = _database()
        table = RuleTable.from_registry(
            Registry.load(rules), RuleSelection(select=frozenset({AllRules()}), ignore=frozenset())
        )
        source = database.text(TYPING)
        assert isinstance(source, DocumentText), 'the document is UTF-8, so it decodes'

        #: When
        reports = check_subjects(database, [TYPING], table)

        #: Then
        assert reports == (judge_document(database, source, table),), (
            'the entry point decodes the document and hands it to the runner every mode shares, and adds no judgment'
        )
