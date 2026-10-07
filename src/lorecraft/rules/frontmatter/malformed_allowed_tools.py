"""`FM011`: a skill's `allowed-tools` is not a list of tool entries."""

from dataclasses import dataclass
from enum import Enum
from typing import ClassVar, Self, assert_never

from lorecraft.project.context import SkillContext
from lorecraft.project.schemas import field_line
from lorecraft.project.syntax import Frontmatter, InvalidYamlFrontmatter, MissingFrontmatter, NonMappingFrontmatter
from lorecraft.rules.declaration import Level, Release, RuleCode, RuleName, rule
from lorecraft.rules.location import Help, Note, Subdiagnostic
from lorecraft.rules.subject import SkillRule

from .__ruleset__ import GROUP_ID


class MalformedAllowedToolsProblem(Enum):
    """The structural reason an allowed-tools entry is malformed."""

    EMPTY = 'empty'
    COMMA = 'comma'
    PARENTHESES = 'parentheses'
    ENTRY = 'entry'


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
        entry: The malformed entry, exactly as read from the field.
        problem: The structural reason the entry does not parse.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 11)
    NAME: ClassVar[RuleName] = RuleName('malformed-allowed-tools')
    LEVEL: ClassVar[Level] = Level.WARN
    SINCE: ClassVar[Release] = Release('0.3.0')

    spec: None = None
    entry: str
    problem: MalformedAllowedToolsProblem

    def message(self) -> str:
        """Name the malformed entry."""
        return f'malformed `allowed-tools` entry {self.entry!r}'

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Point at the specification and give the correction for this entry."""
        match self.problem:
            case MalformedAllowedToolsProblem.EMPTY:
                fix = 'write one or more tool names separated by spaces'
            case MalformedAllowedToolsProblem.COMMA:
                fix = 'separate tools with spaces, not commas'
            case MalformedAllowedToolsProblem.PARENTHESES:
                fix = 'balance the parentheses around the pattern'
            case MalformedAllowedToolsProblem.ENTRY:
                fix = 'write the entry as `Tool` or `Tool(pattern)`'
        return (
            Note(
                "the Agent Skills specification's experimental `allowed-tools` field: "
                'https://agentskills.io/specification#allowed-tools-field'
            ),
            Help(fix),
        )

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
            return (cls(line=line, entry='', problem=MalformedAllowedToolsProblem.EMPTY),)

        occurrences: list[Self] = []
        for entry in entries:
            problem = _problem(entry)
            if problem is not None:
                occurrences.append(cls(line=line, entry=entry, problem=problem))
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


def _problem(entry: str) -> MalformedAllowedToolsProblem | None:
    """Return the kind of malformed entry, or `None` when it has the allowed shape."""
    if not entry:
        return MalformedAllowedToolsProblem.EMPTY
    if ',' in entry and '(' not in entry:
        return MalformedAllowedToolsProblem.COMMA

    name_end = 0
    for character in entry:
        if character.isascii() and (character.isalpha() or character.isdigit() or character in '_-'):
            name_end += 1
        else:
            break
    if name_end == 0:
        if entry.count('(') != entry.count(')'):
            return MalformedAllowedToolsProblem.PARENTHESES
        return MalformedAllowedToolsProblem.COMMA if ',' in entry else MalformedAllowedToolsProblem.ENTRY
    if name_end == len(entry):
        return None
    if entry[name_end] == ')':
        return MalformedAllowedToolsProblem.PARENTHESES
    if entry[name_end] != '(':
        return MalformedAllowedToolsProblem.COMMA if ',' in entry else MalformedAllowedToolsProblem.ENTRY

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
        return MalformedAllowedToolsProblem.PARENTHESES
    if close_position != len(entry) - 1:
        suffix = entry[close_position + 1 :]
        if suffix.count('(') != suffix.count(')'):
            return MalformedAllowedToolsProblem.PARENTHESES
        return MalformedAllowedToolsProblem.ENTRY
    return None
