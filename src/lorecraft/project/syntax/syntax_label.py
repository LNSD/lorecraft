"""What a syntax error is called in lorecraft's words, as `LC202` reports it.

`lorecraft.yaml` classifies a parser's error into one of adr-019's kinds and never words it; this module words each
kind with a label, a help and the line the writer fixes, and a refused control character the same way.
"""

from dataclasses import dataclass
from typing import assert_never

from lorecraft.core.lines import LineOffset
from lorecraft.yaml.problem import ControlCharacterProblem
from lorecraft.yaml.syntax_error import (
    ClosesNothing,
    ColonInValue,
    IndentedUnderText,
    MatchesNoLevel,
    NotKeyOrItem,
    SeparatorEscape,
    TabIndent,
    TabInLine,
    TextAfterCollection,
    TextAfterQuote,
    UnclosedQuote,
    UnknownEscape,
    UnreadableBlock,
    UnstartableCharacter,
    YamlSyntaxError,
)


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


def describe_syntax_error(error: YamlSyntaxError) -> SyntaxProblem:
    """Word a syntax error's kind with its label and help.

    Args:
        error: The kind the parser's error was classified as.
    """
    match error:
        case NotKeyOrItem(line):
            return SyntaxProblem(
                'this line is not `key: value` or `- item`',
                'Add `: ` after the key, or quote a value that runs on',
                _line_value(line),
            )
        case UnclosedQuote(line):
            return SyntaxProblem(
                'this quote is never closed', 'Close it on the line it continues to, or remove it', _line_value(line)
            )
        case SeparatorEscape(separator, line):
            # The separator is invisible between backticks, so the label names its code point.
            return SyntaxProblem(
                f'`\\` before U+{ord(separator):04X} is not an escape',
                'Write `\\\\` for a backslash, or use single quotes',
                _line_value(line),
            )
        case UnknownEscape(escape, line):
            return SyntaxProblem(
                f'`{escape}` is not an escape', 'Write `\\\\` for a backslash, or use single quotes', _line_value(line)
            )
        case UnstartableCharacter(character, line):
            # A backtick is named in words: written between backticks it would close its own quoting.
            named = 'a backtick' if character == '`' else f'`{character}`'
            return SyntaxProblem(f'a plain value cannot start with {named}', 'Quote the value', _line_value(line))
        case ColonInValue(key, value, line):
            quoted = f'`{key}: "{value}"`' if value and '"' not in value else 'it'
            return SyntaxProblem('this value holds `: `', f'Quote the value: {quoted}', _line_value(line))
        case IndentedUnderText(key, parent, line):
            return SyntaxProblem(
                f'`{key}` is indented under `{parent}`, whose value is text',
                'Align it with the key it belongs beside',
                _line_value(line),
            )
        case MatchesNoLevel(line):
            return SyntaxProblem(
                "this line's indentation matches no key or item above it",
                'Indent it like the keys or items it belongs with',
                _line_value(line),
            )
        case ClosesNothing(bracket, line):
            return SyntaxProblem(f'this `{bracket}` closes nothing', 'Remove it, or quote the value', _line_value(line))
        case TextAfterQuote(line):
            return SyntaxProblem(
                'text follows the closing quote', 'Put the whole value inside the quotes', _line_value(line)
            )
        case TextAfterCollection(bracket, line):
            return SyntaxProblem(
                f'text follows the closing `{bracket}`',
                'Move the text inside the brackets, or quote the whole value',
                _line_value(line),
            )
        case TabIndent(line):
            return SyntaxProblem('a tab indents this line', 'Indent with spaces', _line_value(line))
        case TabInLine(line):
            return SyntaxProblem('a tab is not whitespace here', 'Use spaces', _line_value(line))
        case UnreadableBlock(line):
            return SyntaxProblem('the block cannot be read from this line on', None, _line_value(line))
        case _:
            assert_never(error)


def describe_control_character(error: ControlCharacterProblem) -> SyntaxProblem:
    """Name a character the reader refuses, and the line it is on.

    Args:
        error: The refused character, with its position in the block.
    """
    return SyntaxProblem(
        f'the block holds the control character U+{error.code:04X}',
        'Remove it',
        error.position.line.value - 1,
    )


def _line_value(line: LineOffset | None) -> int | None:
    """Unwrap the zero-based YAML line for the diagnostic value."""
    return None if line is None else line.value
