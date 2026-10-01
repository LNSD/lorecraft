"""The frontmatter node of a document's parse tree: the decoded YAML mapping and where each key sits.

A document's frontmatter is a ``---`` delimited block on its first lines. Finding the block is the Markdown
parser's job (see ``document``); decoding it is this module's. Parsing has exactly four outcomes, one type each:
no block, a block that is not YAML, a block that is YAML but not a mapping, and a mapping. Every outcome is a
value, never an exception, because a broken block is a fact about the document that a check reports, not a
failure of the parse.
"""

from dataclasses import dataclass
from typing import Final

import yaml
from yaml.composer import ComposerError
from yaml.constructor import ConstructorError
from yaml.error import Mark
from yaml.reader import ReaderError
from yaml.scanner import ScannerError

from .position import LineNumber

_FIRST_BLOCK_LINE: Final[int] = 2
"""The document line the block's first YAML line sits on: the opening delimiter is always line 1."""

_STRING_KEY_TAGS: Final[frozenset[str]] = frozenset({'tag:yaml.org,2002:str', 'tag:yaml.org,2002:value'})
"""The tags of a scalar key that decodes to a string. ``value`` is the tag YAML gives a plain ``=`` key, or one
written with ``!!value``, and construction turns it into the string it holds, so it names a field like any other."""


@dataclass(frozen=True, slots=True)
class FrontmatterKey:
    """One top-level key of a frontmatter mapping and the line it is written on.

    Attributes:
        name: The key as YAML decoded it.
        line: The document line the key starts on. For a key written as an alias, such as ``*k``, it is the line of
            the anchored node the alias names: the node tree holds that node in the alias's place and keeps no
            position of the alias itself.
    """

    name: str
    line: LineNumber


@dataclass(frozen=True, slots=True)
class Frontmatter:
    """A frontmatter block that decoded to a YAML mapping.

    Frozen for equality only: ``data`` is a dict, so an instance is not hashable and must not be put in a set
    or used as a key. The parse tree is shared by every check that reads the document, so no check mutates
    ``data``.

    Attributes:
        data: The decoded mapping, exactly as ``yaml.safe_load`` returns it.
        keys: Every top-level key the mapping writes as a plain string, in document order, with its line. A key
            written more than once appears once per occurrence, although ``data`` holds only one value for it. A
            plain ``=`` key is listed too: YAML tags it as a value key, and it decodes to the string ``'='``. A
            key that reaches ``data`` only through a ``<<`` merge is not listed, so a finding about it lands on
            line 1, and neither is the ``<<`` key itself, which YAML tags as a merge rather than a string.
    """

    data: dict[object, object]
    keys: tuple[FrontmatterKey, ...]

    def key_line(self, name: str) -> LineNumber | None:
        """The line the last top-level key called ``name`` is written on, or ``None`` when there is none.

        The last, because a key written twice decodes to the value of its last occurrence: ``yaml.safe_load``
        replaces the earlier value with the later one, so the last line is where the value in ``data`` is written.
        A key the mapping writes also wins over the same key supplied by a ``<<`` merge, so its line is the right
        one even then.
        """
        line: LineNumber | None = None
        for key in self.keys:
            if key.name == name:
                line = key.line
        return line


@dataclass(frozen=True, slots=True)
class MissingFrontmatter:
    """The document does not open with a ``---`` line, or the block is never closed by one."""


@dataclass(frozen=True, slots=True)
class InvalidYamlFrontmatter:
    """The block is there but is not valid YAML.

    A value, compared by value, so it holds the parser's facts rather than the parser's exception, which compares
    by identity.

    Attributes:
        problem: What the YAML parser found wrong, such as ``mapping values are not allowed here``: in the parser's
            own words, or in this module's where the parser fails with a plain Python exception instead.
        line: The document line the problem is on, or None when it cannot be known: when the parser does not say,
            or when the block nests collections too deeply, where the parser stops at whatever depth the
            interpreter's stack allows rather than at a line of the document.
    """

    problem: str
    line: LineNumber | None


@dataclass(frozen=True, slots=True)
class NonMappingFrontmatter:
    """The block is valid YAML, but it decodes to something other than a mapping, such as a list or nothing."""


type FrontmatterNode = Frontmatter | MissingFrontmatter | InvalidYamlFrontmatter | NonMappingFrontmatter
"""Every outcome of parsing a document's frontmatter."""


def decode_frontmatter(block: str) -> FrontmatterNode:
    """Decode the YAML between a document's ``---`` delimiters into its node. Pure: raises nothing.

    Never ``MissingFrontmatter``: whether a block exists is decided before this is called. Every block PyYAML
    cannot read is ``InvalidYamlFrontmatter``, including the few it fails on with a plain Python exception rather
    than its own error, such as collections nested too deeply to parse.

    Args:
        block: The lines between the delimiters, line endings kept; the first of them is document line 2.
    """
    # `yaml.safe_load` composes a node tree and then constructs the value from it. The two steps run here
    # apart, on one loader, because the node tree is what records the line each key is written on.
    try:
        # The loader checks every character as it is built, so a control character fails here, not in the parse.
        loader = _SafeLoader(block)
    except ReaderError as exc:
        line = LineNumber(block.count('\n', 0, exc.position) + _FIRST_BLOCK_LINE)
        return InvalidYamlFrontmatter(problem=exc.reason, line=line)
    try:
        node = loader.get_single_node()
        # The keys are read before the value is constructed, because construction rewrites the node: for a `<<`
        # merge it puts the merged pairs in front of the written ones, so read afterwards, the keys would hold
        # keys the mapping never wrote, out of document order. It also retags a `=` key from a value key to a
        # string, which is why `_keys` accepts both tags.
        keys: tuple[FrontmatterKey, ...] = ()
        if isinstance(node, yaml.MappingNode):
            keys = _keys(node)
        data: object = None if node is None else loader.construct_document(node)
    except yaml.MarkedYAMLError as exc:
        # `_SafeLoader` raises the plain Python exceptions PyYAML lets escape as its own errors, so this one clause
        # sees every block that cannot be composed or constructed.
        return _invalid_yaml(exc)
    finally:
        # Clears the parser's state stack and nothing else, so it raises nothing, even after a failed compose.
        loader.dispose()

    if not isinstance(node, yaml.MappingNode) or not isinstance(data, dict):
        return NonMappingFrontmatter()
    return Frontmatter(data=data, keys=keys)


class _SafeLoader(yaml.SafeLoader):
    """PyYAML's safe loader, raising its own error for every block it cannot read, never a plain Python exception.

    PyYAML lets a plain Python exception escape in four places, and each is raised here as the loader's error,
    which ``decode_frontmatter`` already turns into invalid YAML:

    - The safe constructors of ``bool``, ``int``, ``float`` and ``timestamp`` convert a scalar's text with plain
      Python: ``!!int x`` raises a ``ValueError`` and ``!!bool x`` a ``KeyError``, and an untagged scalar YAML
      resolves to one of those tags fails the same way, such as the date ``9999-99-99``. Each is a
      ``ConstructorError`` on the scalar's line.
    - A double-quoted ``\\U`` escape above ``U+10FFFF`` names no character, and ``chr`` raises a ``ValueError``,
      or an ``OverflowError`` for one too large for a C ``int``. It is a ``ScannerError`` on the escape's line.
    - A ``%YAML`` directive whose version number has more digits than Python converts to an ``int``, 4300 by
      default, raises a ``ValueError``. It is a ``ScannerError`` on the directive's line.
    - Collections nested a few hundred levels deep exhaust the interpreter's stack in the composer, which recurses
      once per level, and raise a ``RecursionError``. It is a ``ComposerError`` with no line.
    """

    def get_single_node(self) -> yaml.Node | None:
        """Compose the block's one document into its node tree, as the safe loader does, or ``None`` for no document.

        Raises:
            ComposerError: The block nests collections deeper than the interpreter's stack can compose.
            yaml.MarkedYAMLError: The block is not valid YAML, as PyYAML reports it.
        """
        try:
            return super().get_single_node()
        except RecursionError as exc:
            # The composer recurses once per level of nesting, so only a deeply nested block reaches the
            # interpreter's limit. Catching it is safe here: by the time this clause runs, the stack has unwound to
            # this frame, so there is room to raise again, and the loader whose state the composer left half-built
            # is discarded by its caller, which reads nothing more from it. The line is left out, because the
            # depth the composer stops at depends on the interpreter's recursion limit and on how deep the caller's
            # stack already was, not on the document.
            problem = 'found collections nested too deeply to parse'
            raise ComposerError(None, None, problem, None) from exc

    def scan_flow_scalar_non_spaces(self, double: bool, start_mark: Mark) -> list[str]:
        """Scan the text of a quoted scalar up to its next space, as the safe loader does.

        Raises:
            ScannerError: An escape names no Unicode character, or the text is not valid YAML.
        """
        try:
            return super().scan_flow_scalar_non_spaces(double, start_mark)
        except (ValueError, OverflowError) as exc:
            # The scanner checks that an escape is written in hexadecimal, but not that the code point it names is
            # at most U+10FFFF, so `chr` raises: a ValueError for `\U00110000`, and for `\UFFFFFFFF`, which does not
            # fit a C int, an OverflowError on the interpreters that convert the argument first. Nothing else in
            # this method raises either. The scanner stops on the escape's digits, so its current mark is on the
            # escape's line.
            problem = 'found an escape sequence that names no Unicode character'
            raise ScannerError(None, None, problem, self.get_mark()) from exc

    def scan_yaml_directive_number(self, start_mark: Mark) -> int:
        """Scan one number of a ``%YAML`` directive's version, as the safe loader does.

        Raises:
            ScannerError: The number is too long to read, or the text is not a number.
        """
        try:
            return super().scan_yaml_directive_number(start_mark)
        except ValueError as exc:
            # The scanner reads every digit there is and converts them with `int`, which refuses more digits than
            # the interpreter's integer string conversion limit. The scanner stops before the digits, so its
            # current mark is on the directive's line.
            problem = 'found a YAML version number too long to read'
            raise ScannerError(None, None, problem, self.get_mark()) from exc

    def construct_object(self, node: yaml.Node, deep: bool = False) -> object:
        """Construct the value of one node, as the safe loader does, or raise a ``ConstructorError`` marked at it."""
        # The classes caught are the ones the safe constructors raise for a scalar's text: a `ValueError` from
        # `int`, `float` or `datetime` for text or a field out of range, a `KeyError` from the `bool` lookup, an
        # `IndexError` from reading the sign of empty text, an `AttributeError` from a timestamp that does not
        # match its pattern, and a `TypeError` from a timestamp written as a `=` mapping. The failing scalar's own
        # call raises it, so the scalar is the node marked; the error then passes through every enclosing call
        # unchanged, since a `ConstructorError` is none of these classes.
        try:
            return super().construct_object(node, deep=deep)
        except (ValueError, KeyError, IndexError, AttributeError, TypeError) as exc:
            problem = f'could not construct a value for the tag {node.tag!r}'
            raise ConstructorError(None, None, problem, node.start_mark) from exc


def _invalid_yaml(error: yaml.MarkedYAMLError) -> InvalidYamlFrontmatter:
    """The parser's facts about a block that does not parse: its problem, and the line it marked."""
    # The parser names the problem, or, for a few errors, only the construct it was reading when it stopped.
    problem = error.problem or error.context or 'the block is not valid YAML'
    mark = error.problem_mark or error.context_mark
    if mark is None:
        return InvalidYamlFrontmatter(problem=problem, line=None)
    # The mark counts lines from 0 within the block; the block starts on document line 2.
    return InvalidYamlFrontmatter(problem=problem, line=LineNumber(mark.line + _FIRST_BLOCK_LINE))


def _keys(mapping: yaml.MappingNode) -> tuple[FrontmatterKey, ...]:
    """Every top-level key of the mapping written as a plain string, in document order, with its document line.

    Read from a node no value has been constructed from yet, which still holds every pair as it is written. A key
    written more than once is listed once per occurrence, where the constructed mapping keeps only one value. A
    scalar key tagged as a value key, such as a plain ``=``, is listed as well, because construction has not yet
    retagged it to the string it decodes to. A key the mapping spells some other way, such as a list or a number,
    has no name a check could ask for, so it is left out, and so is a ``<<`` merge key, which is tagged as a merge
    rather than a string.
    """
    keys: list[FrontmatterKey] = []
    for key_node, _value_node in mapping.value:
        if not isinstance(key_node, yaml.ScalarNode) or key_node.tag not in _STRING_KEY_TAGS:
            continue
        # The mark counts lines from 0 within the block; the block starts on document line 2.
        line = LineNumber(key_node.start_mark.line + _FIRST_BLOCK_LINE)
        keys.append(FrontmatterKey(name=key_node.value, line=line))
    return tuple(keys)
