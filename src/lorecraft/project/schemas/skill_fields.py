"""The entries an `allowed-tools` value lists, each judged on its own.

The text is split at the whitespace outside balanced parentheses into the entries it lists, each one a well-formed
``AllowedTool`` or a ``MalformedEntry`` saying what is wrong with it, so a rule reads what the field holds instead of
splitting the raw text.
"""

from dataclasses import dataclass


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
