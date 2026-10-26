"""`LEN002`: an item is longer than its line budget allows."""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import ClassVar, Protocol, Self

from lorecraft.core.num import NonZeroUnsignedInt, UnsignedInt
from lorecraft.core.path import RootRelativePath
from lorecraft.project.item import ItemType, SpecPart
from lorecraft.project.query import GovernancePrimitives, ItemQuery, item_line_count, item_structure_sources
from lorecraft.project.schemas.structure import BuiltinLineBudget, StructureSpec
from lorecraft.project.syntax import LineCount, LineNumber
from lorecraft.rules.collector import rule
from lorecraft.rules.identity import Level, Release, RuleCode, RuleName
from lorecraft.rules.length.__ruleset__ import GROUP_ID, spec_note
from lorecraft.rules.location import Help, Here, Label, Note, Subdiagnostic
from lorecraft.rules.overrun import Overrun, find_overrun
from lorecraft.rules.subject import Gate, QueriedItemRule, WhenSpec
from lorecraft.schemas import BuiltinOrigin


@dataclass(frozen=True, slots=True)
class LineBudget:
    """A line limit set by a governing structure specification."""

    spec: RootRelativePath | BuiltinOrigin
    lines: NonZeroUnsignedInt


@dataclass(frozen=True, slots=True)
class LineFacts:
    """The file's line count and each line limit that governs it."""

    count: LineCount
    budgets: tuple[LineBudget, ...]


class _LinePrimitives(GovernancePrimitives, Protocol):
    """Primitives needed to derive a line count and its governing limits."""


def line_facts(primitives: _LinePrimitives) -> LineFacts:
    """Read structure line budgets, counting only when a limit applies."""
    budgets: list[LineBudget] = []
    for source, structure in primitives.query(item_structure_sources):
        match structure:
            case BuiltinLineBudget(lines=lines):
                budgets.append(LineBudget(source, lines))
            case StructureSpec(lines=lines) if lines is not None:
                budgets.append(LineBudget(source, lines))
            case StructureSpec():
                pass
    count = primitives.query(item_line_count) if budgets else LineCount(UnsignedInt(0))
    return LineFacts(count, tuple(budgets))


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class TooManyLines(QueriedItemRule[LineFacts]):
    """An item is longer than a governing line budget.

    ## What it does

    Checks each `lines` budget set by the item's governing structure files. A document or spec with no line
    budget is not counted. The builtin Agent Skills structure layer sets skills' default limit to 500 lines.

    The whole file counts: frontmatter, blank lines and code as much as prose. A file exactly at its budget fits;
    the first line after it is reported.

    ## Why is this bad?

    An agent loads the whole file, so every line uses context whether or not the current task needs it.

    ## Use instead

    Split material into a linked document, or into a skill resource under `references/` for skills.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 2)
    NAME: ClassVar[RuleName] = RuleName('too-many-lines')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('0.3.0')
    APPLIES_TO: ClassVar[Mapping[ItemType, Gate]] = MappingProxyType(
        {
            ItemType.DOCUMENT: WhenSpec(SpecPart.BUDGET),
            ItemType.SPEC: WhenSpec(SpecPart.BUDGET),
            ItemType.SKILL_ENTRYPOINT: WhenSpec(SpecPart.BUDGET),
        }
    )

    spec: RootRelativePath | None = None
    overrun: Overrun

    def message(self) -> str:
        """Name the line count and the budget it exceeds."""
        return f'too many lines ({self.overrun.count} > {self.overrun.cap})'

    def labels(self) -> tuple[Label, ...]:
        """Mark the first line past the budget and the number of excess lines."""
        return (
            Label(
                Here(self.line),
                f'the budget ends before this line; lines past it: {self.overrun.excess}',
            ),
        )

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Point to the governing specification or explain the default skill limit."""
        if self.spec is None:
            return (
                Note(f'the Agent Skills specification keeps a SKILL.md to at most {self.overrun.cap} lines'),
                Help(
                    'move what most activations do not need into files under references/, and say in SKILL.md when '
                    'to read each'
                ),
            )
        return (
            spec_note(self.spec),
            Help('split the file or move material into a document of its own and link to it'),
        )

    @classmethod
    def query(cls) -> ItemQuery[LineFacts]:
        """The line limits that apply to the item and its whole-file line count."""
        return line_facts

    @classmethod
    def judge(cls, facts: LineFacts, /) -> tuple[Self, ...]:
        """One occurrence for each line budget the item exceeds."""
        occurrences: list[Self] = []
        for budget in facts.budgets:
            overrun = find_overrun(facts.count, budget.lines)
            if overrun is not None:
                occurrences.append(
                    cls(
                        spec=budget.spec if isinstance(budget.spec, RootRelativePath) else None,
                        line=LineNumber(budget.lines.successor()),
                        overrun=overrun,
                    )
                )
        return tuple(occurrences)
