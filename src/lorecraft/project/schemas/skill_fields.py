"""What each field of a skill's frontmatter holds once it is parsed, keyed by the field it was read from.

`SkillFrontmatterSchema` says what is wrong with a frontmatter; this module says what is right with it. Each field
is parsed on its own, so a field that conforms is available even when another one is rejected: a rule over the
`allowed-tools` field has no reason to go silent because the `name` is misspelt. A field that is not written, is
null, is not of the type the specification asks for, or is rejected by its value object, has no entry.

The `allowed-tools` text is split into the entries it lists, each one a well-formed `AllowedTool` or a
`MalformedEntry` saying what is wrong with it, so a rule reads what the field holds instead of the raw text.
"""

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from lorecraft.core.error import Error
from lorecraft.core.mapping import Frozen, FrozenMapping
from lorecraft.project.syntax import Frontmatter, FrontmatterNode

from .skill_frontmatter import SkillCompatibility, SkillDescription, SkillLicense, SkillName


class SkillField(StrEnum):
    """The fields of a skill's frontmatter, valued by the key each is written under."""

    NAME = 'name'
    DESCRIPTION = 'description'
    LICENSE = 'license'
    COMPATIBILITY = 'compatibility'
    METADATA = 'metadata'
    ALLOWED_TOOLS = 'allowed-tools'


@dataclass(frozen=True, slots=True)
class AllowedTool:
    """One entry of `allowed-tools` that is a tool name, optionally followed by one balanced parenthesised pattern.

    Attributes:
        entry: The entry, exactly as read from the field.
    """

    entry: str


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
"""What is wrong with one entry of the field."""


@dataclass(frozen=True, slots=True)
class AllowedTools:
    """The `allowed-tools` text, split into the entries it lists.

    Attributes:
        text: The whole value, exactly as written.
        entries: The entries in the order written; empty when the value holds none, such as an all-whitespace one.
    """

    text: str
    entries: tuple[AllowedTool | MalformedEntry, ...]


type SkillFieldValue = (
    SkillName | SkillDescription | SkillLicense | SkillCompatibility | FrozenMapping[str, str] | AllowedTools
)
"""What one field holds once parsed; each field has its own type."""

type SkillFields = FrozenMapping[SkillField, SkillFieldValue]
"""The fields of one frontmatter that parsed, by the field; one that is absent or rejected has no entry."""


def parse_skill_fields(frontmatter: FrontmatterNode) -> SkillFields:
    """The fields of a skill's frontmatter that parse, each on its own. Raises nothing.

    Args:
        frontmatter: The frontmatter of the skill's `SKILL.md`, as parsed; a block that is missing, not YAML or not a
            mapping holds no field.
    """
    if not isinstance(frontmatter, Frontmatter):
        return FrozenMapping({})
    data = frontmatter.data
    fields: dict[SkillField, SkillFieldValue] = {}

    name = data.get(SkillField.NAME)
    if isinstance(name, str):
        _keep(fields, SkillField.NAME, SkillName.parse, name)
    description = data.get(SkillField.DESCRIPTION)
    if isinstance(description, str):
        _keep(fields, SkillField.DESCRIPTION, SkillDescription.parse, description)
    license_text = data.get(SkillField.LICENSE)
    if isinstance(license_text, str):
        fields[SkillField.LICENSE] = SkillLicense.parse(license_text)
    compatibility = data.get(SkillField.COMPATIBILITY)
    if isinstance(compatibility, str):
        _keep(fields, SkillField.COMPATIBILITY, SkillCompatibility.parse, compatibility)
    metadata = _string_mapping(data.get(SkillField.METADATA))
    if metadata is not None:
        fields[SkillField.METADATA] = metadata
    allowed_tools = data.get(SkillField.ALLOWED_TOOLS)
    if isinstance(allowed_tools, str):
        fields[SkillField.ALLOWED_TOOLS] = parse_allowed_tools(allowed_tools)
    return FrozenMapping(fields)


def parse_allowed_tools(text: str) -> AllowedTools:
    """Split an `allowed-tools` value at the whitespace outside balanced parentheses, and judge each entry.

    Args:
        text: The value, as written in the frontmatter.
    """
    entries: list[AllowedTool | MalformedEntry] = []
    for entry in _split_entries(text):
        problem = _problem(entry)
        if problem is None:
            entries.append(AllowedTool(entry))
        else:
            entries.append(problem)
    return AllowedTools(text, tuple(entries))


def _keep(
    fields: dict[SkillField, SkillFieldValue], field: SkillField, parse: Callable[[str], SkillFieldValue], text: str
) -> None:
    """Record the value object `text` parses into, or nothing when its type rejects it."""
    try:
        fields[field] = parse(text)
    except Error:
        return


def _string_mapping(value: Frozen) -> FrozenMapping[str, str] | None:
    """The mapping when every key and value is a string, as the specification asks of `metadata`; else `None`."""
    if not isinstance(value, FrozenMapping):
        return None
    strings: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(item, str):
            return None
        strings[key] = item
    return FrozenMapping(strings)


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
