"""The check run's entry point over the shared runner: it adds no judgment of its own to a decoded document."""

from typing import Final

import pytest

from lorecraft import rules
from lorecraft.core.path import RootRelativePath
from lorecraft.project.aspect import AspectFilename
from lorecraft.project.corpus import CorpusName
from lorecraft.project.database import Database, DocumentText
from lorecraft.project.document import DocumentRef
from lorecraft.rules.registry import Registry
from lorecraft.rules.report import CheckedSubject, SkippedSubject, UndecodableSubject
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


LOGGING: Final[DocumentRef] = DocumentRef(CorpusName.parse('code'), AspectFilename.parse('logging'))
"""A document of corpus `code` no namespace spec of the corpus governs."""

CODE_SPEC_PATH: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/code.structure.json')
PYTHON_SPEC_PATH: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/code-python.structure.json')

STATES_NO_RULE: Final[bytes] = b'{}'
"""A structure specification that follows the format and states no rule, so its layer fails to load."""


def _database_with(files: dict[str, bytes], documents: dict[str, bytes]) -> Database:
    """A database over corpus `code` holding the given meta spec files and documents.

    Args:
        files: The files of `docs/__meta__/`, by name.
        documents: The files of `docs/code/`, by name.
    """
    snapshot = Snapshot.from_tree({'docs': {'__meta__': files, 'code': documents}})
    return Database.open(snapshot)


def _all_rules() -> RuleTable:
    """The table with every rule of the package enabled."""
    return RuleTable.from_registry(
        Registry.load(rules), RuleSelection(select=frozenset({AllRules()}), ignore=frozenset())
    )


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


@pytest.mark.unit
class TestCheckSubjectsWithAFailedLayer:
    def test_check_subjects_with_a_failed_corpus_spec_skips_each_document_of_the_corpus(self) -> None:
        #: Given
        database = _database_with(
            {'code.structure.json': STATES_NO_RULE, 'code-python.structure.json': CORPUS_SPEC},
            {'python-typing.md': DOCUMENT, 'logging.md': DOCUMENT},
        )

        #: When
        reports = check_subjects(database, [TYPING, LOGGING], _all_rules())

        #: Then
        assert reports == (
            SkippedSubject(TYPING, failed_layers=(CODE_SPEC_PATH,)),
            SkippedSubject(LOGGING, failed_layers=(CODE_SPEC_PATH,)),
        ), 'the corpus spec governs every document, so none is judged from the layers that loaded'

    def test_check_subjects_with_a_failed_namespace_spec_skips_only_the_documents_it_governs(self) -> None:
        #: Given
        database = _database_with(
            {'code.structure.json': CORPUS_SPEC, 'code-python.structure.json': STATES_NO_RULE},
            {'python-typing.md': DOCUMENT, 'logging.md': DOCUMENT},
        )
        table = _all_rules()
        logging_text = database.text(LOGGING)
        assert isinstance(logging_text, DocumentText), 'the document is UTF-8, so it decodes'
        judged = judge_document(database, logging_text, table)

        #: When
        reports = check_subjects(database, [TYPING, LOGGING], table)

        #: Then
        assert reports == (
            SkippedSubject(TYPING, failed_layers=(PYTHON_SPEC_PATH,)),
            judged,
        ), 'the document the namespace governs is skipped; the other is judged as if nothing had failed'

    def test_check_subjects_with_two_failed_layers_names_both_in_layer_order(self) -> None:
        #: Given
        database = _database_with(
            {'code.structure.json': STATES_NO_RULE, 'code-python.structure.json': STATES_NO_RULE},
            {'python-typing.md': DOCUMENT},
        )

        #: When
        reports = check_subjects(database, [TYPING], _all_rules())

        #: Then
        assert reports == (SkippedSubject(TYPING, failed_layers=(CODE_SPEC_PATH, PYTHON_SPEC_PATH)),), (
            'every failed layer that governs the document is named, the corpus spec first'
        )

    def test_check_subjects_with_a_failed_layer_still_reports_a_document_that_does_not_decode(self) -> None:
        #: Given
        database = _database_with(
            {'code.structure.json': STATES_NO_RULE},
            {'python-typing.md': b'---\nname: caf\xe9\n---\n'},
        )

        #: When
        reports = check_subjects(database, [TYPING], _all_rules())

        #: Then
        assert len(reports) == 1, 'the one document has one report'
        assert isinstance(reports[0], UndecodableSubject), (
            'the document is decoded first, so a file that does not decode is reported as it is without a failure'
        )

    def test_check_subjects_with_a_failed_layer_skips_the_document_whatever_rules_the_table_enables(self) -> None:
        #: Given
        database = _database_with({'code.structure.json': STATES_NO_RULE}, {'python-typing.md': DOCUMENT})
        no_rules = RuleTable.from_registry(Registry.load(rules), RuleSelection(select=frozenset(), ignore=frozenset()))

        #: When
        reports = check_subjects(database, [TYPING], no_rules)

        #: Then
        assert reports == (SkippedSubject(TYPING, failed_layers=(CODE_SPEC_PATH,)),), (
            'a document is skipped for what governs it, not for what the run enables, so it is never read as clean'
        )

    def test_check_subjects_with_no_failed_layer_judges_the_document_as_before(self) -> None:
        #: Given
        database = _database_with({'code.structure.json': CORPUS_SPEC}, {'python-typing.md': DOCUMENT})

        #: When
        reports = check_subjects(database, [TYPING], _all_rules())

        #: Then
        assert len(reports) == 1, 'the one document has one report'
        assert isinstance(reports[0], CheckedSubject), 'nothing failed, so it is judged'
