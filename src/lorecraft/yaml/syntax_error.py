"""What is wrong with a YAML text that does not parse, as a kind a caller words.

The YAML parser fails with an error that names its own internals: `<block end>`, `simple key`, a tuple of tokens.
adr-019 states the kinds of syntax error a writer meets, and this module classifies the parser's error into one of
them, as a value that carries the facts of the kind: the line the writer fixes and the text the error names. It
reads what the error carries, the problem and the context it names and its two marks, and the text's own lines at
them; no parser text reaches the result, and the package above words each kind.

An error no kind matches is `UnreadableBlock`, on the line the parser marked, so a parser upgrade that rewords an
error moves it there rather than to a wrong kind.
"""

import ast
import logging
import re
import string
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from lorecraft.core.lines import split_lines
from lorecraft.core.num import UnsignedInt

from .position import LINE_SEPARATORS
from .tree import YamlPosition

logger = logging.getLogger(__name__)

_ESCAPE_HEX_DIGITS: Final[Mapping[str, int]] = MappingProxyType({'x': 2, 'u': 4, 'U': 8})
"""How many hexadecimal digits the escapes `\\x`, `\\u` and `\\U` take after their letter."""

_PROBLEM_TEMPLATES: Final[tuple[str, ...]] = (
    'expected chomping or indentation indicators',
    'expected a comment or a line break',
    'expected <block end>',
    'expected the node content',
    'expected <document start>',
    'expected alphabetic or numeric character',
    'did not find expected',
    'could not find expected',
    'found undefined',
    'found character',
    'found unexpected',
    'found duplicate',
    'found invalid',
    'found unknown',
    'found a tab character',
    'while parsing',
    'mapping values are not allowed here',
    'mapping keys are not allowed here',
    'sequence entries are not allowed here',
)
"""The parser's problem templates that can be logged: each stops before the first character it quotes of the text."""

_BLOCK_SCALAR_HEADER: Final[re.Pattern[str]] = re.compile(r'(?:^|\s)[|>][+-]?[0-9]?\s*(?:#.*)?$')
"""The end of a line that opens a literal or folded block scalar, with its indicators and a comment after them."""


@dataclass(frozen=True, slots=True)
class _Mark:
    """Where the parser marked an error, counted from 0 as the classification below reads it.

    Attributes:
        line: The line of the block.
        column: The column of the line, in characters.
    """

    line: int
    column: int


def _mark_of(position: YamlPosition | None) -> _Mark | None:
    """The mark of a position, or `None` where the parser gave none.

    Args:
        position: A position of the parser's error, which counts from 1.
    """
    if position is None:
        return None
    return _Mark(position.line.value - 1, position.column.value - 1)


def _check_line(line: int | None) -> None:
    """Refuse a negative line, which no line of the text is.

    Args:
        line: The line a kind carries, counted from 0, or None when the parser marks none.

    Raises:
        NegativeIntError: If the line is below 0.
    """
    if line is not None:
        UnsignedInt(line)


@dataclass(frozen=True, slots=True)
class NotKeyOrItem:
    """A line is neither `key: value` nor `- item`.

    Attributes:
        line: The line the writer fixes, counted from 0, or None when the parser marks none.
    """

    line: int | None

    def __post_init__(self) -> None:
        """Refuse a negative line."""
        _check_line(self.line)


@dataclass(frozen=True, slots=True)
class UnclosedQuote:
    """A quote is never closed.

    Attributes:
        line: The line the quote opens on, counted from 0, or None when the parser marks none.
    """

    line: int | None

    def __post_init__(self) -> None:
        """Refuse a negative line."""
        _check_line(self.line)


@dataclass(frozen=True, slots=True)
class SeparatorEscape:
    """A backslash is written before a line separator, which is no line break to escape.

    Attributes:
        separator: The separator the backslash is written before.
        line: The line, counted from 0, or None when the parser marks none.
    """

    separator: str
    line: int | None

    def __post_init__(self) -> None:
        """Refuse a negative line."""
        _check_line(self.line)


@dataclass(frozen=True, slots=True)
class UnknownEscape:
    """A double-quoted scalar holds an escape it does not know.

    Attributes:
        escape: The escape as written, with the hexadecimal digits the writer gave.
        line: The line, counted from 0.
    """

    escape: str
    line: int

    def __post_init__(self) -> None:
        """Refuse a negative line."""
        _check_line(self.line)


@dataclass(frozen=True, slots=True)
class UnstartableCharacter:
    """A character that cannot start a plain value starts one.

    Attributes:
        character: The character.
        line: The line, counted from 0, or None when the parser marks none.
    """

    character: str
    line: int | None

    def __post_init__(self) -> None:
        """Refuse a negative line."""
        _check_line(self.line)


@dataclass(frozen=True, slots=True)
class ColonInValue:
    """A plain value holds a `: `.

    Attributes:
        key: The key of the line, as written.
        value: What follows the first `: ` of the line, as written.
        line: The line, counted from 0.
    """

    key: str
    value: str
    line: int

    def __post_init__(self) -> None:
        """Refuse a negative line."""
        _check_line(self.line)


@dataclass(frozen=True, slots=True)
class IndentedUnderText:
    """A key is indented under a key whose value is text.

    Attributes:
        key: The indented key, as written.
        parent: The key whose value is text.
        line: The line of the indented key, counted from 0.
    """

    key: str
    parent: str
    line: int

    def __post_init__(self) -> None:
        """Refuse a negative line."""
        _check_line(self.line)


@dataclass(frozen=True, slots=True)
class MatchesNoLevel:
    """A line is indented to no level of the block.

    Attributes:
        line: The line, counted from 0, or None when the parser marks none.
    """

    line: int | None

    def __post_init__(self) -> None:
        """Refuse a negative line."""
        _check_line(self.line)


@dataclass(frozen=True, slots=True)
class ClosesNothing:
    """A closing bracket closes no flow collection.

    Attributes:
        bracket: The `]` or `}` as written.
        line: The line, counted from 0, or None when the parser marks none.
    """

    bracket: str
    line: int | None

    def __post_init__(self) -> None:
        """Refuse a negative line."""
        _check_line(self.line)


@dataclass(frozen=True, slots=True)
class TextAfterQuote:
    """Text follows a closing quote.

    Attributes:
        line: The line, counted from 0.
    """

    line: int

    def __post_init__(self) -> None:
        """Refuse a negative line."""
        _check_line(self.line)


@dataclass(frozen=True, slots=True)
class TextAfterCollection:
    """Text follows a closed flow collection.

    Attributes:
        bracket: The `]` or `}` that closes it.
        line: The line, counted from 0.
    """

    bracket: str
    line: int

    def __post_init__(self) -> None:
        """Refuse a negative line."""
        _check_line(self.line)


@dataclass(frozen=True, slots=True)
class TabIndent:
    """A tab indents a line.

    Attributes:
        line: The line, counted from 0, or None when the parser marks none.
    """

    line: int | None

    def __post_init__(self) -> None:
        """Refuse a negative line."""
        _check_line(self.line)


@dataclass(frozen=True, slots=True)
class TabInLine:
    """A tab is written where it is not whitespace.

    Attributes:
        line: The line, counted from 0, or None when the parser marks none.
    """

    line: int | None

    def __post_init__(self) -> None:
        """Refuse a negative line."""
        _check_line(self.line)


@dataclass(frozen=True, slots=True)
class UnreadableBlock:
    """An error no other kind matches.

    Attributes:
        line: The line the parser marked, counted from 0, or None when it marks none.
    """

    line: int | None

    def __post_init__(self) -> None:
        """Refuse a negative line."""
        _check_line(self.line)


type YamlSyntaxError = (
    NotKeyOrItem
    | UnclosedQuote
    | SeparatorEscape
    | UnknownEscape
    | UnstartableCharacter
    | ColonInValue
    | IndentedUnderText
    | MatchesNoLevel
    | ClosesNothing
    | TextAfterQuote
    | TextAfterCollection
    | TabIndent
    | TabInLine
    | UnreadableBlock
)


@dataclass(frozen=True, slots=True)
class ParserError:
    """What the parser or the scanner reported about a text it could not read, in its own words.

    Attributes:
        problem: What it found wrong, or an empty text when it gave none.
        context: What it was reading, or an empty text when it gave none.
        position: Where it found the problem, or `None` when it gave no mark.
        context_position: Where what it was reading began, or `None` when it gave no mark.
    """

    problem: str
    context: str
    position: YamlPosition | None
    context_position: YamlPosition | None


def classify_syntax_error(error: ParserError, block: str) -> YamlSyntaxError:
    """Classify a scanner's or a parser's error into one of adr-019's syntax error kinds.

    Args:
        error: The scanner's or the parser's error, whose problem, context and positions pick the kind.
        block: The text the parser read.
    """
    kind = _classify(error, block)
    if isinstance(kind, UnreadableBlock):
        logger.debug(
            'yaml syntax error unclassified',
            extra={'fields': {'problem': _template(error.problem), 'line': kind.line}},
        )
    else:
        logger.debug(
            'yaml syntax error classified',
            extra={'fields': {'kind': type(kind).__name__, 'line': getattr(kind, 'line', None)}},
        )
    return kind


def _template(problem: str) -> str:
    """The parser's problem as one of its fixed templates, or a constant for any other text.

    The parser's text echoes the characters it found, quoted in ways no cut can follow, so only a template that is
    known to carry none is logged.

    Args:
        problem: What the parser found wrong.
    """
    for template in _PROBLEM_TEMPLATES:
        if problem.startswith(template):
            return template
    return 'unrecognized'


def _classify(error: ParserError, block: str) -> YamlSyntaxError:
    """The kind of a scanner's or a parser's error, before it is logged.

    Args:
        error: The scanner's or the parser's error.
        block: The text the parser read.
    """
    lines = list(split_lines(block))
    problem = error.problem
    context = error.context
    mark = _mark_of(error.position)
    context_mark = _mark_of(error.context_position)

    if problem == "could not find expected ':'":
        return _not_key_or_item(_line_of(context_mark or mark))
    if context.startswith('while scanning a quoted scalar') and problem.startswith('found unexpected end'):
        return UnclosedQuote(_line_of(context_mark or mark))
    if 'quoted scalar' in context and problem.startswith(('found unknown escape', 'expected escape sequence')):
        separator = _escaped_separator(problem)
        if separator is not None:
            return _separator_escape(separator, mark)
        return _unknown_escape(mark, lines)
    if problem.startswith('found character') and 'cannot start any token' in problem:
        return _unstartable_character(problem, mark, lines)
    if problem == 'mapping values are not allowed here':
        return _misplaced_colon(mark, lines)
    if problem == 'mapping keys are not allowed here':
        return _cannot_start_value('?', mark)
    if problem.startswith(("expected <block end>, but found ']'", "expected <block end>, but found '}'")) or (
        problem.startswith(("expected the node content, but found ']'", "expected the node content, but found '}'"))
    ):
        bracket = ']' if "found ']'" in problem else '}'
        return _closes_nothing(bracket, mark)
    if problem.startswith('expected <block end>, but found') and _ends_a_flow_collection(mark, lines):
        # Whatever the text is, a scalar, a bracket, a comma or a property, it follows a closed flow collection.
        return _text_after_value(mark, lines)
    if problem.startswith(
        (
            "expected <block end>, but found '<block",
            "expected <block end>, but found '-'",
            "expected <block end>, but found '?'",
        )
    ):
        return _bad_indent(mark, lines)
    if problem == 'sequence entries are not allowed here':
        if _ends_a_flow_collection(mark, lines):
            return _text_after_value(mark, lines)
        return _not_key_or_item(_line_of(mark))
    if problem.startswith("expected <block end>, but found '<scalar>'"):
        return _text_after_value(mark, lines)
    if problem.startswith("expected '<document start>'"):
        return _not_key_or_item(_line_of(mark))
    return _unreadable(_line_of(mark or context_mark))


def _line_of(mark: _Mark | None) -> int | None:
    """The line a mark is on, counted from 0, or None when there is no mark.

    Args:
        mark: A mark of the parser's error, which may be absent.
    """
    return None if mark is None else mark.line


def _unreadable(line: int | None) -> UnreadableBlock:
    """The kind for an error no kind of the table matches, reported on the line the parser marked.

    Args:
        line: The line, counted from 0, or None when the parser marks none.
    """
    return UnreadableBlock(line)


def _text(lines: list[str], line: int) -> str:
    """The text of a line of the block, or an empty one when the parser marked none.

    Args:
        lines: The block's lines.
        line: The line, counted from 0.
    """
    return lines[line] if 0 <= line < len(lines) else ''


def _not_key_or_item(line: int | None) -> NotKeyOrItem:
    """The kind for a line that is neither `key: value` nor `- item`.

    Args:
        line: The line, counted from 0, or None when the parser marks none.
    """
    return NotKeyOrItem(line)


def _is_key_line(text: str) -> bool:
    """Whether a line of the block is a `key: value` or a `key:`, which a text value cannot continue on.

    Args:
        text: The line.
    """
    stripped = text.strip()
    return ': ' in stripped or stripped.endswith(':')


def _is_skipped(text: str) -> bool:
    """Whether a walk up the block steps over a line: a blank one, or a comment.

    Args:
        text: The line.
    """
    return not text.strip() or text.strip().startswith('#')


def _is_list_item(text: str) -> bool:
    """Whether a line of the block starts a list item, with a `- `.

    Args:
        text: The line.
    """
    return text.strip().startswith('- ')


def _key_of_line(text: str) -> str:
    """The key a `key: value` line, or a `- key: value` item, starts with.

    Args:
        text: The line.
    """
    item_content = text.strip().removeprefix('- ')
    return item_content.split(': ', 1)[0]


def _indented_under_text(lines: list[str], line: int, key: str) -> IndentedUnderText | None:
    """The kind for a key written indented under a key whose value is text, or None when it is not one.

    The scalar the key's line continues is walked up to the `key: value` line it started on, over the lines of
    plain words between, and that line must be indented less than this one.

    Args:
        lines: The block's lines.
        line: The line that holds the key, counted from 0.
        key: The key as written.
    """
    indent = _indent(_text(lines, line))
    for number in range(line - 1, -1, -1):
        text = lines[number]
        if _is_skipped(text):
            continue
        if not _is_key_line(text):
            continue  # plain words the scalar continues over
        if _indent(text) >= indent:
            return None
        if text.strip().endswith(':'):
            # A `key:` with no value opens a block, so a line under it is a child, not a mistake.
            return None
        parent = _key_of_line(text)
        return IndentedUnderText(key, parent, line)
    return None


def _indent(text: str) -> int:
    """How many spaces start a line.

    Args:
        text: The line.
    """
    return len(text) - len(text.lstrip(' '))


def _bad_indent(mark: _Mark | None, lines: list[str]) -> YamlSyntaxError:
    """Classify a line indented to no level of the block, which may be a key under a text value.

    Args:
        mark: Where the parser found the line's first token.
        lines: The block's lines.
    """
    if mark is not None:
        text = _text(lines, mark.line)
        if _is_key_line(text):
            under_text = _indented_under_text(lines, mark.line, text[mark.column :].split(':', 1)[0].strip())
            if under_text is not None:
                return under_text
    return _matches_no_level(_line_of(mark))


def _matches_no_level(line: int | None) -> MatchesNoLevel:
    """The kind for a line indented to no level of the block.

    Args:
        line: The line, counted from 0, or None when the parser marks none.
    """
    return MatchesNoLevel(line)


def _misplaced_colon(mark: _Mark | None, lines: list[str]) -> YamlSyntaxError:
    """Classify a `:` where a key is not allowed: in a value, under a text value, or ending a multi-line scalar.

    Args:
        mark: Where the scanner found the `:`.
        lines: The block's lines.
    """
    if mark is None:
        return _unreadable(None)
    text = _text(lines, mark.line)
    before = text[: mark.column]
    if before.rstrip().endswith(':'):
        return _cannot_start_value(':', mark)
    if ': ' in before:
        key, _, value = text.strip().partition(': ')
        return ColonInValue(key, value, mark.line)
    under_text = _indented_under_text(lines, mark.line, before.strip())
    if under_text is not None:
        return under_text
    start = _scalar_start(lines, mark.line)
    if _is_list_item(_text(lines, start)):
        # The scalar is the value of a list item, so the key that ends it lines up with no key or item.
        return _matches_no_level(mark.line)
    return _not_key_or_item(start)


def _scalar_start(lines: list[str], line: int) -> int:
    """The line a plain scalar ending at `line` began on: its topmost words, or the list item it is the value of.

    Args:
        lines: The block's lines.
        line: The line the scalar ends on, counted from 0.
    """
    start = line
    for number in range(line - 1, -1, -1):
        text = lines[number]
        if _is_skipped(text):
            continue
        if _is_key_line(text):
            break
        start = number
        if _is_list_item(text):
            break
    return start


def _ends_a_flow_collection(mark: _Mark | None, lines: list[str]) -> bool:
    """Whether the text on the mark's line before the mark ends in a `]` or a `}`.

    Args:
        mark: Where the parser found the text.
        lines: The block's lines.
    """
    if mark is None:
        return False
    return _text(lines, mark.line)[: mark.column].rstrip().endswith((']', '}'))


def _text_after_value(mark: _Mark | None, lines: list[str]) -> YamlSyntaxError:
    """Classify text where an entry ended: after a closing quote, after a flow collection, or below a block scalar.

    Args:
        mark: Where the parser found the text.
        lines: The block's lines.
    """
    if mark is not None:
        before = _text(lines, mark.line)[: mark.column].rstrip()
        if before.endswith(('"', "'")):
            return TextAfterQuote(mark.line)
        if before.endswith((']', '}')):
            return TextAfterCollection(before[-1], mark.line)
        if _below_block_scalar(mark.line, lines):
            return _bad_indent(mark, lines)
    return _unreadable(_line_of(mark))


def _closes_nothing(bracket: str, mark: _Mark | None) -> ClosesNothing:
    """The kind for a closing bracket that closes no flow collection.

    Args:
        bracket: The `]` or `}` as written.
        mark: Where the parser found it.
    """
    return ClosesNothing(bracket, _line_of(mark))


def _below_block_scalar(line: int, lines: list[str]) -> bool:
    """Whether a line is indented less than the text of the block scalar above it, and more than its key.

    Args:
        line: The line, counted from 0.
        lines: The block's lines.
    """
    indent = _indent(_text(lines, line))
    text_indent: int | None = None
    for number in range(line - 1, -1, -1):
        text = lines[number]
        if _is_skipped(text):
            continue
        if _BLOCK_SCALAR_HEADER.search(text):
            return text_indent is not None and _indent(text) < indent < text_indent
        if _indent(text) <= indent:
            return False
        text_indent = _indent(text) if text_indent is None else min(text_indent, _indent(text))
    return False


def _cannot_start_value(character: str, mark: _Mark | None) -> UnstartableCharacter:
    """The kind for a character that cannot start a plain value.

    Args:
        character: The character, shown in the label.
        mark: Where the scanner found it.
    """
    return UnstartableCharacter(character, _line_of(mark))


def _unstartable_character(problem: str, mark: _Mark | None, lines: list[str]) -> YamlSyntaxError:
    """Classify a character that cannot start a token: a tab, or a character no plain value starts with.

    Args:
        problem: The scanner's problem, which names the character between quotes.
        mark: Where the scanner found it.
        lines: The block's lines.
    """
    if "'\\t'" in problem:
        text = _text(lines, mark.line) if mark is not None else ''
        if text.lstrip(' ').startswith('\t'):
            return TabIndent(_line_of(mark))
        return TabInLine(_line_of(mark))
    if "'" not in problem:
        return _unreadable(_line_of(mark))
    return _cannot_start_value(problem.split("'")[1], mark)


def _escaped_separator(problem: str) -> str | None:
    r"""The line separator a scanner's unknown escape problem names, or `None` for any other character.

    Args:
        problem: The scanner's problem, `found unknown escape character '\x85'` for U+0085, whose repr it ends with.
    """
    prefix = 'found unknown escape character '
    if not problem.startswith(prefix):
        return None
    try:
        character = ast.literal_eval(problem[len(prefix) :])
    except ValueError, SyntaxError:
        return None
    return character if isinstance(character, str) and character in LINE_SEPARATORS else None


def _separator_escape(separator: str, mark: _Mark | None) -> SeparatorEscape:
    """The kind for a backslash before a line separator, which is no line break to escape.

    Args:
        separator: The separator the backslash is written before.
        mark: Where the scanner found it.
    """
    return SeparatorEscape(separator, _line_of(mark))


def _unknown_escape(mark: _Mark | None, lines: list[str]) -> YamlSyntaxError:
    """The kind for an escape double quotes do not know, naming the escape as written.

    Args:
        mark: Where the scanner found the bad character of the escape.
        lines: The block's lines.
    """
    if mark is None:
        return _unreadable(None)
    text = _text(lines, mark.line)
    start = text.rfind('\\', 0, mark.column + 1)
    if start == -1:
        return _unreadable(mark.line)
    letter = text[start + 1 : start + 2]
    escape_end = start + 2
    for _ in range(_ESCAPE_HEX_DIGITS.get(letter, 0)):
        # The digits the writer gave: a closing quote or any other character is not part of the escape.
        if escape_end >= len(text) or text[escape_end] not in string.hexdigits:
            break
        escape_end += 1
    escape = text[start:escape_end]
    return UnknownEscape(escape, mark.line)
