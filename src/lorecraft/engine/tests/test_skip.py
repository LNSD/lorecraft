"""The check run's entry point over the shared runner: it adds no judgment of its own to a decoded document."""

from typing import Final

import pytest

from lib.tree import from_tree
from lorecraft import rules
from lorecraft.core.path import PathComponent, RootRelativePath
from lorecraft.project.aspect import AspectFilename
from lorecraft.project.corpus import CorpusName
from lorecraft.project.database import Database, ItemText
from lorecraft.project.document import DocumentRef, MetaSpecRef
from lorecraft.project.item import ItemRef, MetaSpecPart
from lorecraft.project.layout import SPECS_DIR
from lorecraft.rules.registry import Registry
from lorecraft.rules.report import CheckedItem, SkippedSubject, UndecodableSubject
from lorecraft.rules.selection import AllRules, RuleSelection
from lorecraft.rules.table import RuleTable
from lorecraft.vfs import OsRefusal, RefusedRead

from ..runner import judge_item
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

CODE_SPEC_PATH: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/code.spec.json')
PYTHON_SPEC_PATH: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/code-python.spec.json')

STATES_NO_RULE: Final[bytes] = b'{}'
"""A structure specification that follows the format and states no rule, so its layer fails to load."""


def _database_with(files: dict[str, bytes], documents: dict[str, bytes]) -> Database:
    """A database over corpus `code` holding the given meta spec files and documents.

    Args:
        files: The files of `docs/__meta__/`, by name.
        documents: The files of `docs/code/`, by name.
    """
    snapshot = from_tree({'docs': {'__meta__': files, 'code': documents}})
    return Database.from_snapshot(snapshot)


def _all_rules() -> RuleTable:
    """The table with every rule of the package enabled."""
    return RuleTable.from_registry(
        Registry.load(rules), RuleSelection(select=frozenset({AllRules()}), ignore=frozenset())
    )


def _database() -> Database:
    """A database over a snapshot of corpus `code`, with its structure file, holding the document `TYPING`."""
    snapshot = from_tree(
        {
            'docs': {
                '__meta__': {'code.md': b'# Code\n', 'code.spec.json': CORPUS_SPEC},
                'code': {'python-typing.md': DOCUMENT},
            }
        }
    )
    return Database.from_snapshot(snapshot)


@pytest.mark.unit
class TestCheckSubjects:
    def test_check_subjects_with_a_document_no_layer_failed_for_reports_what_the_shared_runner_judges(self) -> None:
        #: Given
        database = _database()
        table = RuleTable.from_registry(
            Registry.load(rules), RuleSelection(select=frozenset({AllRules()}), ignore=frozenset())
        )
        source = database.item_text(ItemRef(TYPING.path))
        assert isinstance(source, ItemText), 'the document is UTF-8, so it decodes'

        #: When
        reports = check_subjects(database, [TYPING], table)

        #: Then
        assert reports == (judge_item(database, source, table),), (
            'the entry point decodes the document and hands it to the runner every mode shares, and adds no judgment'
        )


@pytest.mark.unit
class TestCheckSubjectsOverASkillEntry:
    def test_check_subjects_with_a_skill_entry_reports_what_the_shared_runner_judges(self) -> None:
        #: Given
        snapshot = from_tree({'.agents': {'skills': {'review': {'SKILL.md': b'---\nname: review\n---\n\n# Review\n'}}}})
        database = Database.from_snapshot(snapshot)
        table = _all_rules()
        location = database.model().sorted_skill_locations[0]
        source = database.item_text(ItemRef(location.ref.path))
        assert isinstance(source, ItemText), 'the skill is UTF-8, so it decodes'

        #: When
        reports = check_subjects(database, [location], table)

        #: Then
        assert reports == (judge_item(database, source, table),), (
            'a skill goes through the same decode, skip policy and runner entry as a document'
        )

    def test_check_subjects_with_an_undecodable_skill_entry_reports_it_undecodable(self) -> None:
        #: Given
        snapshot = from_tree({'.agents': {'skills': {'review': {'SKILL.md': b'\xff\xfe'}}}})
        database = Database.from_snapshot(snapshot)
        location = database.model().sorted_skill_locations[0]

        #: When
        reports = check_subjects(database, [location], _all_rules())

        #: Then
        assert len(reports) == 1, 'the entry point reports the one skill it was given'
        assert isinstance(reports[0], UndecodableSubject), 'a SKILL.md that is not UTF-8 is reported undecodable'

    def test_check_subjects_with_a_failed_corpus_layer_keeps_agent_skills_checks(self) -> None:
        #: Given
        snapshot = from_tree(
            {
                'docs': {'__meta__': {'skills.spec.json': STATES_NO_RULE}},
                '.agents': {'skills': {'review': {'SKILL.md': b'---\nname: review\n---\n\n# Review\n'}}},
            }
        )
        database = Database.from_snapshot(snapshot)
        location = database.model().sorted_skill_locations[0]
        item = ItemRef(location.ref.path)
        assert database.item_governance(item) is not None, 'the reserved skills corpus governs skill entrypoints'

        #: When
        reports = check_subjects(database, [location], _all_rules())

        #: Then
        assert len(reports) == 1, 'the entry point reports the one skill it was given'
        assert isinstance(reports[0], CheckedItem), 'a failed layer leaves the skill available for package checks'
        assert [str(diagnostic.occurrence.CODE) for diagnostic in reports[0].diagnostics] == ['FM006'], (
            'the Agent Skills floor still reports its missing description'
        )

    def test_check_subjects_with_a_loaded_skills_layer_without_a_structure_file_reports_structure_ungoverned(
        self,
    ) -> None:
        #: Given
        snapshot = from_tree(
            {
                'docs': {'__meta__': {'skills.md': b'# Skills\n'}},
                '.agents': {'skills': {'review': {'SKILL.md': b'---\nname: review\n---\n\n# Review\n'}}},
            }
        )
        database = Database.from_snapshot(snapshot)
        location = database.model().sorted_skill_locations[0]
        source = database.item_text(ItemRef(location.ref.path))
        assert isinstance(source, ItemText), 'the skill is UTF-8, so it decodes'
        governance = database.item_governance(source.descriptor.ref)
        assert governance is not None, 'the loaded skills layer governs its listed entry'
        assert governance.corpus_structure() is None, 'the corpus layer has no structure file'

        #: When
        (report,) = check_subjects(database, [location], _all_rules())

        #: Then
        assert isinstance(report, CheckedItem), 'the loaded skills layer lets package checks run'
        assert MetaSpecPart.STRUCTURE in report.ungoverned, 'no structure file means structure rules are ungoverned'

    def test_check_subjects_with_a_failed_corpus_layer_still_judges_a_resource_for_markdown_checks_only(self) -> None:
        #: Given
        snapshot = from_tree(
            {
                'docs': {'__meta__': {'skills.spec.json': STATES_NO_RULE}},
                '.agents': {
                    'skills': {
                        'review': {
                            'SKILL.md': b'---\nname: review\n---\n',
                            'guide.md': b'Read [x](/x.md) and ![a](/a.png).\n',
                        }
                    }
                },
            }
        )
        database = Database.from_snapshot(snapshot)
        (location,) = database.skill_resources(database.model().sorted_skill_locations[0]).resources
        item = database.resource_item(location)
        assert database.item_governance(item) is None, 'the skills corpus does not govern resources'

        #: When
        (report,) = check_subjects(database, [location], _all_rules())

        #: Then
        assert isinstance(report, CheckedItem), 'a failed layer suppresses none of a resource, which it does not govern'
        assert report.ungoverned == (), 'resource checks are package-defined and are not gated by corpus governance'
        assert [type(item.occurrence).__name__ for item in report.diagnostics] == ['AbsoluteLink', 'AbsoluteLink'], (
            'package Markdown checks continue to judge a resource'
        )


@pytest.mark.unit
class TestCheckSubjectsWithAFailedLayer:
    def test_check_subjects_with_a_failed_corpus_spec_skips_each_document_of_the_corpus(self) -> None:
        #: Given
        database = _database_with(
            {'code.spec.json': STATES_NO_RULE, 'code-python.spec.json': CORPUS_SPEC},
            {'python-typing.md': DOCUMENT, 'logging.md': DOCUMENT},
        )
        table = _all_rules()

        #: When
        reports = check_subjects(database, [TYPING, LOGGING], table)

        #: Then
        assert reports == (
            SkippedSubject(TYPING, failed_layers=(CODE_SPEC_PATH,)),
            SkippedSubject(LOGGING, failed_layers=(CODE_SPEC_PATH,)),
        ), 'the corpus spec governs every document, so none is judged from the layers that loaded'

    def test_check_subjects_with_a_failed_namespace_spec_skips_only_the_documents_it_governs(self) -> None:
        #: Given
        database = _database_with(
            {'code.spec.json': CORPUS_SPEC, 'code-python.spec.json': STATES_NO_RULE},
            {'python-typing.md': DOCUMENT, 'logging.md': DOCUMENT},
        )
        table = _all_rules()
        logging_text = database.item_text(ItemRef(LOGGING.path))
        assert isinstance(logging_text, ItemText), 'the document is UTF-8, so it decodes'
        judged = judge_item(database, logging_text, table)

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
            {'code.spec.json': STATES_NO_RULE, 'code-python.spec.json': STATES_NO_RULE},
            {'python-typing.md': DOCUMENT},
        )
        table = _all_rules()

        #: When
        reports = check_subjects(database, [TYPING], table)

        #: Then
        assert reports == (SkippedSubject(TYPING, failed_layers=(CODE_SPEC_PATH, PYTHON_SPEC_PATH)),), (
            'every failed layer that governs the document is named, the corpus spec first'
        )

    def test_check_subjects_with_a_failed_layer_still_reports_a_document_that_does_not_decode(self) -> None:
        #: Given
        database = _database_with(
            {'code.spec.json': STATES_NO_RULE},
            {'python-typing.md': b'---\nname: caf\xe9\n---\n'},
        )
        table = _all_rules()

        #: When
        reports = check_subjects(database, [TYPING], table)

        #: Then
        assert len(reports) == 1, 'the one document has one report'
        assert isinstance(reports[0], UndecodableSubject), (
            'the document is decoded first, so a file that does not decode is reported as it is without a failure'
        )

    def test_check_subjects_with_a_failed_layer_skips_the_document_whatever_rules_the_table_enables(self) -> None:
        #: Given
        database = _database_with({'code.spec.json': STATES_NO_RULE}, {'python-typing.md': DOCUMENT})
        no_rules = RuleTable.from_registry(Registry.load(rules), RuleSelection(select=frozenset(), ignore=frozenset()))

        #: When
        reports = check_subjects(database, [TYPING], no_rules)

        #: Then
        assert reports == (SkippedSubject(TYPING, failed_layers=(CODE_SPEC_PATH,)),), (
            'a document is skipped for what governs it, not for what the run enables, so it is never read as clean'
        )


CODE_SPECIFICATION: Final[MetaSpecRef] = MetaSpecRef(SPECS_DIR / PathComponent.parse('code.md'))
"""The prose of the meta spec of corpus `code`."""


@pytest.mark.unit
class TestCheckSubjectsOverASpecification:
    def test_check_subjects_with_a_specification_reports_what_the_shared_runner_judges(self) -> None:
        #: Given
        database = _database_with({'code.md': b'# Code\n\nSee [x](/x.md).\n'}, {})
        table = _all_rules()
        source = database.item_text(ItemRef(CODE_SPECIFICATION.path))
        assert isinstance(source, ItemText), 'the specification is UTF-8, so it decodes'

        #: When
        reports = check_subjects(database, [CODE_SPECIFICATION], table)

        #: Then
        assert reports == (judge_item(database, source, table),), (
            'a specification is decoded and handed to the runner every mode shares, and the entry adds no judgment'
        )
        (report,) = reports
        assert isinstance(report, CheckedItem), 'a specification that decodes is judged'
        assert [type(item.occurrence).__name__ for item in report.diagnostics] == ['AbsoluteLink'], (
            'the link checks judge it, and no frontmatter, outline or budget rule does'
        )

    def test_check_subjects_with_an_undecodable_specification_reports_it_undecodable(self) -> None:
        #: Given
        database = _database_with({'code.md': b'\xff\xfe'}, {})

        #: When
        reports = check_subjects(database, [CODE_SPECIFICATION], _all_rules())

        #: Then
        assert len(reports) == 1, 'the entry point reports the one specification it was given'
        assert isinstance(reports[0], UndecodableSubject), 'a specification that is not UTF-8 is reported undecodable'

    def test_check_subjects_with_a_refused_read_of_the_specification_adds_no_report_of_its_own(self) -> None:
        #: Given
        database = _database_with({'code.md': b'# Code\n'}, {})
        refusals = {CODE_SPECIFICATION.path: RefusedRead(OsRefusal.PERMISSION_DENIED)}

        #: When
        reports = check_subjects(database, [CODE_SPECIFICATION], _all_rules(), refusals)

        #: Then
        assert reports == (), 'the unreadable-path report is already in the caller reports, as for a document'

    def test_check_subjects_with_a_failed_layer_of_its_corpus_still_judges_the_specification(self) -> None:
        #: Given
        database = _database_with({'code.md': b'# Code\n', 'code.spec.json': STATES_NO_RULE}, {})

        #: When
        (report,) = check_subjects(database, [CODE_SPECIFICATION], _all_rules())

        #: Then
        assert isinstance(report, CheckedItem), 'the package governs a specification, so no failed layer skips it'
