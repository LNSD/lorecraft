"""The rules engine's runner over a database opened on an in-memory snapshot.

The runner decodes each document and skill, builds each input an enabled rule reads, and runs the rules of a table
built from a registry. The package's own registry runs the frontmatter block rules over documents and skills, the
token budget over documents and the line budget over skills; a registry of sample rules over the token count,
declared in this module, runs through the same runner, with no edit to it.
"""

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import ClassVar, Final, Self

import pytest

from lorecraft import rules
from lorecraft.checks import Database, DocumentText, SkillText
from lorecraft.checks.report import CheckedSubject, RuleDiagnostic, UndecodableSubject
from lorecraft.checks.runner import check_subjects
from lorecraft.checks.table import RuleTable
from lorecraft.core.mapping import FrozenMapping
from lorecraft.core.path import RootRelativePath
from lorecraft.project.aspect import AspectFilename
from lorecraft.project.corpus import CorpusName
from lorecraft.project.document import DocumentRef
from lorecraft.project.schemas import (
    BlockProblem,
    InvalidValueProblem,
    MissingFieldProblem,
    UnknownFieldProblem,
    WrongTypeProblem,
)
from lorecraft.project.skill import SkillLocation, SkillRef
from lorecraft.project.syntax import (
    FrontmatterNode,
    InvalidYamlFrontmatter,
    LineNumber,
    count_tokens,
    parse_frontmatter,
)
from lorecraft.rules.declaration import Level, Release, Rule, RuleCode, RuleGroup, RuleName, Severity
from lorecraft.rules.frontmatter.block_constraint import BlockConstraint
from lorecraft.rules.frontmatter.duplicate_key import DuplicateKey
from lorecraft.rules.frontmatter.invalid_value import InvalidValue
from lorecraft.rules.frontmatter.invalid_yaml import InvalidYaml
from lorecraft.rules.frontmatter.missing_field import MissingField
from lorecraft.rules.frontmatter.missing_frontmatter import MissingFrontmatter
from lorecraft.rules.frontmatter.name_mismatch import DirectoryNameExpected, FilenameExpected, NameMismatch
from lorecraft.rules.frontmatter.non_mapping_frontmatter import NonMappingFrontmatter
from lorecraft.rules.frontmatter.unknown_field import UnknownField
from lorecraft.rules.frontmatter.wrong_type import WrongType
from lorecraft.rules.inputs import InputKind, TokenCountInput, TokenCountRule
from lorecraft.rules.length.too_many_lines import TooManyLines
from lorecraft.rules.length.too_many_tokens import TooManyTokens
from lorecraft.rules.registry import Registry
from lorecraft.vfs import EntryRecord, ResolvedPath, Snapshot, SymlinkRecord

GUIDE: Final[DocumentRef] = DocumentRef(CorpusName.parse('code'), AspectFilename.parse('guide'))
"""A document of corpus `code`."""

INTRO: Final[DocumentRef] = DocumentRef(CorpusName.parse('code'), AspectFilename.parse('intro'))
"""A second document of corpus `code`."""

REVIEW: Final[SkillRef] = SkillRef(RootRelativePath.parse('.agents/skills/review'))
"""A skill an agent reaches under `.agents/skills`."""

GUIDE_TEXT: Final[str] = '# Guide\n\nInstall the toolkit, then run it once over the repository.\n'
"""The text of `GUIDE`."""

CODE_SPEC: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/code.structure.json')
"""The corpus structure specification."""

REVIEW_FILE: Final[RootRelativePath] = RootRelativePath.parse('.agents/skills/review/SKILL.md')
"""Where `REVIEW` is reported: its `SKILL.md`, under the skills directory an agent lists it in."""

OBJECT_SCHEMA: Final[bytes] = b'{"frontmatter": {"type": "object"}}'
"""A corpus structure specification whose frontmatter schema accepts any mapping, and which sets no budget."""

REVIEW_FRONTMATTER: Final[bytes] = b'---\nname: review\ndescription: Review a change before it is merged.\n---\n'
"""A frontmatter of four lines the Agent Skills specification accepts, for `REVIEW`."""

GUIDE_SCHEMA: Final[bytes] = (
    b'{"frontmatter": {"type": "object", "required": ["name", "owner"], "minProperties": 6, '
    b'"properties": {"name": {"type": "string"}, "description": {"type": "string"}, '
    b'"status": {"type": "string", "pattern": "^(draft|stable)$"}}, "additionalProperties": false}}'
)
"""A structure specification whose frontmatter schema each kind of schema problem can break."""

SAMPLE: Final[RuleGroup] = RuleGroup('SMP', 'Sample rules')
"""The group of the sample rules this module declares."""


@dataclass(frozen=True, slots=True, kw_only=True)
class OverHalfBudget(TokenCountRule):
    """A sample rule at `warn`: a document holds more than half the tokens a budget allows.

    Attributes:
        spec: The structure specification that sets the budget.
        token_count: The tokens in the document's whole file.
        budget: The budget, in tokens.
    """

    CODE: ClassVar[RuleCode] = RuleCode(SAMPLE, 1)
    NAME: ClassVar[RuleName] = RuleName('over-half-budget')
    LEVEL: ClassVar[Level] = Level.WARN
    SINCE: ClassVar[Release] = Release('1.0.0')

    spec: RootRelativePath
    token_count: int
    budget: int

    def message(self) -> str:
        """Name the tokens found against the budget."""
        return f'over half the budget ({self.token_count} of {self.budget})'

    @classmethod
    def check(cls, subject: TokenCountInput) -> tuple[Self, ...]:
        """One occurrence for each budget the document holds more than half of.

        Args:
            subject: The document's token count, with the budgets that govern it.
        """
        return tuple(
            cls(
                spec=budget.spec,
                line=LineNumber.from_int(1),
                token_count=subject.token_count.value,
                budget=budget.tokens.value,
            )
            for budget in subject.budgets
            if subject.token_count.value * 2 > budget.tokens.value
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class EmptyDocument(TokenCountRule):
    """A sample rule at `allow`: a document holds no token at all."""

    CODE: ClassVar[RuleCode] = RuleCode(SAMPLE, 2)
    NAME: ClassVar[RuleName] = RuleName('empty-document')
    LEVEL: ClassVar[Level] = Level.ALLOW
    SINCE: ClassVar[Release] = Release('1.0.0')

    def message(self) -> str:
        """Name the condition."""
        return 'document is empty'

    @classmethod
    def check(cls, subject: TokenCountInput) -> tuple[Self, ...]:
        """The occurrence at line 1, when the document has no token.

        Args:
            subject: The document's token count, with the budgets that govern it.
        """
        if subject.token_count.value > 0:
            return ()
        return (cls(spec=None, line=LineNumber.from_int(1)),)


@dataclass(frozen=True, slots=True, kw_only=True)
class AnyTokens(TokenCountRule):
    """A sample rule at `deny` that fires once on every document a budget governs, whatever its token count.

    Attributes:
        token_count: The tokens in the document's whole file.
    """

    CODE: ClassVar[RuleCode] = RuleCode(SAMPLE, 3)
    NAME: ClassVar[RuleName] = RuleName('any-tokens')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('1.0.0')

    token_count: int

    def message(self) -> str:
        """Name the tokens counted."""
        return f'document counted ({self.token_count} tokens)'

    @classmethod
    def check(cls, subject: TokenCountInput) -> tuple[Self, ...]:
        """One occurrence at line 1, whatever the count.

        Args:
            subject: The document's token count, with the budgets that govern it.
        """
        return (cls(spec=None, line=LineNumber.from_int(1), token_count=subject.token_count.value),)


class CountingDatabase(Database):
    """A database that records each document and skill whose tokens, lines or frontmatter it is asked for."""

    def __init__(self, snapshot: Snapshot) -> None:
        """Open the database on the snapshot, with nothing counted yet.

        Args:
            snapshot: The revision the database reads.
        """
        super().__init__(snapshot)
        self.counted_tokens: list[DocumentRef] = []
        self.counted_lines: list[SkillRef] = []
        self.parsed_frontmatters: list[DocumentRef | SkillRef] = []

    def tokens(self, source: DocumentText) -> int:
        """Record the document, then count its tokens.

        Args:
            source: The decoded document whose tokens are counted, recorded by its ref first.
        """
        self.counted_tokens.append(source.ref)
        return super().tokens(source)

    def skill_lines(self, source: SkillText) -> int:
        """Record the skill, then count the lines of its `SKILL.md`.

        Args:
            source: The decoded `SKILL.md` whose lines are counted, recorded by its skill's ref first.
        """
        self.counted_lines.append(source.ref)
        return super().skill_lines(source)

    def frontmatter(self, source: DocumentText) -> FrontmatterNode:
        """Record the document, then parse its frontmatter.

        Args:
            source: The decoded document whose frontmatter is parsed, recorded by its ref first.
        """
        self.parsed_frontmatters.append(source.ref)
        return super().frontmatter(source)

    def skill_frontmatter(self, source: SkillText) -> FrontmatterNode:
        """Record the skill, then parse the frontmatter of its `SKILL.md`.

        Args:
            source: The decoded `SKILL.md` whose frontmatter is parsed, recorded by its skill's ref first.
        """
        self.parsed_frontmatters.append(source.ref)
        return super().skill_frontmatter(source)


def _snapshot(
    structure_spec: bytes, *, guide: bytes, intro: bytes = b'# Intro\n', review: bytes = REVIEW_FRONTMATTER
) -> Snapshot:
    """A snapshot of corpus `code`, holding the documents `GUIDE` and `INTRO`, and the skill `REVIEW`.

    Args:
        structure_spec: Bytes of the corpus structure specification.
        guide: Bytes of `GUIDE`.
        intro: Bytes of `INTRO`.
        review: Bytes of `REVIEW`'s `SKILL.md`; by default `REVIEW_FRONTMATTER` and nothing else.
    """
    return Snapshot.from_tree(
        {
            '.agents': {'skills': {'review': {'SKILL.md': review}}},
            'docs': {
                '__meta__': {'code.md': b'# Code\n', 'code.structure.json': structure_spec},
                'code': {'guide.md': guide, 'intro.md': intro},
            },
        }
    )


def _skill_of(lines: int) -> bytes:
    """The bytes of a `SKILL.md` of exactly `lines` lines: `REVIEW_FRONTMATTER`, then one step per line.

    Args:
        lines: The lines the file holds; at least 4, for the frontmatter.
    """
    return REVIEW_FRONTMATTER + b'Run the next step.\n' * (lines - 4)


def _location(database: Database, ref: SkillRef) -> SkillLocation:
    """The location the database's model hands out for a skill the test wrote into a skills directory.

    Args:
        database: The database whose model lists the skill.
        ref: A skill the snapshot holds in an agent's skills directory.
    """
    location = database.model().find_skill_location(ref.directory)
    assert location is not None, f'the model lists the skill {ref.directory}'
    return location


def _invalid_yaml_problem(text: str) -> str:
    """What the YAML parser finds wrong with the frontmatter of a text whose block is not YAML.

    Args:
        text: A whole document or `SKILL.md`, whose block the test wrote as invalid YAML.
    """
    frontmatter = parse_frontmatter(text)
    assert isinstance(frontmatter, InvalidYamlFrontmatter), 'the test wrote a block that is not YAML'
    return frontmatter.problem


def _budget(tokens: int) -> bytes:
    """A structure specification that sets a token budget and nothing else.

    Args:
        tokens: The most tokens the specification lets a document it governs hold; at least 1.
    """
    return f'{{"tokens": {tokens}}}'.encode()


@pytest.fixture(scope='module')
def package_table() -> RuleTable:
    """The rule table of the package's own rules at their default levels; immutable, so shared by the module."""
    return RuleTable.from_registry(Registry.load(rules))


@pytest.fixture(scope='module')
def sample_table() -> RuleTable:
    """The rule table of the sample rules this module declares, one at each level; immutable, so shared by the module.

    The registry holds the sample rules as it would hold any rule, so they reach the runner through the table alone.
    """
    return RuleTable.from_registry(Registry((OverHalfBudget, EmptyDocument, AnyTokens)))


@pytest.mark.it
class TestCheckSubjects:
    def test_check_subjects_with_a_document_over_its_budget_reports_the_token_budget_as_an_error(
        self, package_table: RuleTable
    ) -> None:
        #: Given
        database = Database(_snapshot(_budget(5), guide=GUIDE_TEXT.encode()))

        #: When
        reports = check_subjects(database, (GUIDE,), package_table)

        #: Then
        occurrence = TooManyTokens(
            spec=CODE_SPEC, line=LineNumber.from_int(1), token_count=count_tokens(GUIDE_TEXT), budget=5
        )
        assert reports == (
            CheckedSubject(
                GUIDE,
                diagnostics=(RuleDiagnostic(GUIDE.path, occurrence, Severity.ERROR),),
                ungoverned=(InputKind.FRONTMATTER_BLOCK, InputKind.SCHEMA_PROBLEMS),
            ),
        ), 'LEN001 runs at deny, so a document over its budget carries its occurrence as an error'

    def test_check_subjects_with_a_document_within_its_budget_reports_it_clean(self, package_table: RuleTable) -> None:
        #: Given
        database = Database(_snapshot(_budget(1000), guide=GUIDE_TEXT.encode()))

        #: When
        reports = check_subjects(database, (GUIDE,), package_table)

        #: Then
        assert reports == (
            CheckedSubject(GUIDE, diagnostics=(), ungoverned=(InputKind.FRONTMATTER_BLOCK, InputKind.SCHEMA_PROBLEMS)),
        ), 'a document within its budget has no diagnostic, and no frontmatter schema governs it'

    def test_check_subjects_with_no_budget_set_reports_the_token_count_as_ungoverned(
        self, package_table: RuleTable
    ) -> None:
        #: Given
        database = Database(_snapshot(b'{"empty_sections": "forbidden"}', guide=GUIDE_TEXT.encode()))

        #: When
        reports = check_subjects(database, (GUIDE,), package_table)

        #: Then
        assert reports == (
            CheckedSubject(
                GUIDE,
                diagnostics=(),
                ungoverned=(InputKind.FRONTMATTER_BLOCK, InputKind.SCHEMA_PROBLEMS, InputKind.TOKEN_COUNT),
            ),
        ), 'no specification sets a budget or a frontmatter schema, which is coverage, not a diagnostic'

    def test_check_subjects_with_a_document_in_no_corpus_reports_the_token_count_as_ungoverned(
        self, package_table: RuleTable
    ) -> None:
        #: Given
        # the code corpus sets a budget, but `docs/blog/` has no corpus spec, so the model holds no `blog` corpus
        snapshot = Snapshot.from_tree(
            {
                'docs': {
                    '__meta__': {'code.md': b'# Code\n', 'code.structure.json': _budget(5)},
                    'blog': {'launch.md': GUIDE_TEXT.encode()},
                }
            }
        )
        database = Database(snapshot)
        launch = DocumentRef(CorpusName.parse('blog'), AspectFilename.parse('launch'))

        #: When
        reports = check_subjects(database, (launch,), package_table)

        #: Then
        assert reports == (
            CheckedSubject(
                launch,
                diagnostics=(),
                ungoverned=(InputKind.FRONTMATTER_BLOCK, InputKind.SCHEMA_PROBLEMS, InputKind.TOKEN_COUNT),
            ),
        ), 'no specification governs a document in no corpus the model holds, which is coverage, not a diagnostic'

    def test_check_subjects_with_an_undecodable_document_reports_it_undecodable(self, package_table: RuleTable) -> None:
        #: Given
        database = Database(_snapshot(_budget(1000), guide=b'# Caf\xe9\n'))

        #: When
        reports = check_subjects(database, (GUIDE,), package_table)

        #: Then
        assert reports == (UndecodableSubject(GUIDE),), 'a document that is not UTF-8 is judged by no rule'

    def test_check_subjects_with_an_undecodable_ungoverned_document_reports_it_undecodable(
        self, package_table: RuleTable
    ) -> None:
        #: Given
        database = Database(_snapshot(b'{"empty_sections": "forbidden"}', guide=b'# Caf\xe9\n'))

        #: When
        reports = check_subjects(database, (GUIDE,), package_table)

        #: Then
        assert reports == (UndecodableSubject(GUIDE),), (
            'a document is decoded before governance is read, so it is undecodable whatever governs it'
        )

    def test_check_subjects_with_several_documents_reports_them_in_the_order_given(
        self, package_table: RuleTable
    ) -> None:
        #: Given
        database = Database(_snapshot(_budget(1000), guide=GUIDE_TEXT.encode()))

        #: When
        reports = check_subjects(database, (INTRO, GUIDE), package_table)

        #: Then
        assert [report.ref for report in reports] == [INTRO, GUIDE], 'each document is reported in the order given'

    def test_check_subjects_with_no_enabled_rule_over_the_token_count_never_counts_the_tokens(self) -> None:
        #: Given
        database = CountingDatabase(_snapshot(_budget(5), guide=GUIDE_TEXT.encode()))
        severities: dict[type[Rule], Severity] = {}
        table = RuleTable(severities)

        #: When
        check_subjects(database, (GUIDE,), table)

        #: Then
        assert database.counted_tokens == [], (
            'an input no enabled rule reads is never built, so its query is never asked'
        )

    def test_check_subjects_with_sample_rules_reports_each_at_its_level(self, sample_table: RuleTable) -> None:
        #: Given
        # a budget the document holds more than half of, and less than all of
        token_count_of_guide = count_tokens(GUIDE_TEXT)
        database = Database(_snapshot(_budget(token_count_of_guide + 1), guide=GUIDE_TEXT.encode()))

        #: When
        reports = check_subjects(database, (GUIDE,), sample_table)

        #: Then
        over_half = OverHalfBudget(
            spec=CODE_SPEC,
            line=LineNumber.from_int(1),
            token_count=token_count_of_guide,
            budget=token_count_of_guide + 1,
        )
        any_tokens = AnyTokens(spec=None, line=LineNumber.from_int(1), token_count=token_count_of_guide)
        assert reports == (
            CheckedSubject(
                GUIDE,
                diagnostics=(
                    RuleDiagnostic(GUIDE.path, any_tokens, Severity.ERROR),
                    RuleDiagnostic(GUIDE.path, over_half, Severity.WARNING),
                ),
                ungoverned=(),
            ),
        ), 'each sample rule runs at its level through the registry alone, the error sorted before the warning'

    def test_check_subjects_with_a_sample_rule_at_allow_never_runs_it(self, sample_table: RuleTable) -> None:
        #: Given
        # an empty document, which the sample rule at allow, empty-document, would report
        database = Database(_snapshot(_budget(10), guide=b''))

        #: When
        reports = check_subjects(database, (GUIDE,), sample_table)

        #: Then
        any_tokens = AnyTokens(spec=None, line=LineNumber.from_int(1), token_count=0)
        assert reports == (
            CheckedSubject(GUIDE, diagnostics=(RuleDiagnostic(GUIDE.path, any_tokens, Severity.ERROR),), ungoverned=()),
        ), 'a rule at allow is not in the table, so only the enabled rules report'

    def test_check_subjects_with_a_skill_over_the_line_budget_reports_the_line_budget_as_an_error(
        self, package_table: RuleTable
    ) -> None:
        #: Given
        database = Database(_snapshot(_budget(1000), guide=GUIDE_TEXT.encode(), review=_skill_of(501)))

        #: When
        reports = check_subjects(database, (_location(database, REVIEW),), package_table)

        #: Then
        occurrence = TooManyLines(line=LineNumber.from_int(1), line_count=501)
        skill_file = RootRelativePath.parse('.agents/skills/review/SKILL.md')
        assert reports == (
            CheckedSubject(
                REVIEW, diagnostics=(RuleDiagnostic(skill_file, occurrence, Severity.ERROR),), ungoverned=()
            ),
        ), 'LEN002 runs at deny, so a skill over the budget carries its occurrence as an error, at its SKILL.md'

    def test_check_subjects_with_a_linked_skill_over_the_line_budget_reports_it_where_an_agent_reaches_it(
        self, package_table: RuleTable
    ) -> None:
        #: Given
        # What a scan records for `.agents/skills/review -> ../../skills/review`: the link in the skills directory,
        # and the SKILL.md at the resolved path it leads to.
        shipped = Snapshot.from_tree({'.agents': {'skills': {}}, 'skills': {'review': {'SKILL.md': _skill_of(501)}}})
        records: dict[RootRelativePath, EntryRecord] = dict(shipped.records)
        records[RootRelativePath.parse('.agents/skills/review')] = SymlinkRecord(PurePosixPath('../../skills/review'))
        database = Database(Snapshot(FrozenMapping(records)))

        #: When
        reports = check_subjects(database, (_location(database, REVIEW),), package_table)

        #: Then
        occurrence = TooManyLines(line=LineNumber.from_int(1), line_count=501)
        skill_file = RootRelativePath.parse('.agents/skills/review/SKILL.md')
        assert reports == (
            CheckedSubject(
                REVIEW, diagnostics=(RuleDiagnostic(skill_file, occurrence, Severity.ERROR),), ungoverned=()
            ),
        ), 'the SKILL.md is counted where the link leads, and reported under the skills directory, not under skills/'

    def test_check_subjects_with_a_skill_at_the_line_budget_reports_it_clean(self, package_table: RuleTable) -> None:
        #: Given
        database = Database(_snapshot(_budget(1000), guide=GUIDE_TEXT.encode(), review=_skill_of(500)))

        #: When
        reports = check_subjects(database, (_location(database, REVIEW),), package_table)

        #: Then
        assert reports == (CheckedSubject(REVIEW, diagnostics=(), ungoverned=()),), (
            'a SKILL.md of exactly 500 lines is within the budget, and the package governs its line count'
        )

    def test_check_subjects_with_an_undecodable_skill_reports_it_undecodable(self, package_table: RuleTable) -> None:
        #: Given
        database = Database(_snapshot(_budget(1000), guide=GUIDE_TEXT.encode(), review=b'---\nname: caf\xe9\n---\n'))

        #: When
        reports = check_subjects(database, (_location(database, REVIEW),), package_table)

        #: Then
        assert reports == (UndecodableSubject(REVIEW),), 'a skill whose SKILL.md is not UTF-8 is judged by no rule'

    def test_check_subjects_with_documents_and_skills_reports_them_in_the_order_given(
        self, package_table: RuleTable
    ) -> None:
        #: Given
        database = Database(_snapshot(_budget(1000), guide=GUIDE_TEXT.encode()))

        #: When
        reports = check_subjects(database, (GUIDE, _location(database, REVIEW), INTRO), package_table)

        #: Then
        assert reports == (
            CheckedSubject(GUIDE, diagnostics=(), ungoverned=(InputKind.FRONTMATTER_BLOCK, InputKind.SCHEMA_PROBLEMS)),
            CheckedSubject(REVIEW, diagnostics=(), ungoverned=()),
            CheckedSubject(INTRO, diagnostics=(), ungoverned=(InputKind.FRONTMATTER_BLOCK, InputKind.SCHEMA_PROBLEMS)),
        ), 'documents and skills share one run, each reported in the order given'

    def test_check_subjects_with_no_enabled_rule_over_the_line_count_never_counts_the_lines(self) -> None:
        #: Given
        # only the token budget is enabled, and the skill is over the line budget
        database = CountingDatabase(_snapshot(_budget(1000), guide=GUIDE_TEXT.encode(), review=_skill_of(501)))
        severities: dict[type[Rule], Severity] = {TooManyTokens: Severity.ERROR}
        table = RuleTable(severities)

        #: When
        check_subjects(database, (_location(database, REVIEW),), table)

        #: Then
        assert database.counted_lines == [], (
            'an input no enabled rule reads is never built, so its query is never asked'
        )

    def test_check_subjects_with_a_document_without_a_block_reports_missing_frontmatter(
        self, package_table: RuleTable
    ) -> None:
        #: Given
        database = Database(_snapshot(OBJECT_SCHEMA, guide=GUIDE_TEXT.encode()))

        #: When
        reports = check_subjects(database, (GUIDE,), package_table)

        #: Then
        occurrence = MissingFrontmatter(spec=CODE_SPEC, line=LineNumber.from_int(1))
        assert reports == (
            CheckedSubject(
                GUIDE,
                diagnostics=(RuleDiagnostic(GUIDE.path, occurrence, Severity.ERROR),),
                ungoverned=(InputKind.TOKEN_COUNT,),
            ),
        ), 'FM001 runs at deny over a document a frontmatter schema governs, under its corpus specification'

    def test_check_subjects_with_a_document_whose_block_is_not_yaml_reports_invalid_yaml(
        self, package_table: RuleTable
    ) -> None:
        #: Given
        guide = '---\nname: [guide\n---\n# Guide\n'
        database = Database(_snapshot(OBJECT_SCHEMA, guide=guide.encode()))

        #: When
        reports = check_subjects(database, (GUIDE,), package_table)

        #: Then
        occurrence = InvalidYaml(spec=CODE_SPEC, line=LineNumber.from_int(3), problem=_invalid_yaml_problem(guide))
        assert reports == (
            CheckedSubject(
                GUIDE,
                diagnostics=(RuleDiagnostic(GUIDE.path, occurrence, Severity.ERROR),),
                ungoverned=(InputKind.TOKEN_COUNT,),
            ),
        ), 'FM002 runs at deny, at the line the YAML parser stopped on'

    def test_check_subjects_with_a_document_whose_block_is_a_list_reports_non_mapping_frontmatter(
        self, package_table: RuleTable
    ) -> None:
        #: Given
        database = Database(_snapshot(OBJECT_SCHEMA, guide=b'---\n- guide\n---\n# Guide\n'))

        #: When
        reports = check_subjects(database, (GUIDE,), package_table)

        #: Then
        occurrence = NonMappingFrontmatter(spec=CODE_SPEC, line=LineNumber.from_int(1))
        assert reports == (
            CheckedSubject(
                GUIDE,
                diagnostics=(RuleDiagnostic(GUIDE.path, occurrence, Severity.ERROR),),
                ungoverned=(InputKind.TOKEN_COUNT,),
            ),
        ), 'FM003 runs at deny over a block that reads as YAML but is not a mapping'

    def test_check_subjects_with_a_document_named_otherwise_reports_name_mismatch(
        self, package_table: RuleTable
    ) -> None:
        #: Given
        database = Database(_snapshot(OBJECT_SCHEMA, guide=b'---\nname: setup\n---\n# Guide\n'))

        #: When
        reports = check_subjects(database, (GUIDE,), package_table)

        #: Then
        occurrence = NameMismatch(
            spec=CODE_SPEC, line=LineNumber.from_int(2), name='setup', expectation=FilenameExpected('guide')
        )
        assert reports == (
            CheckedSubject(
                GUIDE,
                diagnostics=(RuleDiagnostic(GUIDE.path, occurrence, Severity.ERROR),),
                ungoverned=(InputKind.TOKEN_COUNT,),
            ),
        ), 'FM004 runs at deny over a document whose `name` is not its filename'

    def test_check_subjects_with_a_document_repeating_a_key_reports_duplicate_key(
        self, package_table: RuleTable
    ) -> None:
        #: Given
        database = Database(_snapshot(OBJECT_SCHEMA, guide=b'---\nname: guide\nname: guide\n---\n# Guide\n'))

        #: When
        reports = check_subjects(database, (GUIDE,), package_table)

        #: Then
        occurrence = DuplicateKey(
            spec=CODE_SPEC, line=LineNumber.from_int(3), key='name', first_line=LineNumber.from_int(2)
        )
        assert reports == (
            CheckedSubject(
                GUIDE,
                diagnostics=(RuleDiagnostic(GUIDE.path, occurrence, Severity.ERROR),),
                ungoverned=(InputKind.TOKEN_COUNT,),
            ),
        ), 'FM005 runs at deny over a key written again, at the later occurrence'

    def test_check_subjects_with_a_skill_without_a_block_reports_missing_frontmatter(
        self, package_table: RuleTable
    ) -> None:
        #: Given
        database = Database(_snapshot(_budget(1000), guide=GUIDE_TEXT.encode(), review=b'# Review\n'))

        #: When
        reports = check_subjects(database, (_location(database, REVIEW),), package_table)

        #: Then
        occurrence = MissingFrontmatter(spec=None, line=LineNumber.from_int(1))
        assert reports == (
            CheckedSubject(
                REVIEW, diagnostics=(RuleDiagnostic(REVIEW_FILE, occurrence, Severity.ERROR),), ungoverned=()
            ),
        ), 'every skill is governed for its frontmatter, so FM001 needs no specification in the repository'

    def test_check_subjects_with_a_skill_whose_block_is_not_yaml_reports_invalid_yaml(
        self, package_table: RuleTable
    ) -> None:
        #: Given
        review = '---\nname: [review\n---\n'
        database = Database(_snapshot(_budget(1000), guide=GUIDE_TEXT.encode(), review=review.encode()))

        #: When
        reports = check_subjects(database, (_location(database, REVIEW),), package_table)

        #: Then
        occurrence = InvalidYaml(spec=None, line=LineNumber.from_int(3), problem=_invalid_yaml_problem(review))
        assert reports == (
            CheckedSubject(
                REVIEW, diagnostics=(RuleDiagnostic(REVIEW_FILE, occurrence, Severity.ERROR),), ungoverned=()
            ),
        ), 'FM002 runs at deny over a skill, at the line the YAML parser stopped on'

    def test_check_subjects_with_a_skill_whose_block_is_a_list_reports_non_mapping_frontmatter(
        self, package_table: RuleTable
    ) -> None:
        #: Given
        database = Database(_snapshot(_budget(1000), guide=GUIDE_TEXT.encode(), review=b'---\n- review\n---\n'))

        #: When
        reports = check_subjects(database, (_location(database, REVIEW),), package_table)

        #: Then
        occurrence = NonMappingFrontmatter(spec=None, line=LineNumber.from_int(1))
        assert reports == (
            CheckedSubject(
                REVIEW, diagnostics=(RuleDiagnostic(REVIEW_FILE, occurrence, Severity.ERROR),), ungoverned=()
            ),
        ), 'FM003 runs at deny over a skill whose block is not a mapping'

    def test_check_subjects_with_a_skill_named_otherwise_reports_name_mismatch(self, package_table: RuleTable) -> None:
        #: Given
        database = Database(
            _snapshot(
                _budget(1000),
                guide=GUIDE_TEXT.encode(),
                review=b'---\nname: code-review\ndescription: Review a change.\n---\n',
            )
        )

        #: When
        reports = check_subjects(database, (_location(database, REVIEW),), package_table)

        #: Then
        occurrence = NameMismatch(
            spec=None,
            line=LineNumber.from_int(2),
            name='code-review',
            expectation=DirectoryNameExpected(directory_name='review', link_target=None),
        )
        assert reports == (
            CheckedSubject(
                REVIEW, diagnostics=(RuleDiagnostic(REVIEW_FILE, occurrence, Severity.ERROR),), ungoverned=()
            ),
        ), 'FM004 runs at deny over a skill whose `name` is not its directory name'

    def test_check_subjects_with_a_skill_repeating_a_key_reports_duplicate_key(self, package_table: RuleTable) -> None:
        #: Given
        database = Database(
            _snapshot(
                _budget(1000),
                guide=GUIDE_TEXT.encode(),
                review=b'---\nname: review\nname: review\ndescription: Review a change.\n---\n',
            )
        )

        #: When
        reports = check_subjects(database, (_location(database, REVIEW),), package_table)

        #: Then
        occurrence = DuplicateKey(spec=None, line=LineNumber.from_int(3), key='name', first_line=LineNumber.from_int(2))
        assert reports == (
            CheckedSubject(
                REVIEW, diagnostics=(RuleDiagnostic(REVIEW_FILE, occurrence, Severity.ERROR),), ungoverned=()
            ),
        ), 'FM005 runs at deny over a skill that writes a key again'

    def test_check_subjects_with_a_linked_skill_named_for_its_target_reports_where_the_link_leads(
        self, package_table: RuleTable
    ) -> None:
        #: Given
        # What a scan records for `.agents/skills/review -> ../../skills/code-review`, whose `name` is the target's.
        shipped = Snapshot.from_tree(
            {
                '.agents': {'skills': {}},
                'skills': {
                    'code-review': {'SKILL.md': b'---\nname: code-review\ndescription: Review a change.\n---\n'}
                },
            }
        )
        records: dict[RootRelativePath, EntryRecord] = dict(shipped.records)
        records[RootRelativePath.parse('.agents/skills/review')] = SymlinkRecord(
            PurePosixPath('../../skills/code-review')
        )
        database = Database(Snapshot(FrozenMapping(records)))

        #: When
        reports = check_subjects(database, (_location(database, REVIEW),), package_table)

        #: Then
        occurrence = NameMismatch(
            spec=None,
            line=LineNumber.from_int(2),
            name='code-review',
            expectation=DirectoryNameExpected(
                directory_name='review', link_target=ResolvedPath(RootRelativePath.parse('skills/code-review'))
            ),
        )
        assert reports == (
            CheckedSubject(
                REVIEW, diagnostics=(RuleDiagnostic(REVIEW_FILE, occurrence, Severity.ERROR),), ungoverned=()
            ),
        ), 'a skill is held to the name it is listed under, and its occurrence carries where the link leads'

    def test_check_subjects_with_no_enabled_rule_over_the_frontmatter_block_never_parses_the_frontmatter(
        self,
    ) -> None:
        #: Given
        # a frontmatter schema governs the document, which has no block, and the skill has none either
        database = CountingDatabase(_snapshot(OBJECT_SCHEMA, guide=GUIDE_TEXT.encode(), review=b'# Review\n'))
        severities: dict[type[Rule], Severity] = {TooManyTokens: Severity.ERROR, TooManyLines: Severity.ERROR}
        table = RuleTable(severities)

        #: When
        check_subjects(database, (GUIDE, _location(database, REVIEW)), table)

        #: Then
        assert database.parsed_frontmatters == [], (
            'an input no enabled rule reads is never built, so no frontmatter is parsed or held to a schema'
        )

    def test_check_subjects_with_every_package_rule_asks_for_each_frontmatter_once_per_input(
        self, package_table: RuleTable
    ) -> None:
        #: Given
        # every FM rule reads the one frontmatter-block input, built once per subject
        database = CountingDatabase(_snapshot(OBJECT_SCHEMA, guide=GUIDE_TEXT.encode()))

        #: When
        check_subjects(database, (GUIDE, _location(database, REVIEW), INTRO), package_table)

        #: Then
        assert database.parsed_frontmatters == [GUIDE, GUIDE, REVIEW, REVIEW, INTRO, INTRO], (
            'the frontmatter query is asked once per input that reads it, the block and the schema problems, '
            'however many rules read each input'
        )

    def test_check_subjects_with_a_document_breaking_its_schema_reports_each_schema_rule(
        self, package_table: RuleTable
    ) -> None:
        #: Given
        guide = b'---\nname: guide\ndescription: [a]\nextra: y\nstatus: Final\n---\n# Guide\n'
        database = Database(_snapshot(GUIDE_SCHEMA, guide=guide))

        #: When
        reports = check_subjects(database, (GUIDE,), package_table)

        #: Then
        line_1 = LineNumber.from_int(1)
        missing_field = MissingField(
            spec=CODE_SPEC, line=line_1, problem=MissingFieldProblem('owner', "'owner' is a required property")
        )
        unknown_field = UnknownField(
            spec=CODE_SPEC,
            line=LineNumber.from_int(4),
            problem=UnknownFieldProblem('extra', "Additional properties are not allowed ('extra' was unexpected)"),
        )
        wrong_type = WrongType(
            spec=CODE_SPEC,
            line=LineNumber.from_int(3),
            problem=WrongTypeProblem('description', "['a'] is not of type 'string'"),
        )
        invalid_value = InvalidValue(
            spec=CODE_SPEC,
            line=LineNumber.from_int(5),
            problem=InvalidValueProblem('status', "'Final' does not match '^(draft|stable)$'"),
        )
        block_constraint = BlockConstraint(
            spec=CODE_SPEC,
            line=line_1,
            problem=BlockProblem(
                "{'name': 'guide', 'description': ['a'], 'extra': 'y', 'status': 'Final'} "
                'does not have enough properties'
            ),
        )
        assert reports == (
            CheckedSubject(
                GUIDE,
                diagnostics=(
                    RuleDiagnostic(GUIDE.path, missing_field, Severity.ERROR),
                    RuleDiagnostic(GUIDE.path, unknown_field, Severity.WARNING),
                    RuleDiagnostic(GUIDE.path, wrong_type, Severity.ERROR),
                    RuleDiagnostic(GUIDE.path, invalid_value, Severity.ERROR),
                    RuleDiagnostic(GUIDE.path, block_constraint, Severity.ERROR),
                ),
                ungoverned=(InputKind.TOKEN_COUNT,),
            ),
        ), (
            'FM006 and FM008 to FM010 run at deny and FM007 at warn, each on its own problem, on its field line or '
            'line 1, naming the specification'
        )

    def test_check_subjects_with_a_skill_breaking_the_agent_skills_schema_reports_each_schema_rule(
        self, package_table: RuleTable
    ) -> None:
        #: Given
        # no description, an empty compatibility, a metadata that is not a mapping, and a key it does not define
        review = b'---\nname: review\ncompatibility: ""\nmetadata: z\nextra: y\n---\n# Review\n'
        database = Database(_snapshot(_budget(1000), guide=GUIDE_TEXT.encode(), review=review))

        #: When
        reports = check_subjects(database, (_location(database, REVIEW),), package_table)

        #: Then
        line_1 = LineNumber.from_int(1)
        missing_field = MissingField(
            spec=None, line=line_1, problem=MissingFieldProblem('description', '`description` is required')
        )
        unknown_field = UnknownField(
            spec=None,
            line=LineNumber.from_int(5),
            problem=UnknownFieldProblem('extra', '`extra` is not a field of the Agent Skills specification'),
        )
        wrong_type = WrongType(
            spec=None,
            line=LineNumber.from_int(4),
            problem=WrongTypeProblem('metadata', '`metadata` must be a mapping of strings to strings'),
        )
        invalid_value = InvalidValue(
            spec=None,
            line=LineNumber.from_int(3),
            problem=InvalidValueProblem(
                'compatibility', 'skill compatibility cannot be empty; leave the field out instead'
            ),
        )
        assert reports == (
            CheckedSubject(
                REVIEW,
                diagnostics=(
                    RuleDiagnostic(REVIEW_FILE, missing_field, Severity.ERROR),
                    RuleDiagnostic(REVIEW_FILE, unknown_field, Severity.WARNING),
                    RuleDiagnostic(REVIEW_FILE, wrong_type, Severity.ERROR),
                    RuleDiagnostic(REVIEW_FILE, invalid_value, Severity.ERROR),
                ),
                ungoverned=(),
            ),
        ), 'the schema rules judge a skill against the Agent Skills specification, naming no specification file'

    def test_check_subjects_with_a_document_two_schemas_govern_notes_each_problem_with_its_own_specification(
        self, package_table: RuleTable
    ) -> None:
        #: Given
        namespace_spec = RootRelativePath.parse('docs/__meta__/code-python.structure.json')
        snapshot = Snapshot.from_tree(
            {
                'docs': {
                    '__meta__': {
                        'code.md': b'# Code\n',
                        'code.structure.json': b'{"frontmatter": {"type": "object", "required": ["status"]}}',
                        'code-python.md': b'# Code Python\n',
                        'code-python.structure.json': b'{"frontmatter": {"type": "object", "required": ["owner"]}}',
                    },
                    'code': {'python-typing.md': b'---\nname: python-typing\n---\n# Typing\n'},
                }
            }
        )
        database = Database(snapshot)
        typing = DocumentRef(CorpusName.parse('code'), AspectFilename.parse('python-typing'))

        #: When
        reports = check_subjects(database, (typing,), package_table)

        #: Then
        line_1 = LineNumber.from_int(1)
        status = MissingField(
            spec=CODE_SPEC, line=line_1, problem=MissingFieldProblem('status', "'status' is a required property")
        )
        owner = MissingField(
            spec=namespace_spec, line=line_1, problem=MissingFieldProblem('owner', "'owner' is a required property")
        )
        assert reports == (
            CheckedSubject(
                typing,
                diagnostics=(
                    RuleDiagnostic(typing.path, status, Severity.ERROR),
                    RuleDiagnostic(typing.path, owner, Severity.ERROR),
                ),
                ungoverned=(InputKind.TOKEN_COUNT,),
            ),
        ), 'each schema is applied on its own, and each problem names the specification whose schema found it'

    def test_check_subjects_with_no_frontmatter_schema_reports_the_schema_problems_as_ungoverned(
        self, package_table: RuleTable
    ) -> None:
        #: Given
        database = Database(_snapshot(_budget(1000), guide=b'---\nname: [1]\n---\n# Guide\n'))

        #: When
        reports = check_subjects(database, (GUIDE,), package_table)

        #: Then
        assert reports == (
            CheckedSubject(GUIDE, diagnostics=(), ungoverned=(InputKind.FRONTMATTER_BLOCK, InputKind.SCHEMA_PROBLEMS)),
        ), 'no specification states a frontmatter schema, which is coverage, not a diagnostic'

    def test_check_subjects_with_a_block_that_is_not_a_mapping_reports_no_schema_rule(
        self, package_table: RuleTable
    ) -> None:
        #: Given
        database = Database(_snapshot(GUIDE_SCHEMA, guide=b'---\n- status\n---\n# Guide\n'))

        #: When
        reports = check_subjects(database, (GUIDE,), package_table)

        #: Then
        occurrence = NonMappingFrontmatter(spec=CODE_SPEC, line=LineNumber.from_int(1))
        assert reports == (
            CheckedSubject(
                GUIDE,
                diagnostics=(RuleDiagnostic(GUIDE.path, occurrence, Severity.ERROR),),
                ungoverned=(InputKind.TOKEN_COUNT,),
            ),
        ), 'FM003 alone reports a block that is not a mapping: it is held to no schema, so no schema rule fires'

    def test_check_subjects_with_only_the_block_rules_enabled_never_holds_the_frontmatter_to_a_schema(self) -> None:
        #: Given
        # both subjects break their schema, but only the frontmatter block rules are enabled
        database = CountingDatabase(
            _snapshot(GUIDE_SCHEMA, guide=b'---\nname: guide\n---\n', review=b'---\nname: review\n---\n')
        )
        severities: dict[type[Rule], Severity] = {
            MissingFrontmatter: Severity.ERROR,
            InvalidYaml: Severity.ERROR,
            NonMappingFrontmatter: Severity.ERROR,
            NameMismatch: Severity.ERROR,
            DuplicateKey: Severity.ERROR,
        }
        table = RuleTable(severities)

        #: When
        check_subjects(database, (GUIDE, _location(database, REVIEW)), table)

        #: Then
        assert database.parsed_frontmatters == [GUIDE, REVIEW], (
            'the frontmatter is asked for once per subject, by the block input alone: no schema problems are built'
        )
