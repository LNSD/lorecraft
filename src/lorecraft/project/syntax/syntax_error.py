"""What is wrong with a frontmatter block that does not parse, in lorecraft's words.

The YAML parser fails with an error that names its own internals: `<block end>`, `simple key`, a tuple of tokens.
adr-019 states ten kinds of syntax error a writer meets, each with a label, a help and the line the writer fixes, and
this module classifies the parser's error into one of them. It reads what the error carries, its class, the problem
and the context it names and its two marks, and the block's own text at them; no parser text reaches the result.

An error no kind matches is reported on the line the parser marked as `the block cannot be read from this line on`,
with no help, so a parser upgrade that rewords an error moves it there rather than to a wrong kind.
"""

from dataclasses import dataclass

from ruamel.yaml.error import MarkedYAMLError, StreamMark


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
    lines = block.splitlines()
    problem = error.problem or ''
    context = error.context or ''
    mark = error.problem_mark
    context_mark = error.context_mark

    if context.startswith('while scanning a quoted scalar') and problem.startswith('found unexpected end'):
        return SyntaxProblem(
            'this quote is never closed',
            'Close it on the line it continues to, or remove it',
            _line_of(context_mark or mark),
        )
    if problem == 'mapping values are not allowed here':
        return _misplaced_colon(mark, lines)
    if problem.startswith("expected <block end>, but found '<block"):
        return _bad_indent(mark, lines)
    if problem.startswith("expected <block end>, but found '<scalar>'"):
        return _text_after_quote(mark, lines)
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
    return SyntaxProblem(
        "this line's indentation matches no key or item above it",
        'Indent it like the keys or items it belongs with',
        _line_of(mark),
    )


def _misplaced_colon(mark: StreamMark | None, lines: list[str]) -> SyntaxProblem:
    """Classify a `:` where a key is not allowed: a second one in a value, or a key under a text value.

    Args:
        mark: Where the scanner found the `:`.
        lines: The block's lines.
    """
    if mark is None:
        return _unreadable(None)
    text = _text(lines, mark.line)
    before = text[: mark.column]
    if ': ' not in before:
        under_text = _indented_under_text(lines, mark.line, before.strip())
        if under_text is not None:
            return under_text
    key, _, value = text.strip().partition(': ')
    quoted = f'`{key}: "{value}"`' if value and '"' not in value else 'it'
    return SyntaxProblem('this value holds `: `', f'Quote the value: {quoted}', mark.line)


def _text_after_quote(mark: StreamMark | None, lines: list[str]) -> SyntaxProblem:
    """Classify text the parser found where a mapping entry ended: after a closing quote, or something else.

    Args:
        mark: Where the parser found the text.
        lines: The block's lines.
    """
    if mark is not None:
        before = _text(lines, mark.line)[: mark.column].rstrip()
        if before.endswith(('"', "'")):
            return SyntaxProblem('text follows the closing quote', 'Put the whole value inside the quotes', mark.line)
    return _unreadable(_line_of(mark))
