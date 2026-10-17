"""`FM011`: a skill's `allowed-tools` is not a list of tool entries."""

from dataclasses import dataclass
from typing import ClassVar, Self, assert_never

from lorecraft.project.query import Query
from lorecraft.project.schemas import AllowedTool, CommaSeparated, MalformedEntry, NotATool, UnbalancedParentheses
from lorecraft.rules.collector import rule
from lorecraft.rules.identity import Level, Release, RuleCode, RuleName
from lorecraft.rules.location import Help, Here, Label, Subdiagnostic
from lorecraft.rules.subject import QueriedSkillRule

from .__ruleset__ import ALLOWED_TOOLS_NOTE, GROUP_ID, AllowedToolsField, allowed_tools_field


@dataclass(frozen=True, slots=True)
class EmptyValue:
    """The field is written, but holds no tool entry at all."""


type MalformedAllowedToolsProblem = EmptyValue | MalformedEntry
"""What is wrong with the field's value: it holds no entry, or one of its entries is malformed."""


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class MalformedAllowedTools(QueriedSkillRule[AllowedToolsField | None]):
    """A skill's `allowed-tools` is not a list of tool entries.

    ## What it does

    Checks for skills whose `allowed-tools` entries do not match the list structure adopted for the Agent Skills
    specification's experimental field: a tool name of ASCII letters, digits, underscores or hyphens, optionally
    followed by one balanced parenthesised pattern. Spaces and commas inside that pattern belong to it. Whether a
    particular agent recognises a tool or its pattern syntax is not checked.

    ## Why is this bad?

    A malformed entry may be read as a different set of pre-approved tools than the skill author intended.

    ## Example

    `.agents/skills/review/SKILL.md`:

    ```markdown
    ---
    name: review
    description: Review a change.
    allowed-tools: Read, Grep
    ---
    ```

    ## Use instead

    Separate entries with whitespace:

    ```markdown
    ---
    name: review
    description: Review a change.
    allowed-tools: Read Grep
    ---
    ```

    Attributes:
        spec: Always `None`: the package states this rule, after the Agent Skills specification.
        problem: What is wrong with the value: it holds no entry, or one entry is malformed in the way it states,
            with the entry exactly as read from the field.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 11)
    NAME: ClassVar[RuleName] = RuleName('malformed-allowed-tools')
    LEVEL: ClassVar[Level] = Level.WARN
    SINCE: ClassVar[Release] = Release('0.3.0')

    spec: None = None
    problem: MalformedAllowedToolsProblem

    def message(self) -> str:
        """Say the field is not a list of tool entries; the label names the entry."""
        return '`allowed-tools` is not a list of tool entries'

    def labels(self) -> tuple[Label, ...]:
        """Name the entry, or say the field holds none, on the field's line."""
        problem = self.problem
        match problem:
            case EmptyValue():
                return (Label(Here(self.line), 'no tool is written here'),)
            case CommaSeparated() | UnbalancedParentheses() | NotATool():
                return (Label(Here(self.line), f'`{problem.entry}` is not `Tool` or `Tool(pattern)`'),)
            case _:
                assert_never(problem)

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Point at the meta spec and give the correction for this entry."""
        problem = self.problem
        match problem:
            case EmptyValue():
                fix = 'write one or more tool names separated by spaces, or remove `allowed-tools`'
            case CommaSeparated():
                fix = f'write `{problem.suggested}`'
            case UnbalancedParentheses():
                fix = 'balance the parentheses around the pattern'
            case NotATool():
                fix = 'write the entry as `Tool` or `Tool(pattern)`'
            case _:
                assert_never(problem)
        return (ALLOWED_TOOLS_NOTE, Help(fix))

    @classmethod
    def query(cls) -> Query[AllowedToolsField | None]:
        """The `allowed-tools` field and its line."""
        return allowed_tools_field

    @classmethod
    def judge(cls, facts: AllowedToolsField | None, /) -> tuple[Self, ...]:
        """Report malformed entries at the `allowed-tools` field's line.

        Args:
            facts: The field as written; `None` when the skill writes none.
        """
        if facts is None:
            return ()
        line = facts.line
        if not facts.tools.entries:
            return (cls(line=line, problem=EmptyValue()),)

        occurrences: list[Self] = []
        for entry in facts.tools.entries:
            match entry:
                case AllowedTool():
                    pass
                case CommaSeparated() | UnbalancedParentheses() | NotATool():
                    occurrences.append(cls(line=line, problem=entry))
                case _:
                    assert_never(entry)
        return tuple(occurrences)
