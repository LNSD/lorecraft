"""The rules engine's runner over a database opened on a snapshot, built in memory or scanned from a real tree.

The runner decodes each document, skill and resource, hands each rule the facts its query reads from a document, a
skill, the frontmatter or a Markdown file, and runs the rules of a table built from a registry. The package's own
registry runs the frontmatter rules over documents and skills, the token budget, the headings rules and the outline
divergence rules over documents, the line budget over skills, and the link rules over every Markdown file and every
skill's file; a registry of sample rules over a document's token count, declared in this module, runs through the same
runner, with no edit to it.

A snapshot built in memory scans nothing, so no path is in its scope and no link is looked up in it. A test that
needs a path in scope, such as those of `LINK003`, which judges what a link names, writes a tree under `tmp_path`
and opens the database on a scan of it instead.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import ClassVar, Final, Protocol, Self

import pytest

from lib.overruns import overrun
from lib.tree import from_tree
from lorecraft import rules
from lorecraft.core.lines import Line
from lorecraft.core.num import NonZeroUnsignedInt, UnsignedInt
from lorecraft.core.path import PathComponent, RootRelativePath
from lorecraft.engine import check_subjects
from lorecraft.jsonschema import JsonType
from lorecraft.project.aspect import AspectFilename
from lorecraft.project.database import Database
from lorecraft.project.item import ItemRef, ItemType
from lorecraft.project.layout import SNAPSHOT_SCOPE
from lorecraft.project.link_target import DocumentDirectory, SkillRoot
from lorecraft.project.query import (
    CountPrimitives,
    GovernancePrimitives,
    ItemQuery,
    item_frontmatter,
    item_line_count,
    item_parse,
    item_structure_specs,
    item_token_count,
)
from lorecraft.project.schemas import (
    AgentSkillsSchema,
    DocumentEnd,
    DocumentFrontmatterOwner,
    ExpectedSection,
    FieldCount,
    FieldGuidance,
    FieldLimit,
    InvalidValueProblem,
    MissingFieldProblem,
    OtherValueConstraint,
    PatternMismatch,
    SectionName,
    SkillFrontmatterOwner,
    StructureSpecSchema,
    TitlePattern,
    UnknownFieldProblem,
    WrongTypeProblem,
    frontmatter_schema_problems,
)
from lorecraft.project.skill import (
    SkillAliasRef,
    SkillLocation,
    SkillRef,
    SkillRelativePath,
    SkillResourceLocation,
    SkillResourceRef,
)
from lorecraft.project.syntax import (
    Heading,
    InvalidYamlFrontmatter,
    LineNumber,
    SectionHeading,
    TokenCount,
    count_tokens,
    parse_document,
    parse_frontmatter,
    section_headings,
)
from lorecraft.project.workspace import WorkspaceModel
from lorecraft.project.workspace.builtin import AGENT_SKILLS_SPEC_LAYER as SKILLS_LAYER
from lorecraft.rules.declaration import Rule
from lorecraft.rules.frontmatter.allowed_tools_too_long import AllowedToolsTooLong
from lorecraft.rules.frontmatter.duplicate_key import DuplicateKey
from lorecraft.rules.frontmatter.invalid_value import InvalidValue
from lorecraft.rules.frontmatter.invalid_yaml import InvalidYaml
from lorecraft.rules.frontmatter.malformed_allowed_tools import CommaSeparated, MalformedAllowedTools
from lorecraft.rules.frontmatter.missing_field import MissingField
from lorecraft.rules.frontmatter.missing_frontmatter import MissingFrontmatter
from lorecraft.rules.frontmatter.name_mismatch import NameMismatch
from lorecraft.rules.frontmatter.non_mapping_frontmatter import NonMappingFrontmatter
from lorecraft.rules.frontmatter.too_few_fields import TooFewFields
from lorecraft.rules.frontmatter.unknown_field import UnknownField
from lorecraft.rules.frontmatter.wrong_type import WrongType
from lorecraft.rules.identity import Level, Release, RuleCode, RuleGroup, RuleGroupPrefix, RuleName, Severity
from lorecraft.rules.length.section_too_many_words import NamedSectionCap, SectionTooManyWords
from lorecraft.rules.length.title_too_long import TitleTooLong
from lorecraft.rules.length.title_too_many_words import TitleTooManyWords
from lorecraft.rules.length.too_many_lines import TooManyLines
from lorecraft.rules.length.too_many_tokens import TooManyTokens
from lorecraft.rules.link.absolute_link import AbsoluteLink
from lorecraft.rules.link.broken_fragment import BrokenFragment
from lorecraft.rules.link.broken_link import BrokenLink
from lorecraft.rules.link.escaping_link import EscapingLink
from lorecraft.rules.outline.empty_section import EmptySection, OtherSection
from lorecraft.rules.outline.extra_title import ExtraTitle
from lorecraft.rules.outline.forbidden_section import ForbiddenSection
from lorecraft.rules.outline.invalid_title import InvalidTitle
from lorecraft.rules.outline.missing_section import MissingSection
from lorecraft.rules.outline.missing_title import MissingTitle
from lorecraft.rules.outline.section_out_of_order import SectionOutOfOrder
from lorecraft.rules.outline.title_not_first import TitleNotFirst
from lorecraft.rules.outline.unexpected_section import UnexpectedSection
from lorecraft.rules.registry import Registry
from lorecraft.rules.report import (
    CheckedItem,
    RuleDiagnostic,
    SubjectReport,
    UndecodableSubject,
)
from lorecraft.rules.selection import AllRules, RuleSelection
from lorecraft.rules.subject import Gate, QueriedItemRule, SpecPart, WhenSpec
from lorecraft.rules.table import RuleTable
from lorecraft.vfs import (
    ByteOffset,
    EntryRecord,
    ResolvedPath,
    Snapshot,
    SnapshotRecords,
    SymlinkRecord,
    Utf8Failure,
    Utf8Reason,
    VirtualFileSystem,
    take_snapshot,
)
from lorecraft.vfs.view import AbsoluteSymlinkTarget, RelativeSymlinkTarget, SymlinkTarget

GUIDE: Final[ItemRef] = ItemRef(RootRelativePath.parse('docs/code/guide.md'))
"""A document of corpus `code`."""

INTRO: Final[ItemRef] = ItemRef(RootRelativePath.parse('docs/code/intro.md'))
"""A second document of corpus `code`."""

REVIEW: Final[SkillRef] = SkillRef(
    ResolvedPath(RootRelativePath.parse('.agents/skills')), PathComponent.parse('review')
)
"""A skill an agent reaches under `.agents/skills`."""

GUIDE_TEXT: Final[str] = '# Guide\n\nInstall the toolkit, then run it once over the repository.\n'
"""The text of `GUIDE`."""

CODE_SPEC: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/code.spec.json')
"""The corpus structure specification."""

GUIDE_OWNER: Final[DocumentFrontmatterOwner] = DocumentFrontmatterOwner(
    filename=AspectFilename.parse('guide'), spec=CODE_SPEC
)
"""The frontmatter owner of `GUIDE`, which the corpus structure specification governs."""

REVIEW_OWNER: Final[SkillFrontmatterOwner] = SkillFrontmatterOwner(
    directory_name=PathComponent.parse('review'), link_target=None
)
"""The frontmatter owner of `REVIEW`, listed under its own name and not a link."""

_CAFE_TITLE_FAILURE: Final[Utf8Failure] = Utf8Failure(
    line=Line(NonZeroUnsignedInt(1)),
    offset=ByteOffset(UnsignedInt(5)),
    invalid=b'\xe9',
    reason=Utf8Reason.INVALID_CONTINUATION_BYTE,
)
"""Where `# Caf\xe9\n` stops being UTF-8: the Latin-1 `é`, on the first line, followed by a line feed."""

_CAFE_NAME_FAILURE: Final[Utf8Failure] = Utf8Failure(
    line=Line(NonZeroUnsignedInt(2)),
    offset=ByteOffset(UnsignedInt(13)),
    invalid=b'\xe9',
    reason=Utf8Reason.INVALID_CONTINUATION_BYTE,
)
"""Where `---\nname: caf\xe9\n---\n` stops being UTF-8: the Latin-1 `é` in the frontmatter's second line."""

REVIEW_FILE: Final[RootRelativePath] = RootRelativePath.parse('.agents/skills/review/SKILL.md')
"""Where `REVIEW` is reported: its `SKILL.md`, under the skills directory an agent lists it in."""

SKILL_UNGOVERNED: Final[tuple[SpecPart, ...]] = (
    SpecPart.STRUCTURE,
    SpecPart.OUTLINE,
)
"""The skills corpus is absent; the builtin floor still governs frontmatter and line budgets."""

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

DESCRIPTION_GUIDANCE: Final[FieldGuidance] = FieldGuidance(
    description='What the skill does and when to use it, with the keywords that let an agent match it to a task.',
    example=(
        'Extracts text and tables from PDF files, fills PDF forms, and merges multiple PDFs. Use when working'
        ' with PDF documents or when the user mentions PDFs, forms, or document extraction.'
    ),
)
"""What the Agent Skills specification states about a skill's `description`."""

COMPATIBILITY_GUIDANCE: Final[FieldGuidance] = FieldGuidance(
    description=(
        'The environment the skill needs: the product it is meant for, the system packages it runs, or network '
        'access. Most skills need none, and leave it out.'
    ),
    example='Designed for Claude Code (or similar products)',
)
"""What the Agent Skills specification states about a skill's `compatibility`."""

METADATA_GUIDANCE: Final[FieldGuidance] = FieldGuidance(
    description=(
        'Properties the specification does not define, for clients to read: string keys to string values, so a '
        "number is quoted. Keys are best made unique enough not to collide with another client's."
    ),
    example='{"author": "example-org", "version": "1.0"}',
)
"""What the Agent Skills specification states about a skill's `metadata`."""

SAMPLE: Final[RuleGroup] = RuleGroup(RuleGroupPrefix('SMP'), 'Sample rules')
"""The group of the sample rules this module declares."""


def _target(raw: str | PurePosixPath | Path) -> SymlinkTarget:
    """Wrap a target written as it would be by `os.readlink`."""
    target = PurePosixPath(raw)
    if target.is_absolute():
        return AbsoluteSymlinkTarget(target)
    return RelativeSymlinkTarget(target)


@dataclass(frozen=True, slots=True)
class BudgetFacts:
    """What `OverHalfBudget` reads of a document.

    Attributes:
        count: The tokens in the document's whole file.
        budgets: The structure file and the budget each governing specification sets, where it sets one.
    """

    count: TokenCount
    budgets: tuple[tuple[RootRelativePath, int], ...]


class _GovernanceCountPrimitives(GovernancePrimitives, CountPrimitives, Protocol):
    """The primitives the sample queries read."""


def _budget_facts(primitives: _GovernanceCountPrimitives) -> BudgetFacts:
    """The document's token count and the budgets that govern it.

    Args:
        primitives: The model state of the document.
    """
    budgets = tuple(
        (spec.path, spec.tokens.value) for spec in primitives.query(item_structure_specs) if spec.tokens is not None
    )
    return BudgetFacts(count=primitives.query(item_token_count), budgets=budgets)


def _token_count(primitives: CountPrimitives) -> TokenCount:
    """The tokens in the document's whole file.

    Args:
        primitives: The model state of the document.
    """
    return primitives.query(item_token_count)


@dataclass(frozen=True, slots=True, kw_only=True)
class OverHalfBudget(QueriedItemRule[BudgetFacts]):
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
    APPLIES_TO: ClassVar[Mapping[ItemType, Gate]] = MappingProxyType({ItemType.DOCUMENT: WhenSpec(SpecPart.BUDGET)})

    spec: RootRelativePath
    token_count: int
    budget: int

    def message(self) -> str:
        """Name the tokens found against the budget."""
        return f'over half the budget ({self.token_count} of {self.budget})'

    @classmethod
    def query(cls) -> ItemQuery[BudgetFacts]:
        """The document's token count and the budgets that govern it."""
        return _budget_facts

    @classmethod
    def judge(cls, facts: BudgetFacts, /) -> tuple[Self, ...]:
        """One occurrence for each budget the document holds more than half of.

        Args:
            facts: The document's token count and its budgets.
        """
        token_count = facts.count.value
        return tuple(
            cls(spec=spec, line=LineNumber(NonZeroUnsignedInt(1)), token_count=token_count, budget=budget)
            for spec, budget in facts.budgets
            if token_count * 2 > budget
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class EmptyDocument(QueriedItemRule[TokenCount]):
    """A sample rule at `allow`: a document holds no token at all."""

    CODE: ClassVar[RuleCode] = RuleCode(SAMPLE, 2)
    NAME: ClassVar[RuleName] = RuleName('empty-document')
    LEVEL: ClassVar[Level] = Level.ALLOW
    SINCE: ClassVar[Release] = Release('1.0.0')
    APPLIES_TO: ClassVar[Mapping[ItemType, Gate]] = MappingProxyType({ItemType.DOCUMENT: WhenSpec(SpecPart.BUDGET)})

    def message(self) -> str:
        """Name the condition."""
        return 'document is empty'

    @classmethod
    def query(cls) -> ItemQuery[TokenCount]:
        """The tokens in the document's whole file."""
        return _token_count

    @classmethod
    def judge(cls, facts: TokenCount, /) -> tuple[Self, ...]:
        """The occurrence at line 1, when the document has no token.

        Args:
            facts: The tokens in the document's whole file.
        """
        if facts.value > 0:
            return ()
        return (cls(spec=None, line=LineNumber(NonZeroUnsignedInt(1))),)


@dataclass(frozen=True, slots=True, kw_only=True)
class AnyTokens(QueriedItemRule[TokenCount]):
    """A sample rule at `deny` that fires once on every document a budget governs, whatever its token count.

    Attributes:
        token_count: The tokens in the document's whole file.
    """

    CODE: ClassVar[RuleCode] = RuleCode(SAMPLE, 3)
    NAME: ClassVar[RuleName] = RuleName('any-tokens')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('1.0.0')
    APPLIES_TO: ClassVar[Mapping[ItemType, Gate]] = MappingProxyType({ItemType.DOCUMENT: WhenSpec(SpecPart.BUDGET)})

    token_count: int

    def message(self) -> str:
        """Name the tokens counted."""
        return f'document counted ({self.token_count} tokens)'

    @classmethod
    def query(cls) -> ItemQuery[TokenCount]:
        """The tokens in the document's whole file."""
        return _token_count

    @classmethod
    def judge(cls, facts: TokenCount, /) -> tuple[Self, ...]:
        """One occurrence at line 1, whatever the count.

        Args:
            facts: The tokens in the document's whole file.
        """
        return (cls(spec=None, line=LineNumber(NonZeroUnsignedInt(1)), token_count=facts.value),)


class CountingDatabase(Database):
    """A database that records each item whose counts, frontmatter, schema problems or parse it is asked for.

    Attributes:
        counted_tokens: The items whose tokens were counted, in the order asked, a repeat listed again.
        counted_lines: The items whose lines were counted, in the order asked.
        parsed_frontmatters: The items whose frontmatter was parsed, in the order asked.
        parsed_documents: The items whose Markdown was parsed, in the order asked.
    """

    def __init__(self, fs: VirtualFileSystem, model: WorkspaceModel) -> None:
        """Build the database on the view, with nothing counted yet.

        Args:
            fs: The view of the revision the database reads.
            model: The workspace model loaded through the view.
        """
        super().__init__(fs, model)
        self.counted_tokens: list[ItemRef] = []
        self.counted_lines: list[ItemRef] = []
        self.parsed_frontmatters: list[ItemRef] = []
        self.parsed_documents: list[ItemRef] = []

    def query[T](self, query: ItemQuery[T], ref: ItemRef) -> T:
        """Record each declared per-item fact query before evaluating it."""
        if query is item_token_count:
            self.counted_tokens.append(ref)
        elif query is item_line_count:
            self.counted_lines.append(ref)
        elif query is item_frontmatter:
            self.parsed_frontmatters.append(ref)
        elif query is item_parse:
            self.parsed_documents.append(ref)
        return super().query(query, ref)


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
    return from_tree(
        {
            '.agents': {'skills': {'review': {'SKILL.md': review}}},
            'docs': {
                '__meta__': {'code.md': b'# Code\n', 'code.spec.json': structure_spec},
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


def _item(database: Database, location: SkillLocation | SkillResourceLocation) -> ItemRef:
    """The common reference for a skill or resource listed by the database.

    Args:
        database: The revision listing the item.
        location: The model or resource listing's origin-specific location.
    """
    return ItemRef(location.ref.path)


def _resources(database: Database, ref: SkillRef) -> tuple[SkillResourceLocation, ...]:
    """The resources of a skill the test wrote, each located as the database's listing of the skill gives it.

    Args:
        database: The database whose model lists the skill, and which lists its resources.
        ref: A skill the snapshot holds in an agent's skills directory.
    """
    return database.skill_resources(_location(database, ref)).resources


def _invalid_yaml_problem(text: str) -> str:
    """What the YAML parser finds wrong with the frontmatter of a text whose block is not YAML.

    Args:
        text: A whole document or `SKILL.md`, whose block the test wrote as invalid YAML.
    """
    frontmatter = parse_frontmatter(text)
    assert isinstance(frontmatter, InvalidYamlFrontmatter), 'the test wrote a block that is not YAML'
    return frontmatter.problem


def _heading(text: bytes, heading_text: str) -> Heading:
    """The first top-level heading with this text, as the real parser reads it from a document's text.

    Args:
        text: The document's UTF-8 text.
        heading_text: The heading's plain text.

    Raises:
        AssertionError: If the document holds no such heading.
    """
    for heading in parse_document(text.decode()).headings:
        if heading.text == heading_text:
            return heading
    raise AssertionError(f'the document holds a heading `{heading_text}`')


def _section(text: bytes, heading_text: str) -> SectionHeading:
    """The first H2 section with this heading text, as the real parser reads it from a document's text.

    Args:
        text: The document's UTF-8 text.
        heading_text: The heading's plain text.

    Raises:
        AssertionError: If the document holds no such section.
    """
    for section in section_headings(parse_document(text.decode()).headings):
        if section.text == heading_text:
            return section
    raise AssertionError(f'the document holds a section `{heading_text}`')


def _budget(tokens: int) -> bytes:
    """A structure specification that sets a token budget and nothing else.

    Args:
        tokens: The most tokens the specification lets a document it governs hold; at least 1.
    """
    return f'{{"tokens": {tokens}}}'.encode()


@pytest.fixture(scope='module')
def package_table() -> RuleTable:
    """The rule table of the package's own rules at their default levels; immutable, so shared by the module."""
    return RuleTable.from_registry(
        Registry.load(rules), RuleSelection(select=frozenset({AllRules()}), ignore=frozenset())
    )


@pytest.fixture(scope='module')
def sample_table() -> RuleTable:
    """The rule table of the sample rules this module declares, one at each level; immutable, so shared by the module.

    The registry holds the sample rules as it would hold any rule, so they reach the runner through the table alone.
    """
    return RuleTable.from_registry(
        Registry((OverHalfBudget, EmptyDocument, AnyTokens)),
        RuleSelection(select=frozenset({AllRules()}), ignore=frozenset()),
    )


def _refs(reports: tuple[SubjectReport, ...]) -> list[ItemRef | SkillAliasRef]:
    """The document, skill or resource each report is about, every report's, in the order the reports are given.

    Args:
        reports: Reports `check_subjects` returned.
    """
    return [report.ref for report in reports]


@pytest.mark.it
class TestCheckSubjects:
    @pytest.mark.parametrize(
        ('floor_enabled', 'skills_spec', 'expected_codes', 'expected_ungoverned'),
        (
            (True, None, ('LC211', 'LC212', 'LEN002'), ()),
            (
                True,
                b'{"lines":300,"frontmatter":{"type":"object"}}',
                ('LC211', 'LC212', 'LEN002', 'LEN002'),
                (),
            ),
            (
                False,
                b'{"lines":400,"frontmatter":{"type":"object"}}',
                ('LC211', 'LC212', 'LEN002'),
                (),
            ),
            (
                False,
                None,
                (),
                (SpecPart.FRONTMATTER, SpecPart.BUDGET),
            ),
        ),
        ids=('floor', 'floor-and-repository', 'repository-only', 'no-governance'),
    )
    def test_skill_floor_and_repository_layers_gate_budget_and_tool_rules(
        self,
        floor_enabled: bool,
        skills_spec: bytes | None,
        expected_codes: tuple[str, ...],
        expected_ungoverned: tuple[SpecPart, ...],
    ) -> None:
        #: Given
        skill = (
            b'---\nname: review\ndescription: Review a change.\nallowed-tools: '
            + b'A' * 500
            + b',\n---\n'
            + b'Run the next step.\n' * 496
        )
        meta = {'skills.md': b'# Skills\n'}
        if skills_spec is not None:
            meta['skills.spec.json'] = skills_spec
        snapshot = from_tree({'docs': {'__meta__': meta}, '.agents': {'skills': {'review': {'SKILL.md': skill}}}})
        builtin_layers = (SKILLS_LAYER,) if floor_enabled else ()
        database = Database.from_snapshot(snapshot, builtin_layers=builtin_layers)
        table = RuleTable(
            {
                AllowedToolsTooLong: Severity.WARNING,
                MalformedAllowedTools: Severity.WARNING,
                TooManyLines: Severity.ERROR,
            }
        )

        #: When
        reports = check_subjects(database, (_item(database, _location(database, REVIEW)),), table, {})

        #: Then
        assert len(reports) == 1, 'the skill receives one checked report'
        report = reports[0]
        assert isinstance(report, CheckedItem), 'the skill receives a checked report'
        assert tuple(str(diagnostic.occurrence.CODE) for diagnostic in report.diagnostics) == expected_codes, (
            'each rule runs only when a builtin or repository layer states its part'
        )
        assert report.ungoverned == expected_ungoverned, (
            'the absent layer parts appear as coverage when no structure governance exists'
        )
        if floor_enabled and skills_spec is not None:
            line_diagnostics = tuple(
                diagnostic for diagnostic in report.diagnostics if isinstance(diagnostic.occurrence, TooManyLines)
            )
            assert {diagnostic.occurrence.overrun.cap for diagnostic in line_diagnostics} == {
                NonZeroUnsignedInt(500),
                NonZeroUnsignedInt(300),
            }, 'the builtin 500-line cap and tighter repository cap each report their own budget'
            assert {diagnostic.occurrence.message() for diagnostic in line_diagnostics} == {
                'too many lines (501 > 500)',
                'too many lines (501 > 300)',
            }, 'each line diagnostic names the limit that fired'

    def test_check_subjects_with_overlong_malformed_allowed_tools_reports_both_warnings(
        self, tmp_path: Path, package_table: RuleTable
    ) -> None:
        #: Given
        value = 'A' * 500 + ','
        _write(
            tmp_path,
            '.agents/skills/review/SKILL.md',
            f'---\nname: review\ndescription: Review a change.\nallowed-tools: {value}\n---\n'.encode(),
        )
        database = Database.from_snapshot(take_snapshot(tmp_path, SNAPSHOT_SCOPE), builtin_layers=(SKILLS_LAYER,))
        subjects = (_item(database, _location(database, REVIEW)),)

        #: When
        reports = check_subjects(database, subjects, package_table, {})

        #: Then
        skill_file = RootRelativePath.parse('.agents/skills/review/SKILL.md')
        assert reports == (
            CheckedItem(
                ItemRef(REVIEW.path),
                diagnostics=(
                    RuleDiagnostic(
                        skill_file,
                        MalformedAllowedTools(
                            line=LineNumber(NonZeroUnsignedInt(4)),
                            problem=CommaSeparated(entry=value, suggested='A' * 500),
                        ),
                        Severity.WARNING,
                    ),
                    RuleDiagnostic(
                        skill_file,
                        AllowedToolsTooLong(line=LineNumber(NonZeroUnsignedInt(4)), overrun=overrun(501, 500)),
                        Severity.WARNING,
                    ),
                ),
                ungoverned=SKILL_UNGOVERNED,
            ),
        ), 'an overlong value still receives structural validation, and both warnings point at its field'

    def test_check_subjects_with_malformed_allowed_tools_reports_a_warning_at_the_skill_path(
        self, tmp_path: Path, package_table: RuleTable
    ) -> None:
        #: Given
        _write(
            tmp_path,
            '.agents/skills/review/SKILL.md',
            b'---\nname: review\ndescription: Review a change.\nallowed-tools: Read, Grep\n---\n',
        )
        database = Database.from_snapshot(take_snapshot(tmp_path, SNAPSHOT_SCOPE), builtin_layers=(SKILLS_LAYER,))
        subjects = (_item(database, _location(database, REVIEW)),)

        #: When
        reports = check_subjects(database, subjects, package_table, {})

        #: Then
        occurrence = MalformedAllowedTools(
            line=LineNumber(NonZeroUnsignedInt(4)), problem=CommaSeparated(entry='Read,', suggested='Read')
        )
        skill_file = RootRelativePath.parse('.agents/skills/review/SKILL.md')
        assert reports == (
            CheckedItem(
                ItemRef(REVIEW.path),
                diagnostics=(RuleDiagnostic(skill_file, occurrence, Severity.WARNING),),
                ungoverned=SKILL_UNGOVERNED,
            ),
        ), 'the registry runs LC211 over a skill and reports the warning at its listed path and field line'

    def test_check_subjects_with_a_document_over_its_budget_reports_the_token_budget_as_an_error(
        self, package_table: RuleTable
    ) -> None:
        #: Given
        database = Database.from_snapshot(
            _snapshot(_budget(5), guide=GUIDE_TEXT.encode()), builtin_layers=(SKILLS_LAYER,)
        )

        #: When
        reports = check_subjects(database, (GUIDE,), package_table, {})

        #: Then
        occurrence = TooManyTokens(
            spec=CODE_SPEC, line=LineNumber(NonZeroUnsignedInt(1)), overrun=overrun(count_tokens(GUIDE_TEXT).value, 5)
        )
        assert reports == (
            CheckedItem(
                ItemRef(GUIDE.path),
                diagnostics=(RuleDiagnostic(GUIDE.path, occurrence, Severity.ERROR),),
                ungoverned=(SpecPart.FRONTMATTER, SpecPart.OUTLINE),
            ),
        ), 'LEN001 runs at deny, so a document over its budget carries its occurrence as an error'

    def test_check_subjects_with_a_document_over_a_corpus_and_a_namespace_budget_reports_both(self) -> None:
        #: Given
        namespace_spec = RootRelativePath.parse('docs/__meta__/code-python.spec.json')
        typing_text = '# Typing\n\nAnnotate every signature, and keep the checker clean before a change is done.\n'
        snapshot = from_tree(
            {
                'docs': {
                    '__meta__': {
                        'code.md': b'# Code\n',
                        'code.spec.json': _budget(5),
                        'code-python.md': b'# Code Python\n',
                        'code-python.spec.json': _budget(3),
                    },
                    'code': {'python-typing.md': typing_text.encode()},
                }
            }
        )
        typing = ItemRef(RootRelativePath.parse('docs/code/python-typing.md'))
        severities: dict[type[Rule], Severity] = {TooManyTokens: Severity.ERROR}
        table = RuleTable(severities)
        database = Database.from_snapshot(snapshot, builtin_layers=(SKILLS_LAYER,))

        #: When
        reports = check_subjects(database, (typing,), table, {})

        #: Then
        token_count = count_tokens(typing_text).value
        corpus_budget = TooManyTokens(
            spec=CODE_SPEC, line=LineNumber(NonZeroUnsignedInt(1)), overrun=overrun(token_count, 5)
        )
        namespace_budget = TooManyTokens(
            spec=namespace_spec, line=LineNumber(NonZeroUnsignedInt(1)), overrun=overrun(token_count, 3)
        )
        assert reports == (
            CheckedItem(
                ItemRef(typing.path),
                diagnostics=(
                    RuleDiagnostic(typing.path, corpus_budget, Severity.ERROR),
                    RuleDiagnostic(typing.path, namespace_budget, Severity.ERROR),
                ),
                ungoverned=(),
            ),
        ), 'a namespace budget does not replace the corpus one, so the document is held to both, each naming its own'

    def test_check_subjects_with_a_document_within_its_budget_reports_it_clean(self, package_table: RuleTable) -> None:
        #: Given
        database = Database.from_snapshot(
            _snapshot(_budget(1000), guide=GUIDE_TEXT.encode()), builtin_layers=(SKILLS_LAYER,)
        )

        #: When
        reports = check_subjects(database, (GUIDE,), package_table, {})

        #: Then
        assert reports == (
            CheckedItem(
                ItemRef(GUIDE.path),
                diagnostics=(),
                ungoverned=(SpecPart.FRONTMATTER, SpecPart.OUTLINE),
            ),
        ), 'a document within its budget has no diagnostic, and no frontmatter schema governs it'

    def test_check_subjects_with_no_budget_set_reports_the_budget_as_ungoverned(self, package_table: RuleTable) -> None:
        #: Given
        database = Database.from_snapshot(
            _snapshot(b'{"empty_sections": "forbidden"}', guide=GUIDE_TEXT.encode()),
            builtin_layers=(SKILLS_LAYER,),
        )

        #: When
        reports = check_subjects(database, (GUIDE,), package_table, {})

        #: Then
        assert reports == (
            CheckedItem(
                ItemRef(GUIDE.path),
                diagnostics=(),
                ungoverned=(
                    SpecPart.FRONTMATTER,
                    SpecPart.OUTLINE,
                    SpecPart.BUDGET,
                ),
            ),
        ), 'no specification sets a budget or a frontmatter schema, which is coverage, not a diagnostic'

    def test_check_subjects_with_a_document_in_no_corpus_reports_the_budget_as_ungoverned(
        self, package_table: RuleTable
    ) -> None:
        #: Given
        # the code corpus sets a budget, but `docs/blog/` has no corpus spec, so the model holds no `blog` corpus
        snapshot = from_tree(
            {
                'docs': {
                    '__meta__': {'code.md': b'# Code\n', 'code.spec.json': _budget(5)},
                    'blog': {'launch.md': GUIDE_TEXT.encode()},
                }
            }
        )
        database = Database.from_snapshot(snapshot, builtin_layers=(SKILLS_LAYER,))
        launch = ItemRef(RootRelativePath.parse('docs/blog/launch.md'))

        #: When
        reports = check_subjects(database, (launch,), package_table, {})

        #: Then
        assert reports == (
            CheckedItem(
                ItemRef(launch.path),
                diagnostics=(),
                ungoverned=(
                    SpecPart.FRONTMATTER,
                    SpecPart.STRUCTURE,
                    SpecPart.OUTLINE,
                    SpecPart.BUDGET,
                ),
            ),
        ), 'no specification governs a document in no corpus the model holds, which is coverage, not a diagnostic'

    def test_check_subjects_with_a_corpus_stating_no_structure_specification_reports_the_budget_as_ungoverned(
        self,
    ) -> None:
        #: Given
        # the code corpus states only its prose specification, so no structure specification governs its documents
        snapshot = from_tree(
            {'docs': {'__meta__': {'code.md': b'# Code\n'}, 'code': {'guide.md': GUIDE_TEXT.encode()}}}
        )
        database = Database.from_snapshot(snapshot, builtin_layers=(SKILLS_LAYER,))
        severities: dict[type[Rule], Severity] = {TooManyTokens: Severity.ERROR}
        table = RuleTable(severities)

        #: When
        reports = check_subjects(database, (GUIDE,), table, {})

        #: Then
        assert reports == (CheckedItem(ItemRef(GUIDE.path), diagnostics=(), ungoverned=(SpecPart.BUDGET,)),), (
            'a document whose corpus states no structure specification is governed for no facet'
        )

    def test_check_subjects_with_a_corpus_stating_no_structure_specification_never_counts_the_tokens(self) -> None:
        #: Given
        # the code corpus states only its prose specification, so no structure specification governs its documents
        snapshot = from_tree(
            {'docs': {'__meta__': {'code.md': b'# Code\n'}, 'code': {'guide.md': GUIDE_TEXT.encode()}}}
        )
        database = CountingDatabase.from_snapshot(snapshot, builtin_layers=(SKILLS_LAYER,))
        severities: dict[type[Rule], Severity] = {TooManyTokens: Severity.ERROR}
        table = RuleTable(severities)

        #: When
        check_subjects(database, (GUIDE,), table, {})

        #: Then
        assert database.counted_tokens == [], 'no query is run for it, so its tokens are never counted'

    def test_check_subjects_with_a_corpus_stating_no_structure_specification_reports_the_structure_as_ungoverned(
        self,
    ) -> None:
        #: Given
        # the code corpus states only its prose specification, so no structure specification governs its documents
        snapshot = from_tree(
            {'docs': {'__meta__': {'code.md': b'# Code\n'}, 'code': {'guide.md': GUIDE_TEXT.encode()}}}
        )
        database = CountingDatabase.from_snapshot(snapshot, builtin_layers=(SKILLS_LAYER,))
        severities: dict[type[Rule], Severity] = {SectionTooManyWords: Severity.ERROR, TitleTooLong: Severity.ERROR}
        table = RuleTable(severities)

        #: When
        reports = check_subjects(database, (GUIDE,), table, {})

        #: Then
        assert reports == (CheckedItem(ItemRef(GUIDE.path), diagnostics=(), ungoverned=(SpecPart.STRUCTURE,)),), (
            'the length rules over sections and the title read the structure facet, recorded once as ungoverned'
        )
        assert database.parsed_documents == [], 'no query is run for it, so it is never parsed'

    def test_check_subjects_with_an_undecodable_document_reports_it_undecodable(self, package_table: RuleTable) -> None:
        #: Given
        database = Database.from_snapshot(
            _snapshot(_budget(1000), guide=b'# Caf\xe9\n'), builtin_layers=(SKILLS_LAYER,)
        )

        #: When
        reports = check_subjects(database, (GUIDE,), package_table, {})

        #: Then
        assert reports == (UndecodableSubject(GUIDE, _CAFE_TITLE_FAILURE),), (
            'a document that is not UTF-8 is judged by no rule, and says where its bytes stop being UTF-8'
        )

    def test_check_subjects_with_an_undecodable_ungoverned_document_reports_it_undecodable(
        self, package_table: RuleTable
    ) -> None:
        #: Given
        database = Database.from_snapshot(
            _snapshot(b'{"empty_sections": "forbidden"}', guide=b'# Caf\xe9\n'),
            builtin_layers=(SKILLS_LAYER,),
        )

        #: When
        reports = check_subjects(database, (GUIDE,), package_table, {})

        #: Then
        assert reports == (UndecodableSubject(GUIDE, _CAFE_TITLE_FAILURE),), (
            'a document is decoded before governance is read, so it is undecodable whatever governs it'
        )

    def test_check_subjects_with_several_documents_reports_them_in_the_order_given(
        self, package_table: RuleTable
    ) -> None:
        #: Given
        database = Database.from_snapshot(
            _snapshot(_budget(1000), guide=GUIDE_TEXT.encode()), builtin_layers=(SKILLS_LAYER,)
        )

        #: When
        reports = check_subjects(database, (INTRO, GUIDE), package_table, {})

        #: Then
        assert _refs(reports) == [ItemRef(INTRO.path), ItemRef(GUIDE.path)], (
            'each document is reported in the order given'
        )

    def test_check_subjects_with_no_enabled_rule_over_the_token_count_never_counts_the_tokens(self) -> None:
        #: Given
        database = CountingDatabase.from_snapshot(
            _snapshot(_budget(5), guide=GUIDE_TEXT.encode()), builtin_layers=(SKILLS_LAYER,)
        )
        severities: dict[type[Rule], Severity] = {}
        table = RuleTable(severities)

        #: When
        check_subjects(database, (GUIDE,), table, {})

        #: Then
        assert database.counted_tokens == [], 'no enabled rule reads the token count, so its query is never asked'

    def test_check_subjects_with_no_budget_set_never_counts_the_tokens(self, package_table: RuleTable) -> None:
        #: Given
        database = CountingDatabase.from_snapshot(
            _snapshot(b'{"empty_sections": "forbidden"}', guide=GUIDE_TEXT.encode()),
            builtin_layers=(SKILLS_LAYER,),
        )

        #: When
        check_subjects(database, (GUIDE,), package_table, {})

        #: Then
        assert database.counted_tokens == [], (
            'governance is read before a rule over the budget runs, so an ungoverned document never pays for the count'
        )

    def test_check_subjects_with_sample_rules_reports_each_at_its_level(self, sample_table: RuleTable) -> None:
        #: Given
        # a budget the document holds more than half of, and less than all of
        token_count_of_guide = count_tokens(GUIDE_TEXT).value
        database = Database.from_snapshot(
            _snapshot(_budget(token_count_of_guide + 1), guide=GUIDE_TEXT.encode()),
            builtin_layers=(SKILLS_LAYER,),
        )

        #: When
        reports = check_subjects(database, (GUIDE,), sample_table, {})

        #: Then
        over_half = OverHalfBudget(
            spec=CODE_SPEC,
            line=LineNumber(NonZeroUnsignedInt(1)),
            token_count=token_count_of_guide,
            budget=token_count_of_guide + 1,
        )
        any_tokens = AnyTokens(spec=None, line=LineNumber(NonZeroUnsignedInt(1)), token_count=token_count_of_guide)
        assert reports == (
            CheckedItem(
                ItemRef(GUIDE.path),
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
        database = Database.from_snapshot(_snapshot(_budget(10), guide=b''), builtin_layers=(SKILLS_LAYER,))

        #: When
        reports = check_subjects(database, (GUIDE,), sample_table, {})

        #: Then
        any_tokens = AnyTokens(spec=None, line=LineNumber(NonZeroUnsignedInt(1)), token_count=0)
        assert reports == (
            CheckedItem(
                ItemRef(GUIDE.path),
                diagnostics=(RuleDiagnostic(GUIDE.path, any_tokens, Severity.ERROR),),
                ungoverned=(),
            ),
        ), 'a rule at allow is not in the table, so only the enabled rules report'

    def test_check_subjects_with_a_skill_over_the_line_budget_reports_the_line_budget_as_an_error(
        self, package_table: RuleTable
    ) -> None:
        #: Given
        database = Database.from_snapshot(
            _snapshot(_budget(1000), guide=GUIDE_TEXT.encode(), review=_skill_of(501)),
            builtin_layers=(SKILLS_LAYER,),
        )
        subjects = (_item(database, _location(database, REVIEW)),)

        #: When
        reports = check_subjects(database, subjects, package_table, {})

        #: Then
        occurrence = TooManyLines(line=LineNumber(NonZeroUnsignedInt(501)), overrun=overrun(501, 500))
        skill_file = RootRelativePath.parse('.agents/skills/review/SKILL.md')
        assert reports == (
            CheckedItem(
                ItemRef(REVIEW.path),
                diagnostics=(RuleDiagnostic(skill_file, occurrence, Severity.ERROR),),
                ungoverned=SKILL_UNGOVERNED,
            ),
        ), 'LEN002 runs at deny, so a skill over the budget carries its occurrence as an error, at its SKILL.md'

    def test_check_subjects_with_a_skill_over_the_corpus_token_budget_reports_the_layered_budget(self) -> None:
        #: Given
        snapshot = from_tree(
            {
                'docs': {
                    '__meta__': {
                        'skills.md': b'# Skills\n',
                        'skills.spec.json': b'{"tokens":1}',
                    }
                },
                '.agents': {'skills': {'review': {'SKILL.md': REVIEW_FRONTMATTER + b'# Review\n'}}},
            }
        )
        database = Database.from_snapshot(snapshot, builtin_layers=(SKILLS_LAYER,))
        table = RuleTable({TooManyTokens: Severity.ERROR})

        #: When
        reports = check_subjects(database, (_item(database, _location(database, REVIEW)),), table, {})

        #: Then
        assert len(reports) == 1, 'the skill has one report'
        assert isinstance(reports[0], CheckedItem), 'the skill is a checked item'
        assert [diagnostic.occurrence.spec for diagnostic in reports[0].diagnostics] == [
            RootRelativePath.parse('docs/__meta__/skills.spec.json')
        ], 'the skill is checked against the reserved corpus budget'

    def test_check_subjects_with_a_skill_breaking_its_corpus_structure_reports_the_governing_spec(self) -> None:
        #: Given
        snapshot = from_tree(
            {
                'docs': {
                    '__meta__': {
                        'skills.md': b'# Skills\n',
                        'skills.spec.json': b'{"forbidden":["Changelog"]}',
                    }
                },
                '.agents': {
                    'skills': {
                        'review': {'SKILL.md': REVIEW_FRONTMATTER + b'# Review\n\n## Changelog\n\nUpdated yesterday.\n'}
                    }
                },
            }
        )
        database = Database.from_snapshot(snapshot, builtin_layers=(SKILLS_LAYER,))
        table = RuleTable({ForbiddenSection: Severity.ERROR})

        #: When
        reports = check_subjects(database, (_item(database, _location(database, REVIEW)),), table, {})

        #: Then
        assert len(reports) == 1, 'the skill has one report'
        assert isinstance(reports[0], CheckedItem), 'the skill is checked'
        assert len(reports[0].diagnostics) == 1, 'the forbidden section is reported once'
        diagnostic = reports[0].diagnostics[0]
        assert diagnostic.path == REVIEW_FILE, 'the occurrence is located at the SKILL.md an agent loads'
        assert diagnostic.occurrence.spec == RootRelativePath.parse('docs/__meta__/skills.spec.json'), (
            'the finding names the corpus specification that governs the skill'
        )

    def test_check_subjects_with_a_linked_skill_over_the_line_budget_reports_it_where_an_agent_reaches_it(
        self, package_table: RuleTable
    ) -> None:
        #: Given
        # What a scan records for `.agents/skills/review -> ../../skills/review`: the link in the skills directory,
        # and the SKILL.md at the resolved path it leads to.
        shipped = from_tree({'.agents': {'skills': {}}, 'skills': {'review': {'SKILL.md': _skill_of(501)}}})
        records: dict[RootRelativePath, EntryRecord] = dict(shipped.records)
        records[RootRelativePath.parse('.agents/skills/review')] = SymlinkRecord(_target('../../skills/review'))
        database = Database.from_snapshot(Snapshot(SnapshotRecords(records)), builtin_layers=(SKILLS_LAYER,))
        subjects = (_item(database, _location(database, REVIEW)),)

        #: When
        reports = check_subjects(database, subjects, package_table, {})

        #: Then
        occurrence = TooManyLines(line=LineNumber(NonZeroUnsignedInt(501)), overrun=overrun(501, 500))
        skill_file = RootRelativePath.parse('.agents/skills/review/SKILL.md')
        assert reports == (
            CheckedItem(
                ItemRef(REVIEW.path),
                diagnostics=(RuleDiagnostic(skill_file, occurrence, Severity.ERROR),),
                ungoverned=SKILL_UNGOVERNED,
            ),
        ), 'the SKILL.md is counted where the link leads, and reported under the skills directory, not under skills/'

    def test_check_subjects_with_a_skill_at_the_line_budget_reports_it_clean(self, package_table: RuleTable) -> None:
        #: Given
        database = Database.from_snapshot(
            _snapshot(_budget(1000), guide=GUIDE_TEXT.encode(), review=_skill_of(500)),
            builtin_layers=(SKILLS_LAYER,),
        )
        subjects = (_item(database, _location(database, REVIEW)),)

        #: When
        reports = check_subjects(database, subjects, package_table, {})

        #: Then
        assert reports == (CheckedItem(ItemRef(REVIEW.path), diagnostics=(), ungoverned=SKILL_UNGOVERNED),), (
            'a SKILL.md of exactly 500 lines is within the budget, and the package governs its line count'
        )

    def test_check_subjects_with_an_undecodable_skill_reports_it_undecodable(self, package_table: RuleTable) -> None:
        #: Given
        database = Database.from_snapshot(
            _snapshot(_budget(1000), guide=GUIDE_TEXT.encode(), review=b'---\nname: caf\xe9\n---\n'),
            builtin_layers=(SKILLS_LAYER,),
        )
        subjects = (_item(database, _location(database, REVIEW)),)

        #: When
        reports = check_subjects(database, subjects, package_table, {})

        #: Then
        assert reports == (UndecodableSubject(ItemRef(REVIEW.path), _CAFE_NAME_FAILURE),), (
            'a skill whose SKILL.md is not UTF-8 is judged by no rule'
        )

    def test_check_subjects_with_documents_and_skills_reports_them_in_the_order_given(
        self, package_table: RuleTable
    ) -> None:
        #: Given
        database = Database.from_snapshot(
            _snapshot(_budget(1000), guide=GUIDE_TEXT.encode()), builtin_layers=(SKILLS_LAYER,)
        )
        subjects = (GUIDE, _item(database, _location(database, REVIEW)), INTRO)

        #: When
        reports = check_subjects(database, subjects, package_table, {})

        #: Then
        assert reports == (
            CheckedItem(
                ItemRef(GUIDE.path),
                diagnostics=(),
                ungoverned=(SpecPart.FRONTMATTER, SpecPart.OUTLINE),
            ),
            CheckedItem(ItemRef(REVIEW.path), diagnostics=(), ungoverned=SKILL_UNGOVERNED),
            CheckedItem(
                ItemRef(INTRO.path),
                diagnostics=(),
                ungoverned=(SpecPart.FRONTMATTER, SpecPart.OUTLINE),
            ),
        ), 'documents and skills share one run, each reported in the order given'

    def test_check_subjects_with_no_enabled_rule_over_the_line_count_never_counts_the_lines(self) -> None:
        #: Given
        # only the token budget is enabled, and the skill is over the line budget
        database = CountingDatabase.from_snapshot(
            _snapshot(_budget(1000), guide=GUIDE_TEXT.encode(), review=_skill_of(501)),
            builtin_layers=(SKILLS_LAYER,),
        )
        severities: dict[type[Rule], Severity] = {TooManyTokens: Severity.ERROR}
        table = RuleTable(severities)
        subjects = (_item(database, _location(database, REVIEW)),)

        #: When
        check_subjects(database, subjects, table, {})

        #: Then
        assert database.counted_lines == [], 'no enabled rule reads the line count, so its query is never asked'

    def test_check_subjects_with_a_document_without_a_block_reports_missing_frontmatter(
        self, package_table: RuleTable
    ) -> None:
        #: Given
        database = Database.from_snapshot(
            _snapshot(OBJECT_SCHEMA, guide=GUIDE_TEXT.encode()), builtin_layers=(SKILLS_LAYER,)
        )

        #: When
        reports = check_subjects(database, (GUIDE,), package_table, {})

        #: Then
        occurrence = MissingFrontmatter(owner=GUIDE_OWNER, line=LineNumber(NonZeroUnsignedInt(1)))
        assert reports == (
            CheckedItem(
                ItemRef(GUIDE.path),
                diagnostics=(RuleDiagnostic(GUIDE.path, occurrence, Severity.ERROR),),
                ungoverned=(SpecPart.OUTLINE, SpecPart.BUDGET),
            ),
        ), 'LC201 runs at deny over a document a frontmatter schema governs, under its corpus specification'

    def test_check_subjects_with_a_document_whose_block_is_not_yaml_reports_invalid_yaml(
        self, package_table: RuleTable
    ) -> None:
        #: Given
        guide = '---\nname: [guide\n---\n# Guide\n'
        database = Database.from_snapshot(
            _snapshot(OBJECT_SCHEMA, guide=guide.encode()), builtin_layers=(SKILLS_LAYER,)
        )

        #: When
        reports = check_subjects(database, (GUIDE,), package_table, {})

        #: Then
        occurrence = InvalidYaml(
            owner=GUIDE_OWNER,
            problem=_invalid_yaml_problem(guide),
            stopped_at=LineNumber(NonZeroUnsignedInt(2)),
        )
        assert reports == (
            CheckedItem(
                ItemRef(GUIDE.path),
                diagnostics=(RuleDiagnostic(GUIDE.path, occurrence, Severity.ERROR),),
                ungoverned=(SpecPart.OUTLINE, SpecPart.BUDGET),
            ),
        ), 'LC202 runs at deny, at the line the YAML parser stopped on'

    def test_check_subjects_with_a_document_whose_block_is_a_list_reports_non_mapping_frontmatter(
        self, package_table: RuleTable
    ) -> None:
        #: Given
        database = Database.from_snapshot(
            _snapshot(OBJECT_SCHEMA, guide=b'---\n- guide\n---\n# Guide\n'), builtin_layers=(SKILLS_LAYER,)
        )

        #: When
        reports = check_subjects(database, (GUIDE,), package_table, {})

        #: Then
        occurrence = NonMappingFrontmatter(owner=GUIDE_OWNER, line=LineNumber(NonZeroUnsignedInt(1)))
        assert reports == (
            CheckedItem(
                ItemRef(GUIDE.path),
                diagnostics=(RuleDiagnostic(GUIDE.path, occurrence, Severity.ERROR),),
                ungoverned=(SpecPart.OUTLINE, SpecPart.BUDGET),
            ),
        ), 'LC203 runs at deny over a block that reads as YAML but is not a mapping'

    def test_check_subjects_with_a_document_named_otherwise_reports_name_mismatch(
        self, package_table: RuleTable
    ) -> None:
        #: Given
        database = Database.from_snapshot(
            _snapshot(OBJECT_SCHEMA, guide=b'---\nname: setup\n---\n# Guide\n'),
            builtin_layers=(SKILLS_LAYER,),
        )

        #: When
        reports = check_subjects(database, (GUIDE,), package_table, {})

        #: Then
        occurrence = NameMismatch(owner=GUIDE_OWNER, line=LineNumber(NonZeroUnsignedInt(2)), name='setup')
        assert reports == (
            CheckedItem(
                ItemRef(GUIDE.path),
                diagnostics=(RuleDiagnostic(GUIDE.path, occurrence, Severity.ERROR),),
                ungoverned=(SpecPart.OUTLINE, SpecPart.BUDGET),
            ),
        ), 'LC204 runs at deny over a document whose `name` is not its filename'

    def test_check_subjects_with_a_document_repeating_a_key_reports_duplicate_key(
        self, package_table: RuleTable
    ) -> None:
        #: Given
        database = Database.from_snapshot(
            _snapshot(OBJECT_SCHEMA, guide=b'---\nname: guide\nname: guide\n---\n# Guide\n'),
            builtin_layers=(SKILLS_LAYER,),
        )

        #: When
        reports = check_subjects(database, (GUIDE,), package_table, {})

        #: Then
        occurrence = DuplicateKey(
            owner=GUIDE_OWNER,
            line=LineNumber(NonZeroUnsignedInt(3)),
            key='name',
            first_line=LineNumber(NonZeroUnsignedInt(2)),
            kept_line=LineNumber(NonZeroUnsignedInt(3)),
        )
        assert reports == (
            CheckedItem(
                ItemRef(GUIDE.path),
                diagnostics=(RuleDiagnostic(GUIDE.path, occurrence, Severity.ERROR),),
                ungoverned=(SpecPart.OUTLINE, SpecPart.BUDGET),
            ),
        ), 'LC205 runs at deny over a key written again, at the later occurrence'

    def test_check_subjects_with_a_skill_without_a_block_reports_missing_frontmatter(
        self, package_table: RuleTable
    ) -> None:
        #: Given
        database = Database.from_snapshot(
            _snapshot(_budget(1000), guide=GUIDE_TEXT.encode(), review=b'# Review\n'),
            builtin_layers=(SKILLS_LAYER,),
        )
        subjects = (_item(database, _location(database, REVIEW)),)

        #: When
        reports = check_subjects(database, subjects, package_table, {})

        #: Then
        occurrence = MissingFrontmatter(owner=REVIEW_OWNER, line=LineNumber(NonZeroUnsignedInt(1)))
        assert reports == (
            CheckedItem(
                ItemRef(REVIEW.path),
                diagnostics=(RuleDiagnostic(REVIEW_FILE, occurrence, Severity.ERROR),),
                ungoverned=SKILL_UNGOVERNED,
            ),
        ), 'every skill is governed for its frontmatter, so LC201 needs no specification in the repository'

    def test_check_subjects_with_a_skill_whose_block_is_not_yaml_reports_invalid_yaml(
        self, package_table: RuleTable
    ) -> None:
        #: Given
        review = '---\nname: [review\n---\n'
        database = Database.from_snapshot(
            _snapshot(_budget(1000), guide=GUIDE_TEXT.encode(), review=review.encode()),
            builtin_layers=(SKILLS_LAYER,),
        )
        subjects = (_item(database, _location(database, REVIEW)),)

        #: When
        reports = check_subjects(database, subjects, package_table, {})

        #: Then
        occurrence = InvalidYaml(
            owner=REVIEW_OWNER,
            problem=_invalid_yaml_problem(review),
            stopped_at=LineNumber(NonZeroUnsignedInt(2)),
        )
        assert reports == (
            CheckedItem(
                ItemRef(REVIEW.path),
                diagnostics=(RuleDiagnostic(REVIEW_FILE, occurrence, Severity.ERROR),),
                ungoverned=SKILL_UNGOVERNED,
            ),
        ), 'LC202 runs at deny over a skill, at the line the YAML parser stopped on'

    def test_check_subjects_with_a_skill_whose_block_is_a_list_reports_non_mapping_frontmatter(
        self, package_table: RuleTable
    ) -> None:
        #: Given
        database = Database.from_snapshot(
            _snapshot(_budget(1000), guide=GUIDE_TEXT.encode(), review=b'---\n- review\n---\n'),
            builtin_layers=(SKILLS_LAYER,),
        )
        subjects = (_item(database, _location(database, REVIEW)),)

        #: When
        reports = check_subjects(database, subjects, package_table, {})

        #: Then
        occurrence = NonMappingFrontmatter(owner=REVIEW_OWNER, line=LineNumber(NonZeroUnsignedInt(1)))
        assert reports == (
            CheckedItem(
                ItemRef(REVIEW.path),
                diagnostics=(RuleDiagnostic(REVIEW_FILE, occurrence, Severity.ERROR),),
                ungoverned=SKILL_UNGOVERNED,
            ),
        ), 'LC203 runs at deny over a skill whose block is not a mapping'

    def test_check_subjects_with_a_skill_named_otherwise_reports_name_mismatch(self, package_table: RuleTable) -> None:
        #: Given
        database = Database.from_snapshot(
            _snapshot(
                _budget(1000),
                guide=GUIDE_TEXT.encode(),
                review=b'---\nname: code-review\ndescription: Review a change.\n---\n',
            ),
            builtin_layers=(SKILLS_LAYER,),
        )
        subjects = (_item(database, _location(database, REVIEW)),)

        #: When
        reports = check_subjects(database, subjects, package_table, {})

        #: Then
        occurrence = NameMismatch(owner=REVIEW_OWNER, line=LineNumber(NonZeroUnsignedInt(2)), name='code-review')
        assert reports == (
            CheckedItem(
                ItemRef(REVIEW.path),
                diagnostics=(RuleDiagnostic(REVIEW_FILE, occurrence, Severity.ERROR),),
                ungoverned=SKILL_UNGOVERNED,
            ),
        ), 'LC204 runs at deny over a skill whose `name` is not its directory name'

    def test_check_subjects_with_a_skill_repeating_a_key_reports_duplicate_key(self, package_table: RuleTable) -> None:
        #: Given
        database = Database.from_snapshot(
            _snapshot(
                _budget(1000),
                guide=GUIDE_TEXT.encode(),
                review=b'---\nname: review\nname: review\ndescription: Review a change.\n---\n',
            ),
            builtin_layers=(SKILLS_LAYER,),
        )
        subjects = (_item(database, _location(database, REVIEW)),)

        #: When
        reports = check_subjects(database, subjects, package_table, {})

        #: Then
        occurrence = DuplicateKey(
            owner=REVIEW_OWNER,
            line=LineNumber(NonZeroUnsignedInt(3)),
            key='name',
            first_line=LineNumber(NonZeroUnsignedInt(2)),
            kept_line=LineNumber(NonZeroUnsignedInt(3)),
        )
        assert reports == (
            CheckedItem(
                ItemRef(REVIEW.path),
                diagnostics=(RuleDiagnostic(REVIEW_FILE, occurrence, Severity.ERROR),),
                ungoverned=SKILL_UNGOVERNED,
            ),
        ), 'LC205 runs at deny over a skill that writes a key again'

    def test_check_subjects_with_a_linked_skill_named_for_its_target_reports_where_the_link_leads(
        self, package_table: RuleTable
    ) -> None:
        #: Given
        # What a scan records for `.agents/skills/review -> ../../skills/code-review`, whose `name` is the target's.
        shipped = from_tree(
            {
                '.agents': {'skills': {}},
                'skills': {
                    'code-review': {'SKILL.md': b'---\nname: code-review\ndescription: Review a change.\n---\n'}
                },
            }
        )
        records: dict[RootRelativePath, EntryRecord] = dict(shipped.records)
        records[RootRelativePath.parse('.agents/skills/review')] = SymlinkRecord(_target('../../skills/code-review'))
        database = Database.from_snapshot(Snapshot(SnapshotRecords(records)), builtin_layers=(SKILLS_LAYER,))
        subjects = (_item(database, _location(database, REVIEW)),)

        #: When
        reports = check_subjects(database, subjects, package_table, {})

        #: Then
        owner = SkillFrontmatterOwner(
            directory_name=PathComponent.parse('review'),
            link_target=ResolvedPath(RootRelativePath.parse('skills/code-review')),
        )
        occurrence = NameMismatch(owner=owner, line=LineNumber(NonZeroUnsignedInt(2)), name='code-review')
        assert reports == (
            CheckedItem(
                ItemRef(REVIEW.path),
                diagnostics=(RuleDiagnostic(REVIEW_FILE, occurrence, Severity.ERROR),),
                ungoverned=SKILL_UNGOVERNED,
            ),
        ), 'a skill is held to the name it is listed under, and its occurrence carries where the link leads'

    def test_check_subjects_with_no_enabled_rule_over_the_frontmatter_block_never_parses_the_frontmatter(
        self,
    ) -> None:
        #: Given
        # a frontmatter schema governs the document, which has no block, and the skill has none either
        database = CountingDatabase.from_snapshot(
            _snapshot(OBJECT_SCHEMA, guide=GUIDE_TEXT.encode(), review=b'# Review\n'),
            builtin_layers=(SKILLS_LAYER,),
        )
        severities: dict[type[Rule], Severity] = {TooManyTokens: Severity.ERROR, TooManyLines: Severity.ERROR}
        table = RuleTable(severities)
        subjects = (GUIDE, _item(database, _location(database, REVIEW)))

        #: When
        check_subjects(database, subjects, table, {})

        #: Then
        assert database.parsed_frontmatters == [], 'no enabled rule reads the frontmatter, so it is never parsed'
        assert database.query_reads(frontmatter_schema_problems, ItemRef(GUIDE.path)) == frozenset()
        assert database.query_reads(frontmatter_schema_problems, ItemRef(REVIEW_FILE)) == frozenset()

    def test_check_subjects_with_no_frontmatter_schema_never_parses_a_document_frontmatter(
        self, package_table: RuleTable
    ) -> None:
        #: Given
        # no specification states a frontmatter schema, but the package governs every skill's frontmatter
        database = CountingDatabase.from_snapshot(
            _snapshot(_budget(1000), guide=GUIDE_TEXT.encode()), builtin_layers=(SKILLS_LAYER,)
        )
        subjects = (GUIDE, _item(database, _location(database, REVIEW)), INTRO)

        #: When
        check_subjects(database, subjects, package_table, {})

        #: Then
        assert ItemRef(GUIDE.path) not in database.parsed_frontmatters, (
            'no schema governs the guide, so governance stops the rules over the frontmatter before they parse it'
        )
        assert ItemRef(INTRO.path) not in database.parsed_frontmatters, (
            'no schema governs the intro, so governance stops the rules over the frontmatter before they parse it'
        )

    def test_check_subjects_with_only_a_namespace_frontmatter_schema_reports_the_frontmatter_as_ungoverned(
        self, package_table: RuleTable
    ) -> None:
        #: Given
        # a namespace narrows its corpus's frontmatter schema, and the corpus states none
        snapshot = from_tree(
            {
                'docs': {
                    '__meta__': {
                        'code.md': b'# Code\n',
                        'code.spec.json': _budget(1000),
                        'code-python.md': b'# Code Python\n',
                        'code-python.spec.json': OBJECT_SCHEMA,
                    },
                    'code': {'python-typing.md': b'# Typing\n'},
                }
            }
        )
        typing = ItemRef(RootRelativePath.parse('docs/code/python-typing.md'))
        database = Database.from_snapshot(snapshot, builtin_layers=(SKILLS_LAYER,))

        #: When
        reports = check_subjects(database, (typing,), package_table, {})

        #: Then
        assert reports == (
            CheckedItem(
                ItemRef(typing.path),
                diagnostics=(),
                ungoverned=(SpecPart.FRONTMATTER, SpecPart.OUTLINE),
            ),
        ), 'a namespace schema narrows a corpus schema and cannot supply one, so no rule over the frontmatter runs'

    def test_check_subjects_with_a_document_breaking_its_schema_reports_each_schema_rule(
        self, package_table: RuleTable
    ) -> None:
        #: Given
        guide = b'---\nname: guide\ndescription: [a]\nextra: y\nstatus: Final\n---\n# Guide\n'
        database = Database.from_snapshot(_snapshot(GUIDE_SCHEMA, guide=guide), builtin_layers=(SKILLS_LAYER,))

        #: When
        reports = check_subjects(database, (GUIDE,), package_table, {})

        #: Then
        line_1 = LineNumber(NonZeroUnsignedInt(1))
        missing_field = MissingField(
            source=StructureSpecSchema(spec=CODE_SPEC),
            line=line_1,
            problem=MissingFieldProblem('owner', "'owner' is a required property"),
        )
        unknown_field = UnknownField(
            source=StructureSpecSchema(spec=CODE_SPEC),
            line=LineNumber(NonZeroUnsignedInt(4)),
            problem=UnknownFieldProblem(
                'extra',
                "Additional properties are not allowed ('extra' was unexpected)",
                known_fields=('name', 'description', 'status'),
            ),
        )
        wrong_type = WrongType(
            source=StructureSpecSchema(spec=CODE_SPEC),
            line=LineNumber(NonZeroUnsignedInt(3)),
            problem=WrongTypeProblem(
                'description', "['a'] is not of type 'string'", (JsonType.STRING,), JsonType.ARRAY
            ),
        )
        invalid_value = InvalidValue(
            source=StructureSpecSchema(spec=CODE_SPEC),
            line=LineNumber(NonZeroUnsignedInt(5)),
            problem=InvalidValueProblem(
                'status', "'Final' does not match '^(draft|stable)$'", PatternMismatch('^(draft|stable)$')
            ),
        )
        too_few_fields = TooFewFields(
            source=StructureSpecSchema(spec=CODE_SPEC),
            line=line_1,
            limit=FieldLimit(UnsignedInt(6)),
            field_count=FieldCount(UnsignedInt(4)),
        )
        assert reports == (
            CheckedItem(
                ItemRef(GUIDE.path),
                diagnostics=(
                    RuleDiagnostic(GUIDE.path, missing_field, Severity.ERROR),
                    RuleDiagnostic(GUIDE.path, unknown_field, Severity.WARNING),
                    RuleDiagnostic(GUIDE.path, wrong_type, Severity.ERROR),
                    RuleDiagnostic(GUIDE.path, invalid_value, Severity.ERROR),
                    RuleDiagnostic(GUIDE.path, too_few_fields, Severity.ERROR),
                ),
                ungoverned=(SpecPart.OUTLINE, SpecPart.BUDGET),
            ),
        ), (
            'LC206, LC208, LC209 and LC214 run at deny and LC207 at warn, each on its own problem, on its field line '
            'or line 1, naming the specification'
        )

    def test_check_subjects_with_a_skill_breaking_the_agent_skills_schema_reports_each_schema_rule(
        self, package_table: RuleTable
    ) -> None:
        #: Given
        # no description, an empty compatibility, a metadata that is not a mapping, and a key it does not define
        review = b'---\nname: review\ncompatibility: ""\nmetadata: z\nextra: y\n---\n# Review\n'
        database = Database.from_snapshot(
            _snapshot(_budget(1000), guide=GUIDE_TEXT.encode(), review=review),
            builtin_layers=(SKILLS_LAYER,),
        )
        subjects = (_item(database, _location(database, REVIEW)),)

        #: When
        reports = check_subjects(database, subjects, package_table, {})

        #: Then
        line_1 = LineNumber(NonZeroUnsignedInt(1))
        missing_field = MissingField(
            source=AgentSkillsSchema(),
            line=line_1,
            problem=MissingFieldProblem('description', '`description` is required', guidance=DESCRIPTION_GUIDANCE),
        )
        unknown_field = UnknownField(
            source=AgentSkillsSchema(),
            line=LineNumber(NonZeroUnsignedInt(5)),
            problem=UnknownFieldProblem(
                'extra',
                '`extra` is not a field of the Agent Skills specification',
                known_fields=('name', 'description', 'license', 'compatibility', 'metadata', 'allowed-tools'),
            ),
        )
        wrong_type = WrongType(
            source=AgentSkillsSchema(),
            line=LineNumber(NonZeroUnsignedInt(4)),
            problem=WrongTypeProblem(
                'metadata',
                '`metadata` must be a mapping of strings to strings',
                (JsonType.OBJECT,),
                JsonType.STRING,
                guidance=METADATA_GUIDANCE,
            ),
        )
        invalid_value = InvalidValue(
            source=AgentSkillsSchema(),
            line=LineNumber(NonZeroUnsignedInt(3)),
            problem=InvalidValueProblem(
                'compatibility',
                'skill compatibility cannot be empty; leave the field out instead',
                OtherValueConstraint(),
                guidance=COMPATIBILITY_GUIDANCE,
            ),
        )
        assert reports == (
            CheckedItem(
                ItemRef(REVIEW.path),
                diagnostics=(
                    RuleDiagnostic(REVIEW_FILE, missing_field, Severity.ERROR),
                    RuleDiagnostic(REVIEW_FILE, unknown_field, Severity.WARNING),
                    RuleDiagnostic(REVIEW_FILE, wrong_type, Severity.ERROR),
                    RuleDiagnostic(REVIEW_FILE, invalid_value, Severity.ERROR),
                ),
                ungoverned=SKILL_UNGOVERNED,
            ),
        ), 'the schema rules judge a skill against the Agent Skills specification, naming no specification file'

    def test_check_subjects_with_a_document_two_schemas_govern_notes_each_problem_with_its_own_specification(
        self, package_table: RuleTable
    ) -> None:
        #: Given
        namespace_spec = RootRelativePath.parse('docs/__meta__/code-python.spec.json')
        snapshot = from_tree(
            {
                'docs': {
                    '__meta__': {
                        'code.md': b'# Code\n',
                        'code.spec.json': b'{"frontmatter": {"type": "object", "required": ["status"]}}',
                        'code-python.md': b'# Code Python\n',
                        'code-python.spec.json': b'{"frontmatter": {"type": "object", "required": ["owner"]}}',
                    },
                    'code': {'python-typing.md': b'---\nname: python-typing\n---\n# Typing\n'},
                }
            }
        )
        database = Database.from_snapshot(snapshot, builtin_layers=(SKILLS_LAYER,))
        typing = ItemRef(RootRelativePath.parse('docs/code/python-typing.md'))

        #: When
        reports = check_subjects(database, (typing,), package_table, {})

        #: Then
        line_1 = LineNumber(NonZeroUnsignedInt(1))
        status = MissingField(
            source=StructureSpecSchema(spec=CODE_SPEC),
            line=line_1,
            problem=MissingFieldProblem('status', "'status' is a required property"),
        )
        owner = MissingField(
            source=StructureSpecSchema(spec=namespace_spec),
            line=line_1,
            problem=MissingFieldProblem('owner', "'owner' is a required property"),
        )
        assert reports == (
            CheckedItem(
                ItemRef(typing.path),
                diagnostics=(
                    RuleDiagnostic(typing.path, status, Severity.ERROR),
                    RuleDiagnostic(typing.path, owner, Severity.ERROR),
                ),
                ungoverned=(SpecPart.OUTLINE, SpecPart.BUDGET),
            ),
        ), 'each schema is applied on its own, and each problem names the specification whose schema found it'

    def test_check_subjects_with_no_frontmatter_schema_reports_the_schema_problems_as_ungoverned(
        self, package_table: RuleTable
    ) -> None:
        #: Given
        database = Database.from_snapshot(
            _snapshot(_budget(1000), guide=b'---\nname: [1]\n---\n# Guide\n'), builtin_layers=(SKILLS_LAYER,)
        )

        #: When
        reports = check_subjects(database, (GUIDE,), package_table, {})

        #: Then
        assert reports == (
            CheckedItem(
                ItemRef(GUIDE.path),
                diagnostics=(),
                ungoverned=(SpecPart.FRONTMATTER, SpecPart.OUTLINE),
            ),
        ), 'no specification states a frontmatter schema, which is coverage, not a diagnostic'

    def test_check_subjects_with_a_block_that_is_not_a_mapping_reports_no_schema_rule(
        self, package_table: RuleTable
    ) -> None:
        #: Given
        database = Database.from_snapshot(
            _snapshot(GUIDE_SCHEMA, guide=b'---\n- status\n---\n# Guide\n'), builtin_layers=(SKILLS_LAYER,)
        )

        #: When
        reports = check_subjects(database, (GUIDE,), package_table, {})

        #: Then
        occurrence = NonMappingFrontmatter(owner=GUIDE_OWNER, line=LineNumber(NonZeroUnsignedInt(1)))
        assert reports == (
            CheckedItem(
                ItemRef(GUIDE.path),
                diagnostics=(RuleDiagnostic(GUIDE.path, occurrence, Severity.ERROR),),
                ungoverned=(SpecPart.OUTLINE, SpecPart.BUDGET),
            ),
        ), 'LC203 alone reports a block that is not a mapping: it is held to no schema, so no schema rule fires'

    def test_check_subjects_with_only_the_block_rules_enabled_never_holds_the_frontmatter_to_a_schema(self) -> None:
        #: Given
        # both subjects break their schema, but only the frontmatter block rules are enabled
        database = CountingDatabase.from_snapshot(
            _snapshot(GUIDE_SCHEMA, guide=b'---\nname: guide\n---\n', review=b'---\nname: review\n---\n'),
            builtin_layers=(SKILLS_LAYER,),
        )
        severities: dict[type[Rule], Severity] = {
            MissingFrontmatter: Severity.ERROR,
            InvalidYaml: Severity.ERROR,
            NonMappingFrontmatter: Severity.ERROR,
            NameMismatch: Severity.ERROR,
            DuplicateKey: Severity.ERROR,
        }
        table = RuleTable(severities)
        subjects = (GUIDE, _item(database, _location(database, REVIEW)))

        #: When
        check_subjects(database, subjects, table, {})

        #: Then
        assert database.query_reads(frontmatter_schema_problems, ItemRef(GUIDE.path)) == frozenset()
        assert database.query_reads(frontmatter_schema_problems, ItemRef(REVIEW_FILE)) == frozenset()

    def test_check_subjects_with_a_document_without_its_title_reports_missing_title(
        self, package_table: RuleTable
    ) -> None:
        #: Given
        structure_spec = b'{"empty_sections": "forbidden"}'
        database = Database.from_snapshot(
            _snapshot(structure_spec, guide=b'## Install\n\nRun it once.\n'), builtin_layers=(SKILLS_LAYER,)
        )

        #: When
        reports = check_subjects(database, (GUIDE,), package_table, {})

        #: Then
        missing = MissingTitle(line=LineNumber(NonZeroUnsignedInt(1)))
        assert reports == (
            CheckedItem(
                ItemRef(GUIDE.path),
                diagnostics=(RuleDiagnostic(GUIDE.path, missing, Severity.ERROR),),
                ungoverned=(
                    SpecPart.FRONTMATTER,
                    SpecPart.OUTLINE,
                    SpecPart.BUDGET,
                ),
            ),
        ), (
            'OUT001 runs at deny over a document a structure specification governs, under that specification, and '
            'OUT003 leaves the untitled document to it'
        )

    def test_check_subjects_with_a_document_carrying_a_second_title_reports_extra_title(
        self, package_table: RuleTable
    ) -> None:
        #: Given
        structure_spec = b'{"empty_sections": "forbidden"}'
        guide = b'# Guide\n\nRun it once.\n\n# Again\n\nRun it twice.\n'
        database = Database.from_snapshot(_snapshot(structure_spec, guide=guide), builtin_layers=(SKILLS_LAYER,))

        #: When
        reports = check_subjects(database, (GUIDE,), package_table, {})

        #: Then
        first_title = _heading(guide, 'Guide')
        occurrence = ExtraTitle(line=LineNumber(NonZeroUnsignedInt(5)), first_title=first_title)
        assert reports == (
            CheckedItem(
                ItemRef(GUIDE.path),
                diagnostics=(RuleDiagnostic(GUIDE.path, occurrence, Severity.ERROR),),
                ungoverned=(
                    SpecPart.FRONTMATTER,
                    SpecPart.OUTLINE,
                    SpecPart.BUDGET,
                ),
            ),
        ), 'OUT002 runs at deny over a document a structure specification governs, at the title after the first'

    def test_check_subjects_with_a_document_opening_with_a_section_reports_title_not_first(
        self, package_table: RuleTable
    ) -> None:
        #: Given
        structure_spec = b'{"empty_sections": "forbidden"}'
        guide = b'## Install\n\nRun it once.\n\n# Guide\n\nWhat the guide covers.\n'
        database = Database.from_snapshot(_snapshot(structure_spec, guide=guide), builtin_layers=(SKILLS_LAYER,))

        #: When
        reports = check_subjects(database, (GUIDE,), package_table, {})

        #: Then
        occurrence = TitleNotFirst(
            line=LineNumber(NonZeroUnsignedInt(1)), level=2, title_line=LineNumber(NonZeroUnsignedInt(5))
        )
        assert reports == (
            CheckedItem(
                ItemRef(GUIDE.path),
                diagnostics=(RuleDiagnostic(GUIDE.path, occurrence, Severity.ERROR),),
                ungoverned=(
                    SpecPart.FRONTMATTER,
                    SpecPart.OUTLINE,
                    SpecPart.BUDGET,
                ),
            ),
        ), 'OUT003 runs at deny over a document a structure specification governs, at the heading opening it'

    def test_check_subjects_with_a_document_carrying_its_title_reports_it_clean(self, package_table: RuleTable) -> None:
        #: Given
        structure_spec = b'{"empty_sections": "forbidden"}'
        database = Database.from_snapshot(
            _snapshot(structure_spec, guide=GUIDE_TEXT.encode()), builtin_layers=(SKILLS_LAYER,)
        )

        #: When
        reports = check_subjects(database, (GUIDE,), package_table, {})

        #: Then
        assert reports == (
            CheckedItem(
                ItemRef(GUIDE.path),
                diagnostics=(),
                ungoverned=(
                    SpecPart.FRONTMATTER,
                    SpecPart.OUTLINE,
                    SpecPart.BUDGET,
                ),
            ),
        ), 'a document carrying its title is governed for its headings, and clean'

    def test_check_subjects_with_an_empty_section_reports_empty_section(self, package_table: RuleTable) -> None:
        #: Given
        guide = b'# Guide\n\n## Install\n\n## Run\n\nRun it once.\n'
        database = Database.from_snapshot(
            _snapshot(b'{"empty_sections": "forbidden"}', guide=guide), builtin_layers=(SKILLS_LAYER,)
        )

        #: When
        reports = check_subjects(database, (GUIDE,), package_table, {})

        #: Then
        occurrence = EmptySection(
            spec=CODE_SPEC, line=LineNumber(NonZeroUnsignedInt(3)), section='Install', role=OtherSection()
        )
        assert reports == (
            CheckedItem(
                ItemRef(GUIDE.path),
                diagnostics=(RuleDiagnostic(GUIDE.path, occurrence, Severity.ERROR),),
                ungoverned=(
                    SpecPart.FRONTMATTER,
                    SpecPart.OUTLINE,
                    SpecPart.BUDGET,
                ),
            ),
        ), 'OUT004 runs at deny over a document whose specification forbids empty sections, at the empty heading'

    def test_check_subjects_with_a_forbidden_section_reports_forbidden_section(self, package_table: RuleTable) -> None:
        #: Given
        guide = b'# Guide\n\n## Run\n\nRun it once.\n\n## Changelog\n\nAdded the run step.\n'
        database = Database.from_snapshot(
            _snapshot(b'{"forbidden": ["Changelog"]}', guide=guide), builtin_layers=(SKILLS_LAYER,)
        )

        #: When
        reports = check_subjects(database, (GUIDE,), package_table, {})

        #: Then
        occurrence = ForbiddenSection(spec=CODE_SPEC, line=LineNumber(NonZeroUnsignedInt(7)), section='Changelog')
        assert reports == (
            CheckedItem(
                ItemRef(GUIDE.path),
                diagnostics=(RuleDiagnostic(GUIDE.path, occurrence, Severity.ERROR),),
                ungoverned=(
                    SpecPart.FRONTMATTER,
                    SpecPart.OUTLINE,
                    SpecPart.BUDGET,
                ),
            ),
        ), 'OUT005 runs at deny over a document whose specification forbids a section, at the forbidden heading'

    def test_check_subjects_with_a_section_over_its_word_cap_reports_section_too_many_words(
        self, package_table: RuleTable
    ) -> None:
        #: Given
        guide = b'# Guide\n\n## Run\n\nRun it once, then again.\n'
        database = Database.from_snapshot(
            _snapshot(b'{"outline": [{"section": "Run", "words": 3}]}', guide=guide),
            builtin_layers=(SKILLS_LAYER,),
        )

        #: When
        reports = check_subjects(database, (GUIDE,), package_table, {})

        #: Then
        occurrence = SectionTooManyWords(
            spec=CODE_SPEC,
            line=LineNumber(NonZeroUnsignedInt(3)),
            section='Run',
            overrun=overrun(5, 3),
            cap_source=NamedSectionCap(),
        )
        assert reports == (
            CheckedItem(
                ItemRef(GUIDE.path),
                diagnostics=(RuleDiagnostic(GUIDE.path, occurrence, Severity.ERROR),),
                ungoverned=(SpecPart.FRONTMATTER, SpecPart.BUDGET),
            ),
        ), 'LEN003 runs at deny over a document whose specification caps a section, at the section over its cap'

    def test_check_subjects_with_a_title_over_its_word_cap_reports_title_too_many_words(
        self, package_table: RuleTable
    ) -> None:
        #: Given
        guide = b'# Setting up the guide\n\nRun it once, then again.\n'
        database = Database.from_snapshot(
            _snapshot(b'{"title": {"words": 3}}', guide=guide), builtin_layers=(SKILLS_LAYER,)
        )

        #: When
        reports = check_subjects(database, (GUIDE,), package_table, {})

        #: Then
        occurrence = TitleTooManyWords(spec=CODE_SPEC, line=LineNumber(NonZeroUnsignedInt(1)), overrun=overrun(4, 3))
        assert reports == (
            CheckedItem(
                ItemRef(GUIDE.path),
                diagnostics=(RuleDiagnostic(GUIDE.path, occurrence, Severity.ERROR),),
                ungoverned=(
                    SpecPart.FRONTMATTER,
                    SpecPart.OUTLINE,
                    SpecPart.BUDGET,
                ),
            ),
        ), 'LEN004 runs at deny over a document whose specification caps the title, at the title over its cap'

    def test_check_subjects_with_a_title_over_its_character_cap_reports_title_too_long(
        self, package_table: RuleTable
    ) -> None:
        #: Given
        guide = b'# Setting up the guide\n\nRun it once, then again.\n'
        database = Database.from_snapshot(
            _snapshot(b'{"title": {"chars": 12}}', guide=guide), builtin_layers=(SKILLS_LAYER,)
        )

        #: When
        reports = check_subjects(database, (GUIDE,), package_table, {})

        #: Then
        occurrence = TitleTooLong(spec=CODE_SPEC, line=LineNumber(NonZeroUnsignedInt(1)), overrun=overrun(20, 12))
        assert reports == (
            CheckedItem(
                ItemRef(GUIDE.path),
                diagnostics=(RuleDiagnostic(GUIDE.path, occurrence, Severity.ERROR),),
                ungoverned=(
                    SpecPart.FRONTMATTER,
                    SpecPart.OUTLINE,
                    SpecPart.BUDGET,
                ),
            ),
        ), 'LEN005 runs at deny over a document whose specification caps the title, at the title over its cap'

    def test_check_subjects_with_a_title_failing_its_pattern_reports_invalid_title(
        self, package_table: RuleTable
    ) -> None:
        #: Given
        guide = b'# setting up the guide\n\nRun it once, then again.\n'
        database = Database.from_snapshot(
            _snapshot(b'{"title": {"pattern": "^[A-Z]"}}', guide=guide), builtin_layers=(SKILLS_LAYER,)
        )

        #: When
        reports = check_subjects(database, (GUIDE,), package_table, {})

        #: Then
        occurrence = InvalidTitle(
            spec=CODE_SPEC,
            line=LineNumber(NonZeroUnsignedInt(1)),
            title='setting up the guide',
            pattern=TitlePattern(re.compile('^[A-Z]')),
        )
        assert reports == (
            CheckedItem(
                ItemRef(GUIDE.path),
                diagnostics=(RuleDiagnostic(GUIDE.path, occurrence, Severity.ERROR),),
                ungoverned=(
                    SpecPart.FRONTMATTER,
                    SpecPart.OUTLINE,
                    SpecPart.BUDGET,
                ),
            ),
        ), 'OUT009 runs at deny over a document whose specification sets a title pattern, at the title failing it'

    def test_check_subjects_with_no_enabled_rule_over_the_headings_never_parses_the_document(self) -> None:
        #: Given
        database = CountingDatabase.from_snapshot(
            _snapshot(b'{"empty_sections": "forbidden"}', guide=GUIDE_TEXT.encode()),
            builtin_layers=(SKILLS_LAYER,),
        )
        severities: dict[type[Rule], Severity] = {TooManyTokens: Severity.ERROR}
        table = RuleTable(severities)

        #: When
        check_subjects(database, (GUIDE,), table, {})

        #: Then
        assert database.parsed_documents == [], 'no enabled rule reads the headings, so the document is never parsed'

    def test_check_subjects_with_a_document_lacking_a_section_reports_missing_section(
        self, package_table: RuleTable
    ) -> None:
        #: Given
        outline = b'{"outline": [{"section": "Install"}, {"section": "Usage", "description": "How to run it."}]}'
        guide = b'# Guide\n\n## Install\n\nRun it once.\n'
        database = Database.from_snapshot(_snapshot(outline, guide=guide), builtin_layers=(SKILLS_LAYER,))

        #: When
        reports = check_subjects(database, (GUIDE,), package_table, {})

        #: Then
        occurrence = MissingSection(
            spec=CODE_SPEC,
            section=SectionName.parse('Usage'),
            before=DocumentEnd(last_line=LineNumber(NonZeroUnsignedInt(5)), after=_section(guide, 'Install')),
            description='How to run it.',
            example=None,
        )
        assert reports == (
            CheckedItem(
                ItemRef(GUIDE.path),
                diagnostics=(RuleDiagnostic(GUIDE.path, occurrence, Severity.ERROR),),
                ungoverned=(SpecPart.FRONTMATTER, SpecPart.BUDGET),
            ),
        ), 'OUT006 runs at deny over a document lacking a section its outline requires, at its last line'

    def test_check_subjects_with_a_document_writing_a_section_out_of_order_reports_section_out_of_order(
        self, package_table: RuleTable
    ) -> None:
        #: Given
        outline = b'{"outline": [{"section": "Install"}, {"section": "Usage"}]}'
        guide = b'# Guide\n\n## Usage\n\nRun it.\n\n## Install\n\nRun it once.\n'
        database = Database.from_snapshot(_snapshot(outline, guide=guide), builtin_layers=(SKILLS_LAYER,))

        #: When
        reports = check_subjects(database, (GUIDE,), package_table, {})

        #: Then
        expected = ExpectedSection(name=SectionName.parse('Install'), written_at=_section(guide, 'Install'))
        occurrence = SectionOutOfOrder(
            spec=CODE_SPEC, line=LineNumber(NonZeroUnsignedInt(3)), section='Usage', placement=expected
        )
        assert reports == (
            CheckedItem(
                ItemRef(GUIDE.path),
                diagnostics=(RuleDiagnostic(GUIDE.path, occurrence, Severity.ERROR),),
                ungoverned=(SpecPart.FRONTMATTER, SpecPart.BUDGET),
            ),
        ), 'OUT007 runs at deny over a document writing a section where its outline places another, at its heading'

    def test_check_subjects_with_a_document_writing_a_section_its_outline_does_not_name_reports_unexpected_section(
        self, package_table: RuleTable
    ) -> None:
        #: Given
        outline = b'{"outline": [{"section": "Install"}, {"section": "Usage"}]}'
        guide = b'# Guide\n\n## Install\n\nRun it once.\n\n## Tips\n\nRun it often.\n\n## Usage\n\nRun it.\n'
        database = Database.from_snapshot(_snapshot(outline, guide=guide), builtin_layers=(SKILLS_LAYER,))

        #: When
        reports = check_subjects(database, (GUIDE,), package_table, {})

        #: Then
        expected = ExpectedSection(name=SectionName.parse('Usage'), written_at=_section(guide, 'Usage'))
        occurrence = UnexpectedSection(
            spec=CODE_SPEC, line=LineNumber(NonZeroUnsignedInt(7)), section='Tips', placement=expected
        )
        assert reports == (
            CheckedItem(
                ItemRef(GUIDE.path),
                diagnostics=(RuleDiagnostic(GUIDE.path, occurrence, Severity.ERROR),),
                ungoverned=(SpecPart.FRONTMATTER, SpecPart.BUDGET),
            ),
        ), 'OUT008 runs at deny over a document writing a section its outline does not name, at its heading'

    def test_check_subjects_with_a_document_following_its_outline_reports_it_clean(
        self, package_table: RuleTable
    ) -> None:
        #: Given
        outline = b'{"outline": [{"section": "Install"}]}'
        database = Database.from_snapshot(
            _snapshot(outline, guide=b'# Guide\n\n## Install\n\nRun it once.\n'),
            builtin_layers=(SKILLS_LAYER,),
        )

        #: When
        reports = check_subjects(database, (GUIDE,), package_table, {})

        #: Then
        assert reports == (
            CheckedItem(
                ItemRef(GUIDE.path),
                diagnostics=(),
                ungoverned=(SpecPart.FRONTMATTER, SpecPart.BUDGET),
            ),
        ), 'a document whose sections match its outline is governed for its outline, and clean'

    def test_check_subjects_with_no_enabled_rule_over_the_outline_never_parses_the_document(self) -> None:
        #: Given
        database = CountingDatabase.from_snapshot(
            _snapshot(b'{"outline": [{"section": "Install"}]}', guide=GUIDE_TEXT.encode()),
            builtin_layers=(SKILLS_LAYER,),
        )
        severities: dict[type[Rule], Severity] = {TooManyTokens: Severity.ERROR}
        table = RuleTable(severities)

        #: When
        check_subjects(database, (GUIDE,), table, {})

        #: Then
        assert database.parsed_documents == [], 'no enabled rule reads the outline, so the document is never parsed'

    def test_check_subjects_with_an_absolute_link_in_a_document_reports_absolute_link_on_its_line(
        self, package_table: RuleTable
    ) -> None:
        #: Given
        guide = b'# Guide\n\nRead [the setup](/docs/code/setup.md).\n'
        database = Database.from_snapshot(_snapshot(_budget(1000), guide=guide), builtin_layers=(SKILLS_LAYER,))

        #: When
        reports = check_subjects(database, (GUIDE,), package_table, {})

        #: Then
        occurrence = AbsoluteLink(line=LineNumber(NonZeroUnsignedInt(3)), url='/docs/code/setup.md')
        assert reports == (
            CheckedItem(
                ItemRef(GUIDE.path),
                diagnostics=(RuleDiagnostic(GUIDE.path, occurrence, Severity.ERROR),),
                ungoverned=(SpecPart.FRONTMATTER, SpecPart.OUTLINE),
            ),
        ), 'LINK001 runs at deny over a document its structure specification governs, on the line of the link'

    def test_check_subjects_with_an_absolute_link_in_a_skill_file_reports_absolute_link_at_its_skill_file(
        self, package_table: RuleTable
    ) -> None:
        #: Given
        review = REVIEW_FRONTMATTER + b'# Review\n\nRead [the diff](/tmp/diff.md).\n'
        database = Database.from_snapshot(
            _snapshot(_budget(1000), guide=GUIDE_TEXT.encode(), review=review),
            builtin_layers=(SKILLS_LAYER,),
        )
        subjects = (_item(database, _location(database, REVIEW)),)

        #: When
        reports = check_subjects(database, subjects, package_table, {})

        #: Then
        occurrence = AbsoluteLink(line=LineNumber(NonZeroUnsignedInt(7)), url='/tmp/diff.md')
        assert reports == (
            CheckedItem(
                ItemRef(REVIEW.path),
                diagnostics=(RuleDiagnostic(REVIEW_FILE, occurrence, Severity.ERROR),),
                ungoverned=SKILL_UNGOVERNED,
            ),
        ), "LINK001 runs at deny over a skill's SKILL.md, on the line of the link, counted from the file's first line"

    def test_check_subjects_with_an_absolute_link_in_a_nested_resource_reports_it_where_an_agent_reaches_it(
        self, package_table: RuleTable
    ) -> None:
        #: Given
        resource = b'# Deep\n\nSee [the diagram](/assets/flow.png).\n'
        snapshot = from_tree(
            {
                '.agents': {
                    'skills': {
                        'review': {
                            'SKILL.md': REVIEW_FRONTMATTER,
                            'references': {'deep': {'guide.md': resource}},
                        }
                    }
                }
            }
        )
        database = Database.from_snapshot(snapshot, builtin_layers=(SKILLS_LAYER,))
        guide = SkillResourceRef(REVIEW, SkillRelativePath.parse('references/deep/guide.md'))
        subjects = tuple(_item(database, item) for item in _resources(database, REVIEW))

        #: When
        reports = check_subjects(database, subjects, package_table, {})

        #: Then
        occurrence = AbsoluteLink(line=LineNumber(NonZeroUnsignedInt(3)), url='/assets/flow.png')
        resource_path = RootRelativePath.parse('.agents/skills/review/references/deep/guide.md')
        assert reports == (
            CheckedItem(
                ItemRef(guide.path),
                diagnostics=(RuleDiagnostic(resource_path, occurrence, Severity.ERROR),),
            ),
        ), 'LINK001 runs at deny over a resource, reported at the path an agent reaches it by, on the line of the link'

    def test_check_subjects_with_a_skill_and_its_resources_reports_each_as_its_own_subject(
        self, package_table: RuleTable
    ) -> None:
        #: Given
        snapshot = from_tree(
            {
                '.agents': {
                    'skills': {
                        'review': {
                            'SKILL.md': REVIEW_FRONTMATTER,
                            'references': {'a.md': b'Read [x](/x.md).\n', 'b.md': b'Read [y](y.md).\n'},
                        }
                    }
                }
            }
        )
        database = Database.from_snapshot(snapshot, builtin_layers=(SKILLS_LAYER,))
        first = SkillResourceRef(REVIEW, SkillRelativePath.parse('references/a.md'))
        second = SkillResourceRef(REVIEW, SkillRelativePath.parse('references/b.md'))
        subjects = (
            _item(database, _location(database, REVIEW)),
            *(_item(database, item) for item in _resources(database, REVIEW)),
        )

        #: When
        reports = check_subjects(database, subjects, package_table, {})

        #: Then
        occurrence = AbsoluteLink(line=LineNumber(NonZeroUnsignedInt(1)), url='/x.md')
        first_path = RootRelativePath.parse('.agents/skills/review/references/a.md')
        assert reports == (
            CheckedItem(ItemRef(REVIEW.path), diagnostics=(), ungoverned=SKILL_UNGOVERNED),
            CheckedItem(
                ItemRef(first.path),
                diagnostics=(RuleDiagnostic(first_path, occurrence, Severity.ERROR),),
            ),
            CheckedItem(ItemRef(second.path), diagnostics=()),
        ), 'a skill judges its SKILL.md alone, and each resource is reported on its own, in the order given'

    def test_check_subjects_with_an_undecodable_resource_reports_it_undecodable(self, package_table: RuleTable) -> None:
        #: Given
        snapshot = from_tree(
            {
                '.agents': {
                    'skills': {'review': {'SKILL.md': REVIEW_FRONTMATTER, 'references': {'cafe.md': b'# Caf\xe9\n'}}}
                }
            }
        )
        database = Database.from_snapshot(snapshot, builtin_layers=(SKILLS_LAYER,))
        cafe = SkillResourceRef(REVIEW, SkillRelativePath.parse('references/cafe.md'))
        subjects = tuple(_item(database, item) for item in _resources(database, REVIEW))

        #: When
        reports = check_subjects(database, subjects, package_table, {})

        #: Then
        assert reports == (UndecodableSubject(ItemRef(cafe.path), _CAFE_TITLE_FAILURE),), (
            'a resource that is not UTF-8 is judged by no rule'
        )

    def test_check_subjects_with_an_undecodable_skill_file_still_judges_its_resources(
        self, package_table: RuleTable
    ) -> None:
        #: Given
        snapshot = from_tree(
            {
                '.agents': {
                    'skills': {
                        'review': {'SKILL.md': b'---\nname: caf\xe9\n---\n', 'references': {'a.md': b'[x](/x.md)\n'}}
                    }
                }
            }
        )
        database = Database.from_snapshot(snapshot, builtin_layers=(SKILLS_LAYER,))
        resource = SkillResourceRef(REVIEW, SkillRelativePath.parse('references/a.md'))
        subjects = (
            _item(database, _location(database, REVIEW)),
            *(_item(database, item) for item in _resources(database, REVIEW)),
        )

        #: When
        reports = check_subjects(database, subjects, package_table, {})

        #: Then
        occurrence = AbsoluteLink(line=LineNumber(NonZeroUnsignedInt(1)), url='/x.md')
        assert reports == (
            UndecodableSubject(ItemRef(REVIEW.path), _CAFE_NAME_FAILURE),
            CheckedItem(
                ItemRef(resource.path),
                diagnostics=(RuleDiagnostic(resource.path, occurrence, Severity.ERROR),),
            ),
        ), 'each resource is a subject of its own, judged whatever bytes the SKILL.md holds'

    def test_check_subjects_with_a_skill_file_whose_block_is_not_yaml_still_judges_its_links(
        self, package_table: RuleTable
    ) -> None:
        #: Given
        review = '---\nname: [review\n---\nRead [x](/x.md).\n'
        database = Database.from_snapshot(
            _snapshot(_budget(1000), guide=GUIDE_TEXT.encode(), review=review.encode()),
            builtin_layers=(SKILLS_LAYER,),
        )
        subjects = (_item(database, _location(database, REVIEW)),)

        #: When
        reports = check_subjects(database, subjects, package_table, {})

        #: Then
        invalid_yaml = InvalidYaml(
            owner=REVIEW_OWNER,
            problem=_invalid_yaml_problem(review),
            stopped_at=LineNumber(NonZeroUnsignedInt(2)),
        )
        absolute_link = AbsoluteLink(line=LineNumber(NonZeroUnsignedInt(4)), url='/x.md')
        assert reports == (
            CheckedItem(
                ItemRef(REVIEW.path),
                diagnostics=(
                    RuleDiagnostic(REVIEW_FILE, invalid_yaml, Severity.ERROR),
                    RuleDiagnostic(REVIEW_FILE, absolute_link, Severity.ERROR),
                ),
                ungoverned=SKILL_UNGOVERNED,
            ),
        ), 'a link is judged whether or not the frontmatter parses, so a broken block hides no link diagnostic'

    def test_check_subjects_with_an_absolute_link_over_an_ungoverned_corpus_is_still_judged(
        self,
    ) -> None:
        #: Given
        # the corpus states no structure specification, so no facet governs its documents
        snapshot = from_tree(
            {
                'docs': {
                    '__meta__': {'code.md': b'# Code\n'},
                    'code': {'guide.md': b'# Guide\n\nRead [the setup](/setup.md).\n'},
                }
            }
        )
        database = Database.from_snapshot(snapshot, builtin_layers=(SKILLS_LAYER,))
        severities: dict[type[Rule], Severity] = {AbsoluteLink: Severity.ERROR}
        table = RuleTable(severities)

        #: When
        reports = check_subjects(database, (GUIDE,), table, {})

        #: Then
        assert reports == (
            CheckedItem(
                ItemRef(GUIDE.path),
                diagnostics=(
                    RuleDiagnostic(
                        GUIDE.path,
                        AbsoluteLink(line=LineNumber(NonZeroUnsignedInt(3)), url='/setup.md'),
                        Severity.ERROR,
                    ),
                ),
                ungoverned=(),
            ),
        ), 'Markdown syntax link rules judge documents independently of spec structure'

    def test_check_subjects_with_a_fragment_missing_from_a_document_reports_broken_fragment_on_its_line(
        self, package_table: RuleTable
    ) -> None:
        #: Given
        guide = b'# Guide\n\nSee [the title](#guide), then [install](#install).\n'
        database = Database.from_snapshot(_snapshot(_budget(1000), guide=guide), builtin_layers=(SKILLS_LAYER,))

        #: When
        reports = check_subjects(database, (GUIDE,), package_table, {})

        #: Then
        occurrence = BrokenFragment(line=LineNumber(NonZeroUnsignedInt(3)), url='#install', has_headings=True)
        assert reports == (
            CheckedItem(
                ItemRef(GUIDE.path),
                diagnostics=(RuleDiagnostic(GUIDE.path, occurrence, Severity.ERROR),),
                ungoverned=(SpecPart.FRONTMATTER, SpecPart.OUTLINE),
            ),
        ), "LINK002 runs at deny over a document, reporting the fragment its own headings lack and not the title's"

    def test_check_subjects_with_a_fragment_missing_from_a_skill_file_reports_broken_fragment_at_its_skill_file(
        self, package_table: RuleTable
    ) -> None:
        #: Given
        review = REVIEW_FRONTMATTER + b'# Review\n\nFollow [the steps](#steps).\n'
        database = Database.from_snapshot(
            _snapshot(_budget(1000), guide=GUIDE_TEXT.encode(), review=review),
            builtin_layers=(SKILLS_LAYER,),
        )
        subjects = (_item(database, _location(database, REVIEW)),)

        #: When
        reports = check_subjects(database, subjects, package_table, {})

        #: Then
        occurrence = BrokenFragment(line=LineNumber(NonZeroUnsignedInt(7)), url='#steps', has_headings=True)
        assert reports == (
            CheckedItem(
                ItemRef(REVIEW.path),
                diagnostics=(RuleDiagnostic(REVIEW_FILE, occurrence, Severity.ERROR),),
                ungoverned=SKILL_UNGOVERNED,
            ),
        ), "LINK002 runs at deny over a skill's SKILL.md, on the line of the link"

    def test_check_subjects_with_a_fragment_only_the_skill_file_has_reports_it_missing_from_the_resource(
        self, package_table: RuleTable
    ) -> None:
        #: Given
        # SKILL.md has the heading `Usage`, and both files link `#usage`: each is read against its own headings.
        review = REVIEW_FRONTMATTER + b'# Review\n\nSee [usage](#usage).\n\n## Usage\n'
        resource = b'# Checklist\n\nSee [usage](#usage).\n'
        snapshot = from_tree(
            {'.agents': {'skills': {'review': {'SKILL.md': review, 'references': {'checklist.md': resource}}}}}
        )
        database = Database.from_snapshot(snapshot, builtin_layers=(SKILLS_LAYER,))
        checklist = SkillResourceRef(REVIEW, SkillRelativePath.parse('references/checklist.md'))
        subjects = (
            _item(database, _location(database, REVIEW)),
            *(_item(database, item) for item in _resources(database, REVIEW)),
        )

        #: When
        reports = check_subjects(database, subjects, package_table, {})

        #: Then
        occurrence = BrokenFragment(line=LineNumber(NonZeroUnsignedInt(3)), url='#usage', has_headings=True)
        checklist_path = RootRelativePath.parse('.agents/skills/review/references/checklist.md')
        assert reports == (
            CheckedItem(ItemRef(REVIEW.path), diagnostics=(), ungoverned=SKILL_UNGOVERNED),
            CheckedItem(
                ItemRef(checklist.path),
                diagnostics=(RuleDiagnostic(checklist_path, occurrence, Severity.ERROR),),
            ),
        ), "a resource's fragment names one of its own headings, never the SKILL.md's, and is reported where it is"

    def test_check_subjects_with_escaping_links_reports_each_in_its_file_ordered_by_file_then_line(
        self, package_table: RuleTable
    ) -> None:
        #: Given
        review = REVIEW_FRONTMATTER + b'# Review\n\nRead [the guide](../../docs/guide.md).\n'
        snapshot = from_tree(
            {
                '.agents': {
                    'skills': {
                        'review': {
                            'SKILL.md': review,
                            'references': {
                                'a.md': b'[up](../a.md)\n\n[in](SKILL.md) and ![flow](../../flow.png)\n',
                                'deep': {'guide.md': b'# Guide\n\nBack to [the skill](../SKILL.md).\n'},
                            },
                        }
                    }
                }
            }
        )
        database = Database.from_snapshot(snapshot, builtin_layers=(SKILLS_LAYER,))
        a = SkillResourceRef(REVIEW, SkillRelativePath.parse('references/a.md'))
        guide = SkillResourceRef(REVIEW, SkillRelativePath.parse('references/deep/guide.md'))
        subjects = (
            _item(database, _location(database, REVIEW)),
            *(_item(database, item) for item in _resources(database, REVIEW)),
        )

        #: When
        reports = check_subjects(database, subjects, package_table, {})

        #: Then
        assert reports == (
            CheckedItem(
                ItemRef(REVIEW.path),
                diagnostics=(
                    RuleDiagnostic(
                        REVIEW_FILE,
                        EscapingLink(
                            line=LineNumber(NonZeroUnsignedInt(7)),
                            url='../../docs/guide.md',
                            base=SkillRoot(RootRelativePath.parse('.agents/skills/review')),
                        ),
                        Severity.ERROR,
                    ),
                ),
                ungoverned=SKILL_UNGOVERNED,
            ),
            CheckedItem(
                ItemRef(a.path),
                diagnostics=(
                    RuleDiagnostic(
                        a.path,
                        EscapingLink(
                            line=LineNumber(NonZeroUnsignedInt(1)),
                            url='../a.md',
                            base=SkillRoot(RootRelativePath.parse('.agents/skills/review')),
                        ),
                        Severity.ERROR,
                    ),
                    RuleDiagnostic(
                        a.path,
                        EscapingLink(
                            line=LineNumber(NonZeroUnsignedInt(3)),
                            url='../../flow.png',
                            base=SkillRoot(RootRelativePath.parse('.agents/skills/review')),
                        ),
                        Severity.ERROR,
                    ),
                ),
            ),
            CheckedItem(
                ItemRef(guide.path),
                diagnostics=(
                    RuleDiagnostic(
                        guide.path,
                        EscapingLink(
                            line=LineNumber(NonZeroUnsignedInt(3)),
                            url='../SKILL.md',
                            base=SkillRoot(RootRelativePath.parse('.agents/skills/review')),
                        ),
                        Severity.ERROR,
                    ),
                ),
            ),
        ), 'the SKILL.md first, then each resource by path, each read from the skill root and located in its own file'

    def test_check_subjects_with_an_escaping_link_in_a_linked_skill_reports_it_where_the_agent_finds_it(
        self, package_table: RuleTable
    ) -> None:
        #: Given
        # What a scan records for `.agents/skills/review -> ../../skills/review`: the link in the skills directory,
        # and the skill's files at the resolved path it leads to.
        shipped = from_tree(
            {
                '.agents': {'skills': {}},
                'skills': {
                    'review': {
                        'SKILL.md': REVIEW_FRONTMATTER,
                        'references': {'a.md': b'See [the skill](../SKILL.md).\n'},
                    }
                },
            }
        )
        records: dict[RootRelativePath, EntryRecord] = dict(shipped.records)
        records[RootRelativePath.parse('.agents/skills/review')] = SymlinkRecord(_target('../../skills/review'))
        database = Database.from_snapshot(Snapshot(SnapshotRecords(records)), builtin_layers=(SKILLS_LAYER,))
        a = SkillResourceRef(REVIEW, SkillRelativePath.parse('references/a.md'))
        subjects = tuple(_item(database, item) for item in _resources(database, REVIEW))

        #: When
        reports = check_subjects(database, subjects, package_table, {})

        #: Then
        occurrence = EscapingLink(
            line=LineNumber(NonZeroUnsignedInt(1)),
            url='../SKILL.md',
            base=SkillRoot(RootRelativePath.parse('.agents/skills/review')),
        )
        resource_path = RootRelativePath.parse('.agents/skills/review/references/a.md')
        assert reports == (
            CheckedItem(
                ItemRef(a.path),
                diagnostics=(RuleDiagnostic(resource_path, occurrence, Severity.ERROR),),
            ),
        ), 'the resource is read through the linked entry, and reported under the skills directory'

    def test_check_subjects_with_a_link_back_in_by_the_repository_path_reports_it_escaping(
        self, package_table: RuleTable
    ) -> None:
        #: Given
        review = REVIEW_FRONTMATTER + b'See [the skill](../../skills/review/SKILL.md).\n'
        database = Database.from_snapshot(
            _snapshot(_budget(1000), guide=GUIDE_TEXT.encode(), review=review),
            builtin_layers=(SKILLS_LAYER,),
        )
        subjects = (_item(database, _location(database, REVIEW)),)

        #: When
        reports = check_subjects(database, subjects, package_table, {})

        #: Then
        occurrence = EscapingLink(
            line=LineNumber(NonZeroUnsignedInt(5)),
            url='../../skills/review/SKILL.md',
            base=SkillRoot(RootRelativePath.parse('.agents/skills/review')),
        )
        assert reports == (
            CheckedItem(
                ItemRef(REVIEW.path),
                diagnostics=(RuleDiagnostic(REVIEW_FILE, occurrence, Severity.ERROR),),
                ungoverned=SKILL_UNGOVERNED,
            ),
        ), 'the path alone decides, so a link out of the skill and back in by the repository path escapes'

    def test_check_subjects_with_a_document_link_climbing_its_directory_reports_nothing(
        self, package_table: RuleTable
    ) -> None:
        #: Given
        guide = b'# Guide\n\nRead [the intro](../code/intro.md).\n'
        database = Database.from_snapshot(_snapshot(_budget(1000), guide=guide), builtin_layers=(SKILLS_LAYER,))

        #: When
        reports = check_subjects(database, (GUIDE,), package_table, {})

        #: Then
        assert reports == (
            CheckedItem(
                ItemRef(GUIDE.path),
                diagnostics=(),
                ungoverned=(SpecPart.FRONTMATTER, SpecPart.OUTLINE),
            ),
        ), "a document's links are read from its own directory, so no rule over a skill's file judges them"


def _write(root: Path, relative: str, data: bytes = b'') -> None:
    """Write one file under the root, creating its parents.

    Args:
        root: Directory the file is written under, as the repository root.
        relative: Path of the file below `root`, with `/` separators.
        data: Bytes written to the file; empty by default.
    """
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _write_code_corpus(root: Path, guide: bytes) -> None:
    """Write corpus `code`, whose structure specification sets a budget, holding `GUIDE` with the bytes given.

    Args:
        root: Directory the corpus is written under, as the repository root.
        guide: Bytes of `GUIDE`, at `docs/code/guide.md`.
    """
    _write(root, 'docs/__meta__/code.md', b'# Code\n')
    _write(root, 'docs/__meta__/code.spec.json', _budget(1000))
    _write(root, 'docs/code/guide.md', guide)


def _broken_in_skill(path: str, line: int, url: str) -> RuleDiagnostic:
    """The `LINK003` diagnostic of a link in a file of `REVIEW`, read from the skill root.

    The link names its target by a normalised path, so the target is that path under the skill root.

    Args:
        path: Where an agent reaches the file holding the link, root-relative.
        line: The line the link is on.
        url: The link's destination, as the parser encodes it.
    """
    occurrence = BrokenLink(
        line=LineNumber(NonZeroUnsignedInt(line)),
        url=url,
        base=SkillRoot(REVIEW.directory),
        target=REVIEW.directory / RootRelativePath.parse(url),
    )
    return RuleDiagnostic(RootRelativePath.parse(path), occurrence, Severity.ERROR)


@pytest.fixture(scope='module')
def broken_link_table() -> RuleTable:
    """The rule table enabling `LINK003` alone, as an error; immutable, so shared by the module."""
    severities: dict[type[Rule], Severity] = {BrokenLink: Severity.ERROR}
    return RuleTable(severities)


@pytest.mark.it
class TestCheckSubjectsBrokenLink:
    def test_check_subjects_with_a_broken_link_in_a_skill_file_reports_only_it(
        self, tmp_path: Path, broken_link_table: RuleTable
    ) -> None:
        #: Given
        _write(
            tmp_path,
            '.agents/skills/review/SKILL.md',
            REVIEW_FRONTMATTER + b'# Review\n\nRun [the script](scripts/run.py) from [scripts](scripts/).\n\n'
            b'Read [the steps](references/steps.md).\n',
        )
        _write(tmp_path, '.agents/skills/review/scripts/run.py')
        database = Database.from_snapshot(take_snapshot(tmp_path, SNAPSHOT_SCOPE), builtin_layers=(SKILLS_LAYER,))
        subjects = (_item(database, _location(database, REVIEW)),)

        #: When
        reports = check_subjects(database, subjects, broken_link_table, {})

        #: Then
        assert reports == (
            CheckedItem(
                ItemRef(REVIEW.path),
                diagnostics=(_broken_in_skill('.agents/skills/review/SKILL.md', 9, 'references/steps.md'),),
            ),
        ), 'a file and a directory the skill holds are found, whatever their kind, and the missing file is not'

    def test_check_subjects_with_a_broken_link_in_a_nested_resource_reads_it_from_the_skill_root(
        self, tmp_path: Path, broken_link_table: RuleTable
    ) -> None:
        #: Given
        _write(tmp_path, '.agents/skills/review/SKILL.md', REVIEW_FRONTMATTER)
        _write(tmp_path, '.agents/skills/review/references/a.md', b'# A\n')
        _write(
            tmp_path,
            '.agents/skills/review/references/deep/guide.md',
            b'# Guide\n\nSee [a](references/a.md), not [a](a.md) or [itself](guide.md).\n',
        )
        database = Database.from_snapshot(take_snapshot(tmp_path, SNAPSHOT_SCOPE), builtin_layers=(SKILLS_LAYER,))
        resources = _resources(database, REVIEW)

        #: When
        reports = check_subjects(
            database, tuple(_item(database, resource) for resource in resources), broken_link_table, {}
        )

        #: Then
        guide = '.agents/skills/review/references/deep/guide.md'
        assert reports == (
            CheckedItem(ItemRef(resources[0].ref.path), diagnostics=()),
            CheckedItem(
                ItemRef(resources[1].ref.path),
                diagnostics=(_broken_in_skill(guide, 3, 'a.md'), _broken_in_skill(guide, 3, 'guide.md')),
            ),
        ), 'a link in a resource is read from the skill root, not from the resource, so only the first is found'

    def test_check_subjects_with_a_link_through_a_symlinked_directory_in_the_skill_follows_it(
        self, tmp_path: Path, broken_link_table: RuleTable
    ) -> None:
        #: Given
        _write(
            tmp_path,
            '.agents/skills/review/SKILL.md',
            REVIEW_FRONTMATTER + b'# Review\n\nSee [d](guides/d.md) and [e](guides/e.md).\n',
        )
        _write(tmp_path, 'shared/guides/d.md', b'# D\n')
        (tmp_path / '.agents' / 'skills' / 'review' / 'guides').symlink_to('../../../shared/guides')
        database = Database.from_snapshot(take_snapshot(tmp_path, SNAPSHOT_SCOPE), builtin_layers=(SKILLS_LAYER,))
        subjects = (_item(database, _location(database, REVIEW)),)

        #: When
        reports = check_subjects(database, subjects, broken_link_table, {})

        #: Then
        assert reports == (
            CheckedItem(
                ItemRef(REVIEW.path),
                diagnostics=(_broken_in_skill('.agents/skills/review/SKILL.md', 7, 'guides/e.md'),),
            ),
        ), 'the symlink inside the skill is followed to the files it leads to, and a file it lacks is missing'

    def test_check_subjects_with_a_broken_link_in_a_linked_skill_reports_it_where_the_agent_finds_it(
        self, tmp_path: Path, broken_link_table: RuleTable
    ) -> None:
        #: Given
        _write(
            tmp_path,
            'skills/review/SKILL.md',
            REVIEW_FRONTMATTER + b'# Review\n\nSee [a](references/a.md) and [b](references/b.md).\n',
        )
        _write(tmp_path, 'skills/review/references/a.md', b'# A\n\nBack to [the skill](SKILL.md), on to [c](c.md).\n')
        (tmp_path / '.agents' / 'skills').mkdir(parents=True)
        (tmp_path / '.agents' / 'skills' / 'review').symlink_to('../../skills/review')
        database = Database.from_snapshot(take_snapshot(tmp_path, SNAPSHOT_SCOPE), builtin_layers=(SKILLS_LAYER,))
        resources = _resources(database, REVIEW)
        subjects = (_item(database, _location(database, REVIEW)), *(_item(database, item) for item in resources))

        #: When
        reports = check_subjects(database, subjects, broken_link_table, {})

        #: Then
        assert reports == (
            CheckedItem(
                ItemRef(REVIEW.path),
                diagnostics=(_broken_in_skill('.agents/skills/review/SKILL.md', 7, 'references/b.md'),),
            ),
            CheckedItem(
                ItemRef(resources[0].ref.path),
                diagnostics=(_broken_in_skill('.agents/skills/review/references/a.md', 3, 'c.md'),),
            ),
        ), 'each diagnostic names its file where an agent reaches it, under the skills directory, not under skills/'

    def test_check_subjects_with_links_escaping_the_skill_root_never_reports_them_broken(
        self, tmp_path: Path, broken_link_table: RuleTable
    ) -> None:
        #: Given
        _write(
            tmp_path,
            '.agents/skills/review/SKILL.md',
            REVIEW_FRONTMATTER + b'# Review\n\nSee [back in](../review/references/a.md) and [out](../gone.md).\n',
        )
        _write(tmp_path, '.agents/skills/review/references/a.md', b'# A\n')
        database = Database.from_snapshot(take_snapshot(tmp_path, SNAPSHOT_SCOPE), builtin_layers=(SKILLS_LAYER,))
        subjects = (_item(database, _location(database, REVIEW)),)

        #: When
        reports = check_subjects(database, subjects, broken_link_table, {})

        #: Then
        assert reports == (CheckedItem(ItemRef(REVIEW.path), diagnostics=()),), (
            'a link above the skill root is not judged as broken, whether a file lies where it leads or not'
        )

    def test_check_subjects_with_a_broken_sibling_link_in_a_document_reports_it(
        self, tmp_path: Path, broken_link_table: RuleTable
    ) -> None:
        #: Given
        _write_code_corpus(tmp_path, b'# Guide\n\nRead [the setup](setup.md) first.\n')
        database = Database.from_snapshot(take_snapshot(tmp_path, SNAPSHOT_SCOPE), builtin_layers=(SKILLS_LAYER,))

        #: When
        reports = check_subjects(database, (GUIDE,), broken_link_table, {})

        #: Then
        occurrence = BrokenLink(
            line=LineNumber(NonZeroUnsignedInt(3)),
            url='setup.md',
            base=DocumentDirectory(RootRelativePath.parse('docs/code')),
            target=RootRelativePath.parse('docs/code/setup.md'),
        )
        assert reports == (
            CheckedItem(
                ItemRef(GUIDE.path),
                diagnostics=(RuleDiagnostic(GUIDE.path, occurrence, Severity.ERROR),),
                ungoverned=(),
            ),
        ), "a link in a document is read from the document's own directory, where nothing is named setup.md"

    def test_check_subjects_with_links_to_a_file_and_a_directory_present_reports_the_document_clean(
        self, tmp_path: Path, broken_link_table: RuleTable
    ) -> None:
        #: Given
        _write_code_corpus(tmp_path, b'# Guide\n\nRead [the setup](setup.md), then [the specs](../__meta__/).\n')
        _write(tmp_path, 'docs/code/setup.md', b'# Setup\n')
        database = Database.from_snapshot(take_snapshot(tmp_path, SNAPSHOT_SCOPE), builtin_layers=(SKILLS_LAYER,))

        #: When
        reports = check_subjects(database, (GUIDE,), broken_link_table, {})

        #: Then
        assert reports == (CheckedItem(ItemRef(GUIDE.path), diagnostics=(), ungoverned=()),), (
            "a sibling file and a directory reached by climbing out of the document's directory are both found"
        )

    def test_check_subjects_with_a_link_outside_the_scope_never_judges_it(
        self, tmp_path: Path, broken_link_table: RuleTable
    ) -> None:
        #: Given
        # `src/` is not read by the scan, so whether `src/main.py` exists cannot be told from the snapshot.
        _write_code_corpus(tmp_path, b'# Guide\n\nSee [the entry point](../../src/main.py).\n')
        database = Database.from_snapshot(take_snapshot(tmp_path, SNAPSHOT_SCOPE), builtin_layers=(SKILLS_LAYER,))

        #: When
        reports = check_subjects(database, (GUIDE,), broken_link_table, {})

        #: Then
        assert reports == (CheckedItem(ItemRef(GUIDE.path), diagnostics=(), ungoverned=()),), (
            'a link into a directory the scan never read is not judged'
        )

    def test_check_subjects_with_a_link_climbing_above_the_repository_never_judges_it(
        self, tmp_path: Path, broken_link_table: RuleTable
    ) -> None:
        #: Given
        _write_code_corpus(tmp_path, b'# Guide\n\nSee [elsewhere](../../../elsewhere.md).\n')
        database = Database.from_snapshot(take_snapshot(tmp_path, SNAPSHOT_SCOPE), builtin_layers=(SKILLS_LAYER,))

        #: When
        reports = check_subjects(database, (GUIDE,), broken_link_table, {})

        #: Then
        assert reports == (CheckedItem(ItemRef(GUIDE.path), diagnostics=(), ungoverned=()),), (
            'a link climbing above the repository root names nothing the snapshot can hold, so it is not judged'
        )
