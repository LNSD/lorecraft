"""What is wrong with a frontmatter block that does not parse, in lorecraft's words.

The YAML parser fails with an error that names its own internals: `<block end>`, `simple key`, a tuple of tokens.
adr-019 states ten kinds of syntax error a writer meets, each with a label, a help and the line the writer fixes, and
this module classifies the parser's error into one of them. It reads what the error carries, its class, the problem
and the context it names and its two marks, and the block's own text at them; no parser text reaches the result.

An error no kind matches is reported on the line the parser marked as `the block cannot be read from this line on`,
with no help, so a parser upgrade that rewords an error moves it there rather than to a wrong kind.
"""

import re
import string
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from ruamel.yaml.error import MarkedYAMLError, StreamMark
from ruamel.yaml.reader import ReaderError

from .lines import split_lines

_TOKEN_END_CHARACTERS: Final[str] = ' \t\r\n\x85  ,[]{}'
"""The characters that end an anchor, an alias or a tag as the block writes it: whitespace or a flow indicator."""

_ESCAPE_HEX_DIGITS: Final[Mapping[str, int]] = MappingProxyType({'x': 2, 'u': 4, 'U': 8})
"""How many hexadecimal digits the escapes `\\x`, `\\u` and `\\U` take after their letter."""

_BLOCK_SCALAR_HEADER: Final[re.Pattern[str]] = re.compile(r'(?:^|\s)[|>][+-]?[0-9]?\s*(?:#.*)?$')
"""The end of a line that opens a literal or folded block scalar, with its indicators and a comment after them."""


@dataclass(frozen=True, slots=True)
class SyntaxProblem:
    """One syntax error as lorecraft words it.

    Attributes:
        label: What is wrong, in lorecraft's words, shown at the line.
        help: What to do about it, or None where the error gives no more to say.
        line: The line of the block the writer fixes, counted from 0, or None when the parser marks none.
    """

    label: str
    help: str | None
    line: int | None


def describe_error(error: MarkedYAMLError, block: str) -> SyntaxProblem:
    """Classify a scanner's or a parser's error into one of adr-019's syntax error kinds.

    Args:
        error: The scanner's or the parser's error, whose class, problem, context and marks pick the kind.
        block: The text the parser read, the lines between the frontmatter delimiters.
    """
    lines = list(split_lines(block))
    problem = error.problem or ''
    context = error.context or ''
    mark = error.problem_mark
    context_mark = error.context_mark

    if context.startswith('while scanning an anchor') or context.startswith('while scanning an alias'):
        return _malformed_token('anchor' if 'anchor' in context else 'alias', context_mark, lines)
    if 'tag' in context or problem.startswith('found undefined tag handle'):
        return _malformed_token('tag', context_mark or mark, lines)
    if problem == "could not find expected ':'":
        return _not_key_or_item(_line_of(context_mark or mark))
    if context.startswith('while scanning a quoted scalar') and problem.startswith('found unexpected end'):
        return SyntaxProblem(
            'this quote is never closed',
            'Close it on the line it continues to, or remove it',
            _line_of(context_mark or mark),
        )
    if 'quoted scalar' in context and problem.startswith(('found unknown escape', 'expected escape sequence')):
        return _unknown_escape(mark, lines)
    if problem.startswith('found character') and 'cannot start any token' in problem:
        return _unstartable_character(problem, mark, lines)
    if problem == 'mapping values are not allowed here':
        return _misplaced_colon(mark, lines)
    if problem == 'mapping keys are not allowed here':
        return _cannot_start_value('?', mark)
    if problem.startswith(
        (
            "expected <block end>, but found '<block",
            "expected <block end>, but found '-'",
            "expected <block end>, but found '?'",
        )
    ):
        return _bad_indent(mark, lines)
    if problem == 'sequence entries are not allowed here':
        return _not_key_or_item(_line_of(mark))
    if problem.startswith("expected <block end>, but found '<scalar>'"):
        return _text_after_quote(mark, lines)
    if problem.startswith("expected '<document start>'"):
        return _not_key_or_item(_line_of(mark))
    return _unreadable(_line_of(mark or context_mark))


def _line_of(mark: StreamMark | None) -> int | None:
    """The line a mark is on, counted from 0, or None when there is no mark.

    Args:
        mark: A mark of the parser's error, which may be absent.
    """
    return None if mark is None else mark.line


def _unreadable(line: int | None) -> SyntaxProblem:
    """The kind for an error no kind of the table matches, reported on the line the parser marked.

    Args:
        line: The line, counted from 0, or None when the parser marks none.
    """
    return SyntaxProblem('the block cannot be read from this line on', None, line)


def _text(lines: list[str], line: int) -> str:
    """The text of a line of the block, or an empty one when the parser marked none.

    Args:
        lines: The block's lines.
        line: The line, counted from 0.
    """
    return lines[line] if 0 <= line < len(lines) else ''


def _not_key_or_item(line: int | None) -> SyntaxProblem:
    """The kind for a line that is neither `key: value` nor `- item`.

    Args:
        line: The line, counted from 0, or None when the parser marks none.
    """
    return SyntaxProblem(
        'this line is not `key: value` or `- item`', 'Add `: ` after the key, or quote a value that runs on', line
    )


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


def _indented_under_text(lines: list[str], line: int, key: str) -> SyntaxProblem | None:
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
        return SyntaxProblem(
            f'`{key}` is indented under `{parent}`, whose value is text',
            'Align it with the key it belongs beside',
            line,
        )
    return None


def _indent(text: str) -> int:
    """How many spaces start a line.

    Args:
        text: The line.
    """
    return len(text) - len(text.lstrip(' '))


def _bad_indent(mark: StreamMark | None, lines: list[str]) -> SyntaxProblem:
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


def _matches_no_level(line: int | None) -> SyntaxProblem:
    """The kind for a line indented to no level of the block.

    Args:
        line: The line, counted from 0, or None when the parser marks none.
    """
    return SyntaxProblem(
        "this line's indentation matches no key or item above it",
        'Indent it like the keys or items it belongs with',
        line,
    )


def _misplaced_colon(mark: StreamMark | None, lines: list[str]) -> SyntaxProblem:
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
        quoted = f'`{key}: "{value}"`' if value and '"' not in value else 'it'
        return SyntaxProblem('this value holds `: `', f'Quote the value: {quoted}', mark.line)
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


def _text_after_quote(mark: StreamMark | None, lines: list[str]) -> SyntaxProblem:
    """Classify text where an entry ended: after a closing quote, below a block scalar's text, or something else.

    Args:
        mark: Where the parser found the text.
        lines: The block's lines.
    """
    if mark is not None:
        before = _text(lines, mark.line)[: mark.column].rstrip()
        if before.endswith(('"', "'")):
            return SyntaxProblem('text follows the closing quote', 'Put the whole value inside the quotes', mark.line)
        if _below_block_scalar(mark.line, lines):
            return _bad_indent(mark, lines)
    return _unreadable(_line_of(mark))


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


def describe_control_character(error: ReaderError, block: str) -> SyntaxProblem:
    """Name a character the reader refuses, and the line it is on.

    Args:
        error: The reader's error, whose position is the character's index in the block.
        block: The text the reader read.
    """
    character = error.character
    code = character if isinstance(character, int) else ord(character)
    return SyntaxProblem(
        f'the block holds the control character U+{code:04X}', 'Remove it', block.count('\n', 0, error.position)
    )


def _cannot_start_value(character: str, mark: StreamMark | None) -> SyntaxProblem:
    """The kind for a character that cannot start a plain value.

    Args:
        character: The character, shown in the label.
        mark: Where the scanner found it.
    """
    # A backtick is named in words: written between backticks it would close its own quoting.
    named = 'a backtick' if character == '`' else f'`{character}`'
    return SyntaxProblem(f'a plain value cannot start with {named}', 'Quote the value', _line_of(mark))


def _unstartable_character(problem: str, mark: StreamMark | None, lines: list[str]) -> SyntaxProblem:
    """Classify a character that cannot start a token: a tab, or a character no plain value starts with.

    Args:
        problem: The scanner's problem, which names the character between quotes.
        mark: Where the scanner found it.
        lines: The block's lines.
    """
    if "'\\t'" in problem:
        text = _text(lines, mark.line) if mark is not None else ''
        if text.lstrip(' ').startswith('\t'):
            return SyntaxProblem('a tab indents this line', 'Indent with spaces', _line_of(mark))
        return SyntaxProblem('a tab is not whitespace here', 'Use spaces', _line_of(mark))
    if "'" not in problem:
        return _unreadable(_line_of(mark))
    return _cannot_start_value(problem.split("'")[1], mark)


def _unknown_escape(mark: StreamMark | None, lines: list[str]) -> SyntaxProblem:
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
    return SyntaxProblem(
        f'`{escape}` is not an escape', 'Write `\\\\` for a backslash, or use single quotes', mark.line
    )


def _malformed_token(kind: str, mark: StreamMark | None, lines: list[str]) -> SyntaxProblem:
    """Refuse a malformed anchor, alias or tag as the anchor, alias or tag frontmatter does not allow.

    Args:
        kind: `anchor`, `alias` or `tag`.
        mark: Where the anchor, alias or tag starts.
        lines: The block's lines.
    """
    if mark is None:
        article = 'an' if kind in ('anchor', 'alias') else 'a'
        return SyntaxProblem(f'found {article} {kind}, which frontmatter does not allow', None, None)
    text = _text(lines, mark.line)[mark.column :]
    if text.startswith('!<'):
        closing = text.find('>')
        written = text if closing == -1 else text[: closing + 1]
    else:
        end = next((index for index, character in enumerate(text) if character in _TOKEN_END_CHARACTERS), len(text))
        written = text[:end]
    named = repr(written) if kind == 'tag' else written
    return SyntaxProblem(f'found the {kind} {named}, which frontmatter does not allow', None, mark.line)
