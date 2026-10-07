"""`FM011`: a skill's `allowed-tools` is not a list of tool entries."""

from dataclasses import dataclass
from typing import ClassVar, Self, assert_never

from lorecraft.project.context import SkillContext
from lorecraft.project.schemas import field_line
from lorecraft.project.syntax import Frontmatter, InvalidYamlFrontmatter, MissingFrontmatter, NonMappingFrontmatter
from lorecraft.rules.declaration import Level, Release, RuleCode, RuleName, rule
from lorecraft.rules.location import Help, Here, Label, Subdiagnostic
from lorecraft.rules.subject import SkillRule

from .__ruleset__ import GROUP_ID, allowed_tools_note


@dataclass(frozen=True, slots=True)
class EmptyValue:
    """The field is written, but holds no tool entry at all."""


@dataclass(frozen=True, slots=True)
class CommaSeparated:
    """An entry separates tools with a comma, where the specification separates them with whitespace.

    Attributes:
        entry: The entry, exactly as read from the field.
        suggested: The entry with the commas that separate tools turned to spaces; a comma inside parentheses
            belongs to a pattern and is kept. It is never empty.
    """

    entry: str
    suggested: str


@dataclass(frozen=True, slots=True)
class UnbalancedParentheses:
    """An entry opens a parenthesised pattern it does not close, or closes one it did not open.

    Attributes:
        entry: The entry, exactly as read from the field.
    """

    entry: str


@dataclass(frozen=True, slots=True)
class NotATool:
    """An entry is neither a tool name nor a tool name followed by one balanced parenthesised pattern.

    Attributes:
        entry: The entry, exactly as read from the field.
    """

    entry: str


type MalformedEntry = CommaSeparated | UnbalancedParentheses | NotATool
"""What is wrong with one entry of the field; the empty value has no entry."""

type MalformedAllowedToolsProblem = EmptyValue | MalformedEntry
"""What is wrong with the field's value: it holds no entry, or one of its entries is malformed."""


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class MalformedAllowedTools(SkillRule):
    """A skill's `allowed-tools` is not a list of tool entries.

    ## What it does

    Checks for skills whose `allowed-tools` entries do not match the list structure adopted for the Agent Skills
    specification's experimental field: a tool name of ASCII letters, digits, underscores or hyphens, optionally
    followed by one balanced parenthesised pattern. Spaces and commas inside that pattern belong to it. Whether a
    particular agent recognises a tool or its pattern syntax is not checked.

    ## Why is this bad?

    A malformed entry may be read as a different set of pre-approved tools than the skill author intended.

    ## Example

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
        """Point at the specification and give the correction for this entry."""
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
        return (allowed_tools_note(), Help(fix))

    @classmethod
    def check(cls, subject: SkillContext) -> tuple[Self, ...]:
        """Report malformed entries at the `allowed-tools` field's line.

        Args:
            subject: The skill whose frontmatter is judged.
        """
        frontmatter = subject.frontmatter()
        match frontmatter:
            case Frontmatter():
                pass
            case MissingFrontmatter() | InvalidYamlFrontmatter() | NonMappingFrontmatter():
                return ()
            case _:
                assert_never(frontmatter)

        value = frontmatter.data.get('allowed-tools')
        if not isinstance(value, str):
            return ()

        line = field_line(frontmatter, 'allowed-tools')
        entries = _split_entries(value)
        if not entries:
            return (cls(line=line, problem=EmptyValue()),)

        occurrences: list[Self] = []
        for entry in entries:
            problem = _problem(entry)
            if problem is not None:
                occurrences.append(cls(line=line, problem=problem))
        return tuple(occurrences)


def _split_entries(value: str) -> tuple[str, ...]:
    """Split at whitespace outside balanced parentheses, keeping each entry's spelling."""
    entries: list[str] = []
    start: int | None = None
    depth = 0

    for position, character in enumerate(value):
        if character.isspace() and depth == 0:
            if start is not None:
                entries.append(value[start:position])
                start = None
            continue
        if start is None:
            start = position
        if character == '(':
            depth += 1
        elif character == ')' and depth > 0:
            depth -= 1

    if start is not None:
        entries.append(value[start:])
    return tuple(entries)


def _problem(entry: str) -> MalformedEntry | None:
    """Return the kind of malformed entry, or `None` when it has the allowed shape.

    Args:
        entry: One entry of the field, which holds at least one character: whitespace separates entries.
    """
    if ',' in entry and '(' not in entry:
        return _comma_separated_or_not_a_tool(entry)

    name_end = 0
    for character in entry:
        if character.isascii() and (character.isalpha() or character.isdigit() or character in '_-'):
            name_end += 1
        else:
            break
    if name_end == 0:
        if entry.count('(') != entry.count(')'):
            return UnbalancedParentheses(entry)
        return _comma_separated_or_not_a_tool(entry)
    if name_end == len(entry):
        return None
    if entry[name_end] == ')':
        return UnbalancedParentheses(entry)
    if entry[name_end] != '(':
        return _comma_separated_or_not_a_tool(entry)

    depth = 0
    close_position: int | None = None
    for position in range(name_end, len(entry)):
        character = entry[position]
        if character == '(':
            depth += 1
        elif character == ')':
            depth -= 1
            if depth == 0:
                close_position = position
                break
    if depth != 0 or close_position is None:
        return UnbalancedParentheses(entry)
    if close_position != len(entry) - 1:
        suffix = entry[close_position + 1 :]
        if suffix.count('(') != suffix.count(')'):
            return UnbalancedParentheses(entry)
        # A balanced suffix may still hold a comma between tools, as in `Bash(git diff),Read`.
        return _comma_separated_or_not_a_tool(entry)
    return None


def _comma_separated_or_not_a_tool(entry: str) -> CommaSeparated | NotATool:
    """The problem of an entry that fits no shape: commas between tools when it holds any, else no tool at all.

    Only a comma outside parentheses separates tools, so an entry whose commas are all inside parentheses has no
    correction to suggest.

    Args:
        entry: An entry that is not a tool name, optionally followed by one balanced parenthesised pattern.
    """
    suggested = _separate_with_spaces(entry)
    if suggested and suggested != entry:
        return CommaSeparated(entry, suggested)
    return NotATool(entry)


def _separate_with_spaces(entry: str) -> str:
    """The entry with every comma outside parentheses turned to a space, and no space left at either end.

    A comma inside parentheses belongs to a pattern, so it is kept.

    Args:
        entry: The entry whose commas separate tools.
    """
    separated: list[str] = []
    depth = 0
    for character in entry:
        if character == '(':
            depth += 1
        elif character == ')' and depth > 0:
            depth -= 1
        if character == ',' and depth == 0:
            separated.append(' ')
        else:
            separated.append(character)
    return ''.join(separated).strip()
