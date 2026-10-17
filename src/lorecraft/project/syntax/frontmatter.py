"""The frontmatter node of a document's parse tree: the decoded YAML mapping and where each key sits.

A document's frontmatter is a `---` delimited block on its first lines. Finding the block is the Markdown
reader's job (`lorecraft.markdown.parse_markdown_frontmatter`); decoding its raw block is this module's. Parsing has
exactly four outcomes, one type each: no block, a block that is not YAML, a block that is YAML but not a mapping,
and a mapping. Every outcome is a value, never an exception, because a broken block is a fact about the document
that a check reports, not a failure of the parse.

The block is read as basic YAML, which decodes to exactly what JSON can hold, and accepts only these constructs:

- the block itself is one block mapping, one key to a line, whose keys are plain, single-quoted or double-quoted
  scalars that read as strings;
- a value is any accepted node, or nothing, which is null; a block mapping nested as a value is indented by spaces;
- a block sequence is a value, indented or not, and its items are scalars, flow collections or block mappings;
- a flow sequence or a flow mapping is written on one line and holds only scalars, or nothing;
- a plain scalar is written on one line or continued on more indented lines; a single-quoted scalar writes `''`
  for a quote and a double-quoted one takes YAML's escapes, both on one or more lines;
- a literal (`|`) or folded (`>`) block scalar takes an optional `-` or `+` chomping indicator;
- a comment, on its own line or after a node, blank lines, CRLF line breaks and a BOM before the first line are
  nothing.

A quoted or block scalar is a string. A plain scalar is null, a boolean, an integer or a float when its whole text
is one in YAML 1.2's core schema, such as `~`, `true`, `12` or `1.5`, and a string otherwise, so `.inf` and `.nan`,
`yes`, `on`, `2026-10-05` and `1:30` are strings. A directive, a document marker, an anchor, an alias, a merge key, a
tag, an explicit or empty key, a key that is not a string, a flow collection that spreads over lines, holds a
collection or is the whole block, a block scalar's indentation indicator and a block sequence as an item of a block
sequence are refused, on their line, as a block that is not YAML: none is
needed to write a document's metadata, an alias can make a collection hold itself, a tag builds values JSON has no
counterpart for, and JSON names every key with a string.
"""

from dataclasses import dataclass
from typing import Final, assert_never

from lorecraft.core.mapping import Frozen, FrozenMapping
from lorecraft.core.num import NonZeroUnsignedInt
from lorecraft.yaml.problem import (
    ControlCharacterProblem,
    NestingTooDeepProblem,
    RefusedConstructProblem,
    SyntaxErrorProblem,
    YamlProblem,
)
from lorecraft.yaml.reader import read_yaml
from lorecraft.yaml.tree import YamlMapping, YamlScalar, YamlSequence, YamlValue

from .position import LineNumber
from .refusal import describe_refusal, refusal_help
from .syntax_label import SyntaxProblem, describe_control_character, describe_syntax_error

_FIRST_BLOCK_LINE: Final[int] = 2
"""The document line the block's first YAML line sits on: the opening delimiter is always line 1."""

_TOO_DEEP: Final[str] = 'found collections nested too deeply to parse'
"""The problem of a block that nests collections past what the interpreter's stack reads."""


@dataclass(frozen=True, slots=True)
class FrontmatterKey:
    """One key of a frontmatter mapping, at any depth, and the line it is written on.

    Attributes:
        name: The key as YAML decoded it.
        line: The document line the key starts on.
    """

    name: str
    line: LineNumber


@dataclass(frozen=True, slots=True)
class RepeatedKey:
    """A key a mapping writes again after its first occurrence, at any depth.

    Attributes:
        name: The key as YAML decoded it.
        line: The document line this later occurrence is written on.
        first_line: The line the mapping's first occurrence of the key is written on.
        kept_line: The line of the mapping's last occurrence, whose value the data holds.
    """

    name: str
    line: LineNumber
    first_line: LineNumber
    kept_line: LineNumber


@dataclass(frozen=True, slots=True)
class Frontmatter:
    """A frontmatter block that decoded to a YAML mapping.

    Every key in it is a string, at any depth: a block writing any other key, such as `1:` or `true:`, does not
    decode to frontmatter at all, so no check ever meets a key a JSON Schema cannot name.

    Attributes:
        data: The decoded mapping, frozen all the way down: every mapping in it is a `FrozenMapping`, every list a
            tuple, and every scalar a string, an integer, a float, a boolean or `None`, which is what `json.loads`
            would build for the same data, frozen. So no check can write to it, at any depth, although the parse tree
            is shared by every check that reads the document.
        keys: Every top-level key the mapping writes, in document order, with its line. A key written more than
            once appears once per occurrence, although `data` holds only one value for it.
        repeats: Every key written again within one mapping, at any depth, in document order: one per occurrence after
            the first, which is the line it points back at. The last occurrence's value is the one `data` holds.
    """

    data: FrozenMapping[str, Frozen]
    keys: tuple[FrontmatterKey, ...]
    repeats: tuple[RepeatedKey, ...] = ()

    def find_key_line(self, name: str) -> LineNumber | None:
        """The line the last top-level key called `name` is written on, or `None` when there is none.

        The last, because a key written twice decodes to the value of its last occurrence, so the last line is
        where the value in `data` is written.

        Args:
            name: Key to look up, spelled as written.
        """
        line: LineNumber | None = None
        for key in self.keys:
            if key.name == name:
                line = key.line
        return line


@dataclass(frozen=True, slots=True)
class MissingFrontmatter:
    """The document does not open with a `---` line, or the block is never closed by one."""


@dataclass(frozen=True, slots=True)
class InvalidYamlFrontmatter:
    """The block is there but is not valid YAML, or uses YAML beyond the basic subset frontmatter is read as.

    A value, compared by value, so it holds the parser's facts rather than the parser's exception, which compares
    by identity.

    Attributes:
        problem: What is wrong, in lorecraft's words, such as `this value holds ': '`, or `found the tag '!!str',
            which frontmatter does not allow` where the block uses what basic YAML leaves out, a key that is not a
            string included.
        help: What to do about it, where a syntax error has a fix to name, and None for a construct frontmatter
            does not allow, which the problem already names.
        line: The document line the problem is on, or None when it cannot be known: when the parser does not say,
            or when the block nests collections too deeply, where reading stops at whatever depth the interpreter's
            stack allows rather than at a line of the document.
    """

    problem: str
    line: LineNumber | None
    help: str | None = None


@dataclass(frozen=True, slots=True)
class NonMappingFrontmatter:
    """The block is valid YAML, but it decodes to something other than a mapping, such as a list or nothing."""


type FrontmatterNode = Frontmatter | MissingFrontmatter | InvalidYamlFrontmatter | NonMappingFrontmatter
"""Every outcome of parsing a document's frontmatter."""


def decode_frontmatter(block: str) -> FrontmatterNode:
    """Decode the YAML between a document's `---` delimiters into its node. Pure: raises nothing.

    Never `MissingFrontmatter`: whether a block exists is decided before this is called. Every block the YAML
    parser cannot parse is `InvalidYamlFrontmatter`, including the few it fails on with a built-in Python exception
    rather than its own error, and so is every block that uses a directive, a document marker, an anchor, an
    alias, a merge key or a tag, writes a key, at any depth, that is not a string, such as `1:`, `true:` or `null:`,
    or nests collections too deeply to read.

    Args:
        block: The lines between the delimiters, line endings kept; the first of them is document line 2.
    """
    try:
        root = read_yaml(block)
        match root:
            case ControlCharacterProblem() | SyntaxErrorProblem() | RefusedConstructProblem() | NestingTooDeepProblem():
                return _invalid_yaml_of(root)
            case YamlMapping() | YamlSequence() | YamlScalar() | None:
                return _node_of(root)
            case _:
                assert_never(root)
    except RecursionError:
        # The value is mapped with one call per level of nesting, so only a deeply nested block reaches the
        # interpreter's limit, once the read has finished and found nothing wrong above it. By the time this clause
        # runs the stack has unwound to this frame, so there is room to go on. The line is left out, because the
        # depth reading stops at depends on the interpreter's recursion limit and on how deep the caller's stack
        # already was.
        return InvalidYamlFrontmatter(problem=_TOO_DEEP, line=None)


def is_string_when_read_back(text: str) -> bool:
    """Whether a frontmatter field written as `text` without quotes decodes to that same string.

    It goes through `decode_frontmatter`, so the answer is the one the frontmatter reader gives: `1.0`, `true`,
    `0o17` and `1e3` read back as another value, and so does an empty text or one that is not YAML at all.

    Args:
        text: The text to write after `field: `.
    """
    node = decode_frontmatter(f'field: {text}\n')
    match node:
        case Frontmatter():
            return node.data.get('field') == text
        case MissingFrontmatter() | InvalidYamlFrontmatter() | NonMappingFrontmatter():
            return False
        case _:
            assert_never(node)


def _document_line(block_line: int) -> LineNumber:
    """The document line a line of the block is.

    Args:
        block_line: The line as the block counts it, from 1 at the block's first line.
    """
    # The block starts on document line 2, below the opening delimiter.
    return LineNumber(NonZeroUnsignedInt(block_line - 1 + _FIRST_BLOCK_LINE))


def _node_of(root: YamlValue | None) -> Frontmatter | NonMappingFrontmatter:
    """The node a block's root decodes to: frontmatter when it is a mapping, and anything else is not.

    Args:
        root: The block's root, or `None` when the block holds no document.
    """
    if not isinstance(root, YamlMapping):
        return NonMappingFrontmatter()
    # An inner mapping ends before the one that holds it, so its repeats came first; document order is by line.
    repeats = tuple(sorted(_repeats_in(root), key=lambda repeat: repeat.line))
    keys = tuple(FrontmatterKey(key.name, _document_line(key.position.line.value)) for key, _value in root.entries)
    return Frontmatter(data=_to_mapping(root), keys=keys, repeats=repeats)


def _to_frozen(value: YamlValue) -> Frozen:
    """The frozen value a node decodes to: a `FrozenMapping`, a tuple or a scalar.

    Args:
        value: The node.
    """
    match value:
        case YamlMapping():
            return _to_mapping(value)
        case YamlSequence():
            return tuple(_to_frozen(item) for item in value.items)
        case YamlScalar():
            return value.value
        case _:
            assert_never(value)


def _to_mapping(mapping: YamlMapping) -> FrozenMapping[str, Frozen]:
    """The mapping a node decodes to: a key written more than once holds the value of its last occurrence.

    Args:
        mapping: The mapping node, whose pairs are in the order they are written.
    """
    data: dict[str, Frozen] = {}
    for key, value in mapping.entries:
        data[key.name] = _to_frozen(value)
    return FrozenMapping(data)


def _repeats_in(value: YamlValue) -> list[RepeatedKey]:
    """The keys written again in a node and in every mapping inside it, those of the inner mappings first.

    Args:
        value: The node.
    """
    repeats: list[RepeatedKey] = []
    match value:
        case YamlMapping():
            for _key, entry_value in value.entries:
                repeats.extend(_repeats_in(entry_value))
            repeats.extend(_repeats_of(value))
        case YamlSequence():
            for item in value.items:
                repeats.extend(_repeats_in(item))
        case YamlScalar():
            pass
        case _:
            assert_never(value)
    return repeats


def _repeats_of(mapping: YamlMapping) -> list[RepeatedKey]:
    """The keys the mapping writes again, one per occurrence after the first, in the order they are written.

    Args:
        mapping: The mapping node, whose pairs are in the order they are written.
    """
    first_lines: dict[str, LineNumber] = {}
    last_lines: dict[str, LineNumber] = {}
    lines: list[tuple[str, LineNumber]] = []
    for key, _value in mapping.entries:
        line = _document_line(key.position.line.value)
        lines.append((key.name, line))
        first_lines.setdefault(key.name, line)
        last_lines[key.name] = line
    seen: set[str] = set()
    repeats: list[RepeatedKey] = []
    for name, line in lines:
        if name in seen:
            repeats.append(RepeatedKey(name, line, first_lines[name], last_lines[name]))
        seen.add(name)
    return repeats


def _invalid_yaml(problem: SyntaxProblem) -> InvalidYamlFrontmatter:
    """The node for a syntax error: its label, help and line, as the block's document lines count them.

    Args:
        problem: The syntax error as lorecraft words it, on the line the reader counted, from 0.
    """
    line = None if problem.line is None else _document_line(problem.line + 1)
    return InvalidYamlFrontmatter(problem=problem.label, line=line, help=problem.help)


def _invalid_yaml_of(problem: YamlProblem) -> InvalidYamlFrontmatter:
    """The node for a block that could not be read, worded from the problem it wrote first.

    Args:
        problem: What stopped the read.
    """
    match problem:
        case ControlCharacterProblem():
            return _invalid_yaml(describe_control_character(problem))
        case SyntaxErrorProblem():
            return _invalid_yaml(describe_syntax_error(problem.error))
        case RefusedConstructProblem():
            return InvalidYamlFrontmatter(
                problem=describe_refusal(problem.construct),
                line=_document_line(problem.position.line.value),
                help=refusal_help(problem.construct),
            )
        case NestingTooDeepProblem():
            return InvalidYamlFrontmatter(problem=_TOO_DEEP, line=None)
        case _:
            assert_never(problem)
