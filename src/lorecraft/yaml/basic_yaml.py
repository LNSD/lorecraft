"""The YAML grammar Lorecraft reads: ruamel.yaml's reader, scanner and parser, bent to its format.

ruamel.yaml reads YAML 1.2 with a few YAML 1.1 habits and a stricter reading of some constructs than the subset
takes. This module holds the subclasses that make it read exactly the format adr-019 states: a scanner that
refuses what the format leaves out, a reader that records the line separators it does not treat as breaks, and a
parser that takes every tag handle. `lorecraft.yaml.reader` reads the events they produce; it never reaches
ruamel.yaml another way, so no tag ruamel.yaml resolves and no type it constructs is ever involved.

A construct the format leaves out is either an error raised where the scanner or the parser meets it, a
`Refused...Error`, or a `RecordedRefusal` the scanner notes and reads on from, because it reads ahead of the parser.
Each carries the `mark` where it is written and the `construct` it is, which a package above words.
"""

from dataclasses import dataclass
from typing import Final, Never

from ruamel.yaml.compat import check_anchorname_char
from ruamel.yaml.error import StreamMark
from ruamel.yaml.parser import Parser
from ruamel.yaml.reader import Reader
from ruamel.yaml.scanner import Scanner, ScannerError
from ruamel.yaml.tag import Tag as RuamelTag
from ruamel.yaml.tokens import ScalarToken, TagToken, Token

from lorecraft.core.error import Error, Unreachable

from .position import LINE_SEPARATORS
from .problem import (
    Alias,
    Anchor,
    CollectionInFlow,
    CollectionKey,
    Directive,
    DocumentMarker,
    EmptyKey,
    EscapeBeyondUnicode,
    ExplicitKey,
    FlowCollectionRoot,
    IndentationIndicator,
    LineSeparator,
    MergeKey,
    NestedBlockSequence,
    NonStringKey,
    RefusedConstruct,
    SpreadFlowCollection,
    Tag,
)

MERGE_KEY: Final[str] = '<<'
"""The plain key YAML 1.1 reads as a merge: the entries of the mapping an alias names join the mapping."""


class _RefusalError(Error):
    """A construct the subset leaves out that stops parsing, located where it is written.

    Every such construct carries the `mark` where it is written and the `construct` it is.
    """

    mark: StreamMark
    construct: RefusedConstruct


_SPACE_CHARACTERS: Final[str] = '\0 \t\r\n'
"""The characters that end a plain scalar: the end of the text, a space or tab, or a line break."""

_LINE_END_CHARACTERS: Final[str] = '\0\r\n'
"""The characters that end a line: the end of the text, or a line break."""

_TOKEN_END_CHARACTERS: Final[str] = _SPACE_CHARACTERS + ',[]{}'
"""The characters that end an anchor, an alias or a tag as a block writes it: whitespace or a flow indicator."""

_QUOTED_TEXT_END_CHARACTERS: Final[str] = ' \n\'"\\\0\t\r'
"""The characters the text of a quoted scalar stops at: ruamel.yaml's set without U+0085, U+2028 and U+2029, which
are text inside quotes."""

_DIRECTIVE_NAME_END_CHARACTERS: Final[str] = _SPACE_CHARACTERS + ',[]{}:'
"""The characters that end the name a refused directive is reported by: whitespace, a flow indicator or a `:`."""


@dataclass(frozen=True, slots=True)
class RecordedRefusal:
    """A construct the subset leaves out, which the scanner met and recorded without stopping.

    Attributes:
        construct: Which construct it is.
        mark: Where it is written.
    """

    construct: RefusedConstruct
    mark: StreamMark


class RefusedDirectiveError(_RefusalError):
    """A directive, a `%` line, is written.

    Attributes:
        name: The `%` and the name that follows it.
        mark: Where the directive is written.
        construct: The construct, as a value a package above words.
    """

    name: str
    mark: StreamMark
    construct: RefusedConstruct

    def __init__(self, name: str, mark: StreamMark) -> None:
        self.name = name
        self.mark = mark
        self.construct = Directive(name)
        super().__init__(self.construct)


class RefusedDocumentMarkerError(_RefusalError):
    """A `---` or `...` marker is written, though the block is the body of one document.

    Attributes:
        marker: The three characters of the marker.
        mark: Where the marker is written.
        construct: The construct, as a value a package above words.
    """

    marker: str
    mark: StreamMark
    construct: RefusedConstruct

    def __init__(self, marker: str, mark: StreamMark) -> None:
        self.marker = marker
        self.mark = mark
        self.construct = DocumentMarker(marker)
        super().__init__(self.construct)


class RefusedAliasError(_RefusalError):
    """A value is an alias.

    Attributes:
        anchor: The anchor's name, without the `*`.
        mark: Where the alias is written.
        construct: The construct, as a value a package above words.
    """

    anchor: str
    mark: StreamMark
    construct: RefusedConstruct

    def __init__(self, anchor: str, mark: StreamMark) -> None:
        self.anchor = anchor
        self.mark = mark
        self.construct = Alias(anchor)
        super().__init__(self.construct)


class RefusedAnchorError(_RefusalError):
    """A value carries an anchor.

    Attributes:
        anchor: The anchor's name, without the `&`.
        mark: Where the anchor is written.
        construct: The construct, as a value a package above words.
    """

    anchor: str
    mark: StreamMark
    construct: RefusedConstruct

    def __init__(self, anchor: str, mark: StreamMark) -> None:
        self.anchor = anchor
        self.mark = mark
        self.construct = Anchor(anchor)
        super().__init__(self.construct)


class RefusedTagError(_RefusalError):
    """A value carries a tag, the non-specific `!` included.

    Attributes:
        tag: The tag as the block writes it.
        mark: Where the tag is written.
        construct: The construct, as a value a package above words.
    """

    tag: str
    mark: StreamMark
    construct: RefusedConstruct

    def __init__(self, tag: str, mark: StreamMark) -> None:
        self.tag = tag
        self.mark = mark
        self.construct = Tag(tag)
        super().__init__(self.construct)


class RefusedMergeKeyError(_RefusalError):
    """A mapping writes the plain key `<<`, which YAML 1.1 reads as a merge.

    Attributes:
        mark: Where the key is written.
        construct: The construct, as a value a package above words.
    """

    mark: StreamMark
    construct: RefusedConstruct

    def __init__(self, mark: StreamMark) -> None:
        self.mark = mark
        self.construct = MergeKey()
        super().__init__(self.construct)


class RefusedCollectionKeyError(_RefusalError):
    """A mapping's key is a collection, not a string.

    Attributes:
        mark: Where the key is written.
        construct: The construct, as a value a package above words.
    """

    mark: StreamMark
    construct: RefusedConstruct

    def __init__(self, mark: StreamMark) -> None:
        self.mark = mark
        self.construct = CollectionKey()
        super().__init__(self.construct)


class RefusedNonStringKeyError(_RefusalError):
    """A mapping's key is a scalar that decodes to null, a boolean or a number, not a string.

    Attributes:
        key: The key as written, which is empty for a key written as nothing at all.
        mark: Where the key is written.
        construct: The construct, as a value a package above words.
    """

    key: str
    mark: StreamMark
    construct: RefusedConstruct

    def __init__(self, key: str, mark: StreamMark) -> None:
        self.key = key
        self.mark = mark
        self.construct = NonStringKey(key)
        super().__init__(self.construct)


class RefusedFlowBlockError(_RefusalError):
    """The whole block is a flow collection, not a block mapping.

    Attributes:
        mark: Where the flow collection starts.
        construct: The construct, as a value a package above words.
    """

    mark: StreamMark
    construct: RefusedConstruct

    def __init__(self, mark: StreamMark) -> None:
        self.mark = mark
        self.construct = FlowCollectionRoot()
        super().__init__(self.construct)


class RefusedFlowNestedCollectionError(_RefusalError):
    """A flow collection holds a collection.

    Attributes:
        mark: Where the inner collection starts.
        construct: The construct, as a value a package above words.
    """

    mark: StreamMark
    construct: RefusedConstruct

    def __init__(self, mark: StreamMark) -> None:
        self.mark = mark
        self.construct = CollectionInFlow()
        super().__init__(self.construct)


class RefusedNestedBlockSequenceError(_RefusalError):
    """A block sequence holds a block sequence as an item.

    Attributes:
        mark: Where the inner sequence starts.
        construct: The construct, as a value a package above words.
    """

    mark: StreamMark
    construct: RefusedConstruct

    def __init__(self, mark: StreamMark) -> None:
        self.mark = mark
        self.construct = NestedBlockSequence()
        super().__init__(self.construct)


class RefusedMalformedTagError(_RefusalError):
    """A tag the scanner cannot read.

    That is a tag such as a verbatim tag left open or empty, a bad `%` escape, or a tag with no space after it.

    Attributes:
        tag: The tag as the block writes it.
        mark: Where the tag is written.
        construct: The construct, as a value a package above words.
        source: The scanner's error.
    """

    tag: str
    mark: StreamMark
    construct: RefusedConstruct
    source: ScannerError

    def __init__(self, tag: str, mark: StreamMark, *, source: ScannerError) -> None:
        self.tag = tag
        self.mark = mark
        self.construct = Tag(tag)
        self.source = source
        super().__init__(self.construct)
        self.__cause__ = source


class RefusedEscapeError(_RefusalError):
    """A double-quoted escape names a code point above `U+10FFFF`, which `chr` cannot build.

    Attributes:
        mark: Where the escape is written.
        construct: The construct, as a value a package above words.
        source: The failure `chr` raised.
    """

    mark: StreamMark
    construct: RefusedConstruct
    source: ValueError | OverflowError

    def __init__(self, mark: StreamMark, *, source: ValueError | OverflowError) -> None:
        self.mark = mark
        self.construct = EscapeBeyondUnicode()
        self.source = source
        super().__init__(self.construct)
        self.__cause__ = source


def written_token(text: str, start: int) -> str:
    """The anchor, alias or tag that starts at `start` in `text`, spelled as the block writes it.

    Args:
        text: The block, or the reader's buffer, which ends with a NUL.
        start: The index of the `&`, the `*` or the `!` the token starts with.
    """
    end = start
    if text.startswith('!<', start):
        # A verbatim tag is a URI, which may hold a `,` or a `]`, so it runs to its closing `>`, or to the end of the
        # line when it is never closed.
        while end < len(text) and text[end] not in _LINE_END_CHARACTERS and text[end] != '>':
            end += 1
        if end < len(text) and text[end] == '>':
            end += 1
    else:
        while end < len(text) and text[end] not in _TOKEN_END_CHARACTERS:
            end += 1
    return text[start:end]


class _AnyHandleMapping(dict[str, str]):
    """The tag handles a parser resolves a tag against, with every handle defined: an unknown one stands for itself."""

    def __contains__(self, handle: object) -> bool:
        return True

    def __missing__(self, handle: str) -> str:
        return handle


class BasicYamlParser(Parser):
    """ruamel.yaml's parser, taking a tag whose handle no directive defines as it takes `!` and `!!`.

    A directive is the only way to define a handle, and a directive is refused, so the parser would otherwise fail
    on `!e!x` with an error of its own, before `reader._peek_node_start` reaches the node, and
    report the tag ahead of a construct written above it. Taking every handle lets the tag reach that function as an
    event, refused in the order the block writes it, like `!!str`.
    """

    def select_tag_transform(self, tag: RuamelTag) -> None:
        """Make the tag resolve against every handle.

        Args:
            tag: The tag of the node the parser is on.
        """
        super().select_tag_transform(tag)
        tag.handles = _AnyHandleMapping(tag.handles)


class BasicYamlReader(Reader):
    """ruamel.yaml's reader, recording the first U+0085, U+2028 or U+2029 it moves over outside a quoted scalar.

    Attributes:
        quoted: Whether the scanner is inside a single- or double-quoted scalar, where those characters are text.
        separator: The first separator written outside a quoted scalar, or `None`.
    """

    quoted = False
    separator: RecordedRefusal | None = None

    def forward(self, length: int = 1) -> None:
        """Advance `length` characters, recording a line separator written outside a quoted scalar.

        Args:
            length: The number of characters to advance by.
        """
        # The reader ends a line at a `\n` or a lone `\r` only, as `core/lines.py` does, so the separators are not
        # breaks to it. The scanner still ends a line at them, which would read `a: 1<U+0085>b: 2` as two pairs, so
        # one is recorded here and the block is reported for it, like for any construct the scanner records.
        if not self.quoted and self.separator is None:
            for offset, character in enumerate(self.prefix(length)):
                if character in LINE_SEPARATORS:
                    super().forward(offset)
                    self.separator = RecordedRefusal(LineSeparator(character), self.get_mark())
                    super().forward(length - offset)
                    return
        super().forward(length)


class BasicYamlScanner(Scanner):
    r"""ruamel.yaml's scanner, reading the YAML 1.2 grammar and failing with a `ScannerError`.

    A block is accepted or refused by the YAML 1.2 grammar with two rules of the subset's own, and a refusal names
    the construct and where the scanner found it. A blank line before a block scalar's text may hold fewer
    spaces than the text, and a tab is never whitespace between tokens, in a flow collection too. The scanner also
    ends a plain scalar inside a flow collection at a `:` followed by a flow indicator, which YAML 1.2 does and
    ruamel.yaml does not.

    U+0085, U+2028 and U+2029 are text inside a quoted scalar, and a refusal anywhere else, which the reader records
    where it moves over one; `scan_flow_scalar` tells it where a quoted scalar is.

    A directive and a document marker are refused at their indicator, before anything after it is read, so the
    block's own text never reaches ruamel.yaml's directive scanner, whose version number conversion raises a plain
    `ValueError` for more digits than Python converts to an `int`, 4300 by default. Those refusals are
    errors of lorecraft's own, not a `ScannerError`, which `read_yaml` returns as the construct they carry, where
    it returns the scanner's problems as the facts they hold.

    An explicit key, an empty key, a flow collection spread over lines and a block scalar's indentation indicator
    are not refused where the scanner meets them. It records each in `refusals`, in the order the block writes them,
    for `read_yaml` to report once the read ends or fails. The scanner reads ahead of the parser, so
    raising at once would report a construct written below a tag or an anchor before the tag or the anchor. It
    holds `_flow_start`, where the outermost open flow collection begins, to tell a collection spread over lines.

    An anchor or an alias with no name, and a tag the scanner cannot read, are refused here too, as the anchor, alias
    or tag they are. The tag's refusal is chained from the scanner's error.

    A double-quoted `\U` escape above `U+10FFFF` is the one other place a plain Python exception escapes: `chr`
    raises a `ValueError`, or an `OverflowError` for one too large for a C `int`. It is refused here, at
    the escape, as `read_yaml` refuses every construct the subset leaves out.
    """

    def __init__(self, loader: object = None) -> None:
        """Start scanning outside any flow collection, with nothing recorded.

        Args:
            loader: The object ruamel.yaml's entry point passes in, which holds the reader.
        """
        super().__init__(loader)
        self._flow_start: StreamMark | None = None
        self.refusals: list[RecordedRefusal] = []

    def first_refusal(self) -> RecordedRefusal | None:
        """The first construct the scanner or the reader has recorded, in the order the text writes them, or `None`."""
        reader = self.reader
        if not isinstance(reader, BasicYamlReader):
            # SAFETY: the reader is declared on the scanner's base class; `_EventStream` always installs its own.
            raise Unreachable("the scanner is built with `basic_yaml`'s reader")
        recorded = [*self.refusals[:1], *([reader.separator] if reader.separator is not None else [])]
        if not recorded:
            return None
        return min(recorded, key=lambda refusal: refusal.mark.index)

    def fetch_directive(self) -> Never:
        """Refuse a directive, a `%` line, naming it by the `%` and the name that follows it.

        Raises:
            RefusedDirectiveError: Always: the subset holds no directive.
        """
        start_mark = self.reader.get_mark()
        length = 1
        while self.reader.peek(length) not in _DIRECTIVE_NAME_END_CHARACTERS:
            length += 1
        raise RefusedDirectiveError(self.reader.prefix(length), start_mark)

    def fetch_document_start(self) -> Never:
        """Refuse a `---` marker written inside the block.

        Raises:
            RefusedDocumentMarkerError: Always: the block is the body of one document, whose delimiters are not part of
                it.
        """
        self._refuse_document_marker()

    def fetch_document_end(self) -> Never:
        """Refuse a `...` marker written inside the block.

        Raises:
            RefusedDocumentMarkerError: Always: the block is the body of one document, whose delimiters are not part of
                it.
        """
        self._refuse_document_marker()

    def _refuse_document_marker(self) -> Never:
        """Refuse the three-character marker the reader is on.

        Raises:
            RefusedDocumentMarkerError: Always: the marker is not allowed inside the block.
        """
        raise RefusedDocumentMarkerError(self.reader.prefix(3), self.reader.get_mark())

    def scan_anchor(self, TokenClass: type[Token]) -> Token:
        """Scan an anchor or an alias, refusing one with no name as the anchor or alias it is.

        Args:
            TokenClass: The token to build, an anchor's or an alias's.

        Raises:
            RefusedAnchorError: An anchor has no name, or a name with a character the scanner rejects.
            RefusedAliasError: An alias has no name, or a name with a character the scanner rejects.
        """
        # The scanner ends a name at the first character `check_anchorname_char` rejects, such as U+FEFF, and fails
        # when that character is not one that may follow a name. The block's own spelling runs to the next token
        # end, so a character it rejects anywhere in it is the case the scanner would fail on.
        written = written_token(self.reader.buffer, self.reader.pointer)
        name = written[1:]
        if not name or not all(check_anchorname_char(character) for character in name):
            start_mark = self.reader.get_mark()
            if written[0] == '*':
                raise RefusedAliasError(name, start_mark)
            raise RefusedAnchorError(name, start_mark)
        token = super().scan_anchor(TokenClass)
        if not isinstance(token, Token):
            # SAFETY: the base method's return type is `Any`; it builds the token class it was given.
            raise Unreachable('ruamel.yaml scans an anchor into a token')
        return token

    def scan_tag(self) -> TagToken:
        """Scan a tag, refusing one the scanner cannot read as the tag it is.

        Raises:
            RefusedMalformedTagError: The scanner cannot read the tag, such as a verbatim tag left open or empty, a
                bad `%` escape, or a tag with no space after it.
        """
        start_mark = self.reader.get_mark()
        # The reader's buffer holds the whole block, ended by a NUL, and the pointer is where the tag starts.
        written = written_token(self.reader.buffer, self.reader.pointer)
        try:
            token = super().scan_tag()
        except ScannerError as exc:
            raise RefusedMalformedTagError(written, start_mark, source=exc) from exc
        if not isinstance(token, TagToken):
            # SAFETY: the base method's return type is `Any`; it builds a tag token.
            raise Unreachable('ruamel.yaml scans a tag into a tag token')
        return token

    def fetch_key(self) -> None:
        """Fetch a `?` that starts a key, and record it as an explicit key where a node may start."""
        # The scanner's flow context takes every `?` for a key. A `?` that follows a scalar, as in `[what?]` and
        # `[what ? x]`, is part of a plain scalar in YAML 1.2, and the scanner has stopped allowing a node by then,
        # so it is left to the parser. After `[`, `{`, `,` or the start of a block line, a node may start.
        if self.allow_simple_key:
            self.refusals.append(RecordedRefusal(ExplicitKey(), self.reader.get_mark()))
        super().fetch_key()

    def fetch_value(self) -> None:
        """Fetch a `:`, and record it as an empty key when no key was written before it."""
        # The scanner saves the start of every scalar that may be a simple key, and `:` finds it. With none saved,
        # and a key allowed here, the key is written as nothing. Where a key is not allowed, as after `a: b`, the
        # scanner fails with its own problem, which is a syntax error of the value, not an empty key.
        if self.flow_level not in self.possible_simple_keys and (self.flow_level or self.allow_simple_key):
            self.refusals.append(RecordedRefusal(EmptyKey(), self.reader.get_mark()))
        super().fetch_value()

    def fetch_flow_collection_start(self, TokenClass: type[Token], to_push: str) -> None:
        """Fetch a `[` or a `{`, remembering where the outermost flow collection opens.

        Args:
            TokenClass: The token to build, a sequence's or a mapping's start.
            to_push: The character the flow context records.
        """
        if self._flow_start is None:
            self._flow_start = self.reader.get_mark()
        super().fetch_flow_collection_start(TokenClass, to_push)

    def fetch_flow_collection_end(self, TokenClass: type[Token]) -> None:
        """Fetch a `]` or a `}`, forgetting where the outermost flow collection opened once it closes.

        Args:
            TokenClass: The token to build, a sequence's or a mapping's end.
        """
        super().fetch_flow_collection_end(TokenClass)
        if not self.flow_level:
            self._flow_start = None

    def scan_block_scalar_indicators(self, start_mark: StreamMark) -> tuple[bool | None, int | None]:
        """Scan a block scalar's chomping and indentation indicators, recording an indentation indicator.

        Args:
            start_mark: Where the scalar starts, for the scanner's own error messages.
        """
        chomping, increment = super().scan_block_scalar_indicators(start_mark)
        if chomping is not None and not isinstance(chomping, bool):
            # SAFETY: the base method's return type is `Any`; it reads `+` and `-` as a boolean
            raise Unreachable('the chomping indicator is a boolean or absent')
        if increment is not None and not isinstance(increment, int):
            # SAFETY: the base method's return type is `Any`; it reads a digit as an integer
            raise Unreachable('the indentation indicator is an integer or absent')
        if increment is not None:
            self.refusals.append(RecordedRefusal(IndentationIndicator(), start_mark))
        return chomping, increment

    def scan_flow_scalar_breaks(self, double: bool, start_mark: StreamMark) -> list[str]:
        """Scan the line breaks and blank lines inside a quoted scalar, refusing a marker that starts a line.

        Args:
            double: True for a double-quoted scalar; False for a single-quoted one.
            start_mark: Where the scalar starts, for the scanner's own error messages.

        Raises:
            RefusedDocumentMarkerError: A line of the scalar starts with a `---` or `...` marker.
        """
        # ruamel.yaml refuses a marker on a continuation line itself, in its own words, and the format refuses
        # every marker the same way, so the loop is its own with that one check changed.
        chunks: list[str] = []
        while True:
            if self.reader.prefix(3) in ('---', '...') and self.reader.peek(3) in _SPACE_CHARACTERS:
                self._refuse_document_marker()
            while self.reader.peek() in ' \t':
                self.reader.forward()
            if self.reader.peek() not in '\r\n':
                return chunks
            chunks.append(self.scan_line_break())

    def scan_flow_scalar(self, style: str) -> Token:
        """Scan a single- or double-quoted scalar, inside which a line separator is text.

        Args:
            style: The quote the scalar is written with.
        """
        self.reader.quoted = True
        try:
            return super().scan_flow_scalar(style)
        finally:
            self.reader.quoted = False

    def scan_flow_scalar_spaces(self, double: bool, start_mark: StreamMark) -> list[str]:
        """Scan the spaces of a quoted scalar, which stay text before a line separator, as the separator does.

        Args:
            double: True for a double-quoted scalar; False for a single-quoted one.
            start_mark: Where the scalar starts, for the scanner's own error messages.
        """
        length = 0
        while self.reader.peek(length) in ' \t':
            length += 1
        if self.reader.peek(length) in LINE_SEPARATORS:
            # ruamel.yaml folds the spaces and the separator into one line break. Here the separator is text.
            whitespaces = self.reader.prefix(length)
            self.reader.forward(length)
            return [whitespaces]
        return _strings(super().scan_flow_scalar_spaces(double, start_mark))

    # The two methods below are rules of the subset's own, not ruamel.yaml's reading of YAML 1.2.

    def scan_block_scalar_indentation(self) -> tuple[list[str], int, StreamMark]:
        """Scan the blank lines before a block scalar's text, and the widest indent among them.

        A blank line holding fewer spaces than the text's indent is accepted.
        """
        # ruamel.yaml raises "more indented follow up line than first in a block scalar" for a leading blank line
        # that holds spaces, which a block scalar written under an auto-indenting editor often has.
        chunks: list[str] = []
        max_indent = 0
        end_mark = self._current_mark()
        while self.reader.peek() in ' \r\n':
            if self.reader.peek() != ' ':
                chunks.append(self.scan_line_break())
                end_mark = self._current_mark()
            else:
                self.reader.forward()
                max_indent = max(max_indent, int(self.reader.column))
        return chunks, max_indent, end_mark

    def _current_mark(self) -> StreamMark:
        """Where the reader is."""
        mark = self.reader.get_mark()
        if not isinstance(mark, StreamMark):
            # SAFETY: the reader's `get_mark` is typed as optional; a reader over a string always marks its position.
            raise Unreachable('the reader marks every position')
        return mark

    def scan_flow_scalar_non_spaces(self, double: bool, start_mark: StreamMark) -> list[str]:
        """Scan the text of a quoted scalar up to its next space, a line separator taken as text.

        Args:
            double: True for a double-quoted scalar, whose backslash escapes are decoded; False for a single-quoted one.
            start_mark: Where the scalar starts, for the scanner's own error messages.

        Raises:
            ScannerError: An escape is not one YAML knows, or is written with a digit that is not hexadecimal.
            RefusedEscapeError: An escape names no Unicode character.
        """
        # This is ruamel.yaml's method as of 0.19.1 with two changes: a line separator is not a character the text
        # stops at, and a backslash before one is an unknown escape, not an escaped line break.
        chunks: list[str] = []
        while True:
            length = 0
            while self.reader.peek(length) not in _QUOTED_TEXT_END_CHARACTERS:
                length += 1
            if length != 0:
                chunks.append(self.reader.prefix(length))
                self.reader.forward(length)
            character = self.reader.peek()
            if not double and character == "'" and self.reader.peek(1) == "'":
                chunks.append("'")
                self.reader.forward(2)
            elif (double and character == "'") or (not double and character in '"\\'):
                chunks.append(character)
                self.reader.forward()
            elif double and character == '\\':
                self.reader.forward()
                character = self.reader.peek()
                if character in self.ESCAPE_REPLACEMENTS:
                    chunks.append(self.ESCAPE_REPLACEMENTS[character])
                    self.reader.forward()
                elif character in self.ESCAPE_CODES:
                    digits = self.ESCAPE_CODES[character]
                    self.reader.forward()
                    for offset in range(digits):
                        if self.reader.peek(offset) not in '0123456789ABCDEFabcdef':
                            raise ScannerError(
                                'while scanning a double-quoted scalar',
                                start_mark,
                                f'expected escape sequence of {digits:d} '
                                f'hexdecimal numbers, but found {self.reader.peek(offset)!r}',
                                self.reader.get_mark(),
                            )
                    try:
                        chunks.append(chr(int(self.reader.prefix(digits), 16)))
                    except (ValueError, OverflowError) as exc:
                        # The digits are checked to be hexadecimal, but not that the code point they name is at most
                        # U+10FFFF, so `chr` raises: a ValueError for `\U00110000`, and for `\UFFFFFFFF`, which does
                        # not fit a C int, an OverflowError on the interpreters that convert the argument first. The
                        # reader is on the escape's digits, so its mark is on the escape's line.
                        raise RefusedEscapeError(self.reader.get_mark(), source=exc) from exc
                    self.reader.forward(digits)
                elif character in '\n\r':
                    self.scan_line_break()
                    chunks.extend(_strings(self.scan_flow_scalar_breaks(double, start_mark)))
                else:
                    raise ScannerError(
                        'while scanning a double-quoted scalar',
                        start_mark,
                        f'found unknown escape character {character!r}',
                        self.reader.get_mark(),
                    )
            else:
                return chunks

    def scan_to_next_token(self) -> None:
        r"""Skip spaces, comments and line breaks to the next token; a tab is no whitespace, in a flow collection too.

        A tab is a character that cannot start a token, so `[a,\tb]` is refused. Where the next token is on a later
        line than the one the flow collection it is in opened on, the collection is recorded as a refusal.
        """
        # ruamel.yaml skips a tab inside a flow collection, as YAML 1.2 allows; the subset refuses it, so that a tab
        # is never whitespace between tokens.
        if self.reader.index == 0 and self.reader.peek() == '\ufeff':
            self.reader.forward()
        found = False
        while not found:
            while self.reader.peek() == ' ':
                self.reader.forward()
            if self.reader.peek() == '#':
                while self.reader.peek() not in _LINE_END_CHARACTERS:
                    self.reader.forward()
            if self.scan_line_break():
                if not self.flow_level:
                    self.allow_simple_key = True
            else:
                found = True
        # The next token is the first thing the collection holds on a line below the one it opened on, or the end of
        # the block, where an unclosed one stops. A construct written between the opening and the line break, such as
        # the tag of `a: [b, !x c,` / `  d]`, was recorded or met before this point, so it is reported first, on the
        # same line.
        if self._flow_start is not None and self.reader.line != self._flow_start.line:
            # This runs for every token below the opening line, and the collection is refused once.
            if not any(refusal.mark is self._flow_start for refusal in self.refusals):
                self.refusals.append(RecordedRefusal(SpreadFlowCollection(), self._flow_start))

    def check_value(self) -> bool:
        """Whether the `:` the reader is on is a value indicator, which includes one before a flow indicator."""
        # YAML 1.2 reads a `:` followed by `,`, `[`, `]`, `{` or `}` inside a flow collection as a value indicator,
        # which ruamel.yaml reads only as YAML 1.1. Without it, `scan_plain` below ends the scalar at that `:` and no
        # token starts there.
        if self.flow_level and self.reader.peek(1) in ',[]{}':
            return True
        return bool(super().check_value())

    def scan_plain(self) -> ScalarToken:
        """Scan a plain scalar, which ends at a `:` before a flow indicator inside a flow collection."""
        # YAML 1.2 ends a plain scalar inside a flow collection at a `:` followed by `,`, `[`, `]`, `{` or `}`, which
        # ruamel.yaml misses: it keeps the `:` in the scalar, so `{c:[d]}` and `[a:, b]` would read `c` and `a` as
        # part of their values instead of as keys.
        chunks: list[str] = []
        start_mark = self.reader.get_mark()
        end_mark = start_mark
        indent = self.indent + 1
        spaces: list[str] = []
        while True:
            length = 0
            if self.reader.peek() == '#':
                break
            while True:
                ch = self.reader.peek(length)
                colon_ends_scalar = ch == ':' and self.reader.peek(length + 1) in (
                    _SPACE_CHARACTERS + (',[]{}' if self.flow_level else '')
                )
                flow_indicator = self.flow_level and ch in ',[]{}'
                if ch in _SPACE_CHARACTERS or colon_ends_scalar or flow_indicator:
                    break
                length += 1
            if length == 0:
                break
            self.allow_simple_key = False
            chunks.extend(spaces)
            chunks.append(self.reader.prefix(length))
            self.reader.forward(length)
            end_mark = self.reader.get_mark()
            # It returns nothing, rather than a list, when the spaces end at a document marker.
            scanned = self.scan_plain_spaces(indent, start_mark)
            spaces = [] if scanned is None else _strings(scanned)
            if not spaces or self.reader.peek() == '#' or (not self.flow_level and self.reader.column < indent):
                break
        return ScalarToken(''.join(chunks), True, start_mark, end_mark)


def _strings(chunks: object) -> list[str]:
    """The text pieces an untyped ruamel.yaml scanner method returned, checked to be a list of strings.

    Args:
        chunks: What the scanner method returned.
    """
    if not isinstance(chunks, list):
        # SAFETY: the scanner method is untyped; it builds a list of the pieces it scanned.
        raise Unreachable('ruamel.yaml scans text into a list of strings')
    strings: list[str] = []
    for chunk in chunks:
        if not isinstance(chunk, str):
            # SAFETY: the scanner appends only slices of the block's text, which are strings.
            raise Unreachable('ruamel.yaml scans text into a list of strings')
        strings.append(chunk)
    return strings
