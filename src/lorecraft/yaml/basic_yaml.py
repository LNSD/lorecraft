"""The constructs the YAML subset leaves out, as the errors and records ruamel.yaml's scanner reports them by.

A construct the format leaves out is either an error raised where the scanner or the parser meets it, a
`Refused...Error`, or a `RecordedRefusal` the scanner notes and reads on from, because it reads ahead of the parser.
Each carries the `mark` where it is written and the `problem` as `FM002` words it. The module also holds the
subclasses of ruamel.yaml's reader and parser that record the line separators the format does not treat as breaks
and that take every tag handle.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Final, get_args

from ruamel.yaml.error import StreamMark
from ruamel.yaml.parser import Parser
from ruamel.yaml.reader import Reader
from ruamel.yaml.scanner import ScannerError
from ruamel.yaml.tag import Tag

from lorecraft.core.error import Error

LINE_SEPARATORS: Final[str] = '\x85\u2028\u2029'
"""The characters other YAML grammars end a line at, which `core/lines.py` does not: U+0085, U+2028 and U+2029."""

MERGE_KEY: Final[str] = '<<'
"""The plain key YAML 1.1 reads as a merge: the entries of the mapping an alias names join the mapping."""

_NOT_ALLOWED: Final[str] = 'which frontmatter does not allow'
"""How the problem of a refused construct ends: `found <construct>, which frontmatter does not allow`."""


SPACE_CHARACTERS: Final[str] = '\0 \t\r\n'
"""The characters that end a plain scalar: the end of the text, a space or tab, or a line break."""

LINE_END_CHARACTERS: Final[str] = '\0\r\n'
"""The characters that end a line: the end of the text, or a line break."""

_TOKEN_END_CHARACTERS: Final[str] = SPACE_CHARACTERS + ',[]{}'
"""The characters that end an anchor, an alias or a tag as a block writes it: whitespace or a flow indicator."""


class RecordedConstruct(StrEnum):
    """The constructs the scanner records without stopping, each with how the problem names it."""

    EXPLICIT_KEY = 'an explicit key'
    EMPTY_KEY = 'an empty key'
    INDENTATION_INDICATOR = 'a block scalar indentation indicator'
    SPREAD_FLOW_COLLECTION = 'a flow collection spread over lines'
    # Its problem is not worded from this value: `RecordedRefusal.problem` names the character.
    LINE_SEPARATOR = 'a line separator outside a quoted scalar'


@dataclass(frozen=True, slots=True)
class RecordedRefusal:
    """A construct frontmatter leaves out, which the scanner met and recorded without stopping.

    Attributes:
        construct: Which construct it is.
        mark: Where it is written.
        character: The line separator, for a `LINE_SEPARATOR`, and `None` for any other construct.
    """

    construct: RecordedConstruct
    mark: StreamMark
    character: str | None = None

    @property
    def problem(self) -> str:
        """The problem as `FM002` words it, `found <construct>, which frontmatter does not allow` by default."""
        if self.character is not None:
            return f'the block holds U+{ord(self.character):04X}, which is not a line break here'
        return f'found {self.construct}, {_NOT_ALLOWED}'

    @property
    def help(self) -> str | None:
        """What to do about it, or `None` where there is no more to say."""
        if self.character is not None:
            return 'Use a line feed, or remove it'
        return None


class RefusedDirectiveError(Error):
    """A directive, a `%` line, is written.

    Attributes:
        name: The `%` and the name that follows it.
        mark: Where the directive is written.
        problem: The problem as `FM002` words it.
    """

    name: str
    mark: StreamMark
    problem: str

    def __init__(self, name: str, mark: StreamMark) -> None:
        self.name = name
        self.mark = mark
        self.problem = f'found the directive {name}, {_NOT_ALLOWED}'
        super().__init__(self.problem)


class RefusedDocumentMarkerError(Error):
    """A `---` or `...` marker is written, though the block is the body of one document.

    Attributes:
        marker: The three characters of the marker.
        mark: Where the marker is written.
        problem: The problem as `FM002` words it.
    """

    marker: str
    mark: StreamMark
    problem: str

    def __init__(self, marker: str, mark: StreamMark) -> None:
        self.marker = marker
        self.mark = mark
        self.problem = f'found the document marker {marker}, {_NOT_ALLOWED}'
        super().__init__(self.problem)


class RefusedAliasError(Error):
    """A value is an alias.

    Attributes:
        anchor: The anchor's name, without the `*`.
        mark: Where the alias is written.
        problem: The problem as `FM002` words it.
    """

    anchor: str
    mark: StreamMark
    problem: str

    def __init__(self, anchor: str, mark: StreamMark) -> None:
        self.anchor = anchor
        self.mark = mark
        self.problem = f'found the alias *{anchor}, {_NOT_ALLOWED}'
        super().__init__(self.problem)


class RefusedAnchorError(Error):
    """A value carries an anchor.

    Attributes:
        anchor: The anchor's name, without the `&`.
        mark: Where the anchor is written.
        problem: The problem as `FM002` words it.
    """

    anchor: str
    mark: StreamMark
    problem: str

    def __init__(self, anchor: str, mark: StreamMark) -> None:
        self.anchor = anchor
        self.mark = mark
        self.problem = f'found the anchor &{anchor}, {_NOT_ALLOWED}'
        super().__init__(self.problem)


class RefusedTagError(Error):
    """A value carries a tag, the non-specific `!` included.

    Attributes:
        tag: The tag as the block writes it.
        mark: Where the tag is written.
        problem: The problem as `FM002` words it.
    """

    tag: str
    mark: StreamMark
    problem: str

    def __init__(self, tag: str, mark: StreamMark) -> None:
        self.tag = tag
        self.mark = mark
        self.problem = f'found the tag {tag!r}, {_NOT_ALLOWED}'
        super().__init__(self.problem)


class RefusedMergeKeyError(Error):
    """A mapping writes the plain key `<<`, which YAML 1.1 reads as a merge.

    Attributes:
        mark: Where the key is written.
        problem: The problem as `FM002` words it.
    """

    mark: StreamMark
    problem: str

    def __init__(self, mark: StreamMark) -> None:
        self.mark = mark
        self.problem = f'found the merge key {MERGE_KEY}, {_NOT_ALLOWED}'
        super().__init__(self.problem)


class RefusedCollectionKeyError(Error):
    """A mapping's key is a collection, not a string.

    Attributes:
        mark: Where the key is written.
        problem: The problem as `FM002` words it.
    """

    mark: StreamMark
    problem: str

    def __init__(self, mark: StreamMark) -> None:
        self.mark = mark
        self.problem = f'found a collection as a key, {_NOT_ALLOWED}'
        super().__init__(self.problem)


class RefusedNonStringKeyError(Error):
    """A mapping's key is a scalar that decodes to null, a boolean or a number, not a string.

    Attributes:
        key: The key as written, which is empty for a key written as nothing at all.
        mark: Where the key is written.
        problem: The problem as `FM002` words it.
    """

    key: str
    mark: StreamMark
    problem: str

    def __init__(self, key: str, mark: StreamMark) -> None:
        self.key = key
        self.mark = mark
        self.problem = f'found the non-string key {key}, {_NOT_ALLOWED}'
        super().__init__(self.problem)


class RefusedFlowBlockError(Error):
    """The whole block is a flow collection, not a block mapping.

    Attributes:
        mark: Where the flow collection starts.
        problem: The problem as `FM002` words it.
    """

    mark: StreamMark
    problem: str

    def __init__(self, mark: StreamMark) -> None:
        self.mark = mark
        self.problem = f'found a flow collection as the block, {_NOT_ALLOWED}'
        super().__init__(self.problem)


class RefusedFlowNestedCollectionError(Error):
    """A flow collection holds a collection.

    Attributes:
        mark: Where the inner collection starts.
        problem: The problem as `FM002` words it.
    """

    mark: StreamMark
    problem: str

    def __init__(self, mark: StreamMark) -> None:
        self.mark = mark
        self.problem = f'found a collection inside a flow collection, {_NOT_ALLOWED}'
        super().__init__(self.problem)


class RefusedNestedBlockSequenceError(Error):
    """A block sequence holds a block sequence as an item.

    Attributes:
        mark: Where the inner sequence starts.
        problem: The problem as `FM002` words it.
    """

    mark: StreamMark
    problem: str

    def __init__(self, mark: StreamMark) -> None:
        self.mark = mark
        self.problem = f'found a block sequence as an item of a block sequence, {_NOT_ALLOWED}'
        super().__init__(self.problem)


class RefusedMalformedTagError(Error):
    """A tag the scanner cannot read.

    That is a tag such as a verbatim tag left open or empty, a bad `%` escape, or a tag with no space after it.

    Attributes:
        tag: The tag as the block writes it.
        mark: Where the tag is written.
        problem: The problem as `FM002` words it.
        source: The scanner's error.
    """

    tag: str
    mark: StreamMark
    problem: str
    source: ScannerError

    def __init__(self, tag: str, mark: StreamMark, *, source: ScannerError) -> None:
        self.tag = tag
        self.mark = mark
        self.problem = f'found the tag {tag!r}, {_NOT_ALLOWED}'
        self.source = source
        super().__init__(self.problem)
        self.__cause__ = source


class RefusedEscapeError(Error):
    """A double-quoted escape names a code point above `U+10FFFF`, which `chr` cannot build.

    Attributes:
        mark: Where the escape is written.
        problem: The problem as `FM002` words it.
        source: The failure `chr` raised.
    """

    mark: StreamMark
    problem: str
    source: ValueError | OverflowError

    def __init__(self, mark: StreamMark, *, source: ValueError | OverflowError) -> None:
        self.mark = mark
        self.problem = f'found an escape that names no Unicode character, {_NOT_ALLOWED}'
        self.source = source
        super().__init__(self.problem)
        self.__cause__ = source


type Refusal = (
    RefusedDirectiveError
    | RefusedDocumentMarkerError
    | RefusedAliasError
    | RefusedAnchorError
    | RefusedTagError
    | RefusedMalformedTagError
    | RefusedMergeKeyError
    | RefusedCollectionKeyError
    | RefusedNonStringKeyError
    | RefusedFlowBlockError
    | RefusedFlowNestedCollectionError
    | RefusedNestedBlockSequenceError
    | RefusedEscapeError
)
"""Every construct frontmatter leaves out that stops the read where it is met. Each carries the `mark` where it is
written and the `problem` as `FM002` words it, so the decoder reads them alike."""

REFUSALS: Final = get_args(Refusal.__value__)
"""The classes of `Refusal`, for the `except` that catches them."""


class _AnyHandleMapping(dict[str, str]):
    """The tag handles a parser resolves a tag against, with every handle defined: an unknown one stands for itself."""

    def __contains__(self, handle: object) -> bool:
        return True

    def __missing__(self, handle: str) -> str:
        return handle


class BasicYamlParser(Parser):
    """ruamel.yaml's parser, taking a tag whose handle no directive defines as it takes `!` and `!!`.

    A directive is the only way to define a handle, and a directive is refused, so the parser would otherwise fail
    on `!e!x` with an error of its own, before `project.syntax.frontmatter._peek_node_start` reaches the node, and
    report the tag ahead of a construct written above it. Taking every handle lets the tag reach that function as an
    event, refused in the order the block writes it, like `!!str`.
    """

    def select_tag_transform(self, tag: Tag) -> None:
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
                    self.separator = RecordedRefusal(
                        RecordedConstruct.LINE_SEPARATOR, self.get_mark(), character=character
                    )
                    super().forward(length - offset)
                    return
        super().forward(length)


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
        while end < len(text) and text[end] not in LINE_END_CHARACTERS and text[end] != '>':
            end += 1
        if end < len(text) and text[end] == '>':
            end += 1
    else:
        while end < len(text) and text[end] not in _TOKEN_END_CHARACTERS:
            end += 1
    return text[start:end]
