"""Reading a YAML text into a tree of values, and refusing what the subset leaves out.

`read_yaml` is the one way a YAML text becomes a value. The events come from ruamel.yaml's pure-Python reader, scanner
and parser, and the tree is built from them here, never by ruamel.yaml's loader or constructor, so no tag ruamel.yaml
resolves and no type it constructs is ever involved. The text is read lazily and to its end, so a refused construct or
a syntax error anywhere in it is reported, and the constructs the scanner recorded by the time a read fails are the
ones written above the failure.

A read that fails returns the first problem the text writes, as a `YamlProblem`, never an exception: the construct the
scanner recorded above the one the read stopped on comes first, whichever the library met first.
"""

from typing import assert_never, overload

from ruamel.yaml.error import MarkedYAMLError, StreamMark
from ruamel.yaml.reader import ReaderError

from lorecraft.core.error import Unreachable
from lorecraft.core.num import NonZeroUnsignedInt

from ._events import (
    Alias,
    Boundary,
    CollectionStart,
    MappingStart,
    NodeStart,
    ScalarStart,
    SequenceStart,
    _EventStream,
    code_point,
    parse_failure,
)
from .basic_yaml import (
    MERGE_KEY,
    RecordedRefusal,
    RefusedAliasError,
    RefusedAnchorError,
    RefusedCollectionKeyError,
    RefusedFlowBlockError,
    RefusedFlowNestedCollectionError,
    RefusedMergeKeyError,
    RefusedNestedBlockSequenceError,
    RefusedNonStringKeyError,
    RefusedTagError,
    _RefusalError,
)
from .problem import (
    ControlCharacterProblem,
    NestingTooDeepProblem,
    RefusedConstructProblem,
    SyntaxErrorProblem,
    YamlProblem,
)
from .scalar import resolve_plain_scalar
from .tree import YamlKey, YamlMapping, YamlPosition, YamlScalar, YamlScalarValue, YamlSequence, YamlValue


def read_yaml(text: str) -> YamlValue | None | YamlProblem:
    """Read a YAML text, which holds one document, into its tree.

    Every value is read to its end, so a refused construct or a syntax error anywhere in the text is reported rather
    than hidden behind the document's shape. Line and column positions count from the first character of `text`.

    Args:
        text: The YAML text to read, line endings kept.

    Returns:
        The document's root; `None` when the text holds no document, because it is empty or holds only comments; or
        the first problem the text writes, when it cannot be read.
    """
    stream = _EventStream(text)
    try:
        root = _read_document(stream)
    except ReaderError as exc:
        # The reader checks every character as it is built, so a control character fails before the first event.
        return ControlCharacterProblem(code=code_point(exc), index=exc.position)
    except _RefusalError as exc:
        # The read stopped at a construct the subset leaves out. The scanner reads ahead of the parser, so it may
        # have recorded one written above it, which is the one the text is reported for.
        return _refused(_first_refusal(stream, stopped=exc))
    except MarkedYAMLError as exc:
        # Every other `MarkedYAMLError` is ruamel.yaml's own. The scanner reads ahead of the parser, so a construct
        # it recorded is written above whatever the parser or the scanner failed on.
        recorded = _first_refusal(stream)
        if recorded is not None:
            return _refused(recorded)
        failure = parse_failure(exc)
        return SyntaxErrorProblem(
            problem=failure.problem,
            context=failure.context,
            position=_position_of_mark(failure.problem_mark),
            context_position=_position_of_mark(failure.context_mark),
        )
    except RecursionError:
        # The value is read with one call per level of nesting, so only a deeply nested text reaches the
        # interpreter's limit. By the time this clause runs the stack has unwound to this frame, so there is room
        # to go on, and the half-read parser is dropped. A construct the scanner recorded above the depth is
        # reported instead, on its position.
        recorded = _first_refusal(stream)
        if recorded is not None:
            return _refused(recorded)
        return NestingTooDeepProblem()
    # The text was read to its end, so every construct the scanner recorded is written above the end.
    recorded = _first_refusal(stream)
    if recorded is not None:
        return _refused(recorded)
    return root


@overload
def _first_refusal(stream: _EventStream, *, stopped: _RefusalError) -> RecordedRefusal | _RefusalError: ...
@overload
def _first_refusal(stream: _EventStream, *, stopped: None = None) -> RecordedRefusal | None: ...
def _first_refusal(
    stream: _EventStream, *, stopped: _RefusalError | None = None
) -> RecordedRefusal | _RefusalError | None:
    """The refusal a failed or finished read is reported for: the first construct the text writes.

    The scanner reads ahead of the parser, so a construct it recorded may be written above the one the read stopped
    on; the recorded one wins unless it is written below.

    Args:
        stream: The text's events, read as far as the read went.
        stopped: The refusal the read stopped on, if it did.
    """
    recorded = stream.first_refusal()
    if recorded is not None and (stopped is None or recorded.mark.index <= stopped.mark.index):
        return recorded
    return stopped


def _position_of_mark(mark: StreamMark | None) -> YamlPosition | None:
    """A mark of the parser's error as a position, or `None` where it gave none.

    Args:
        mark: The mark, which counts its line and column from 0.
    """
    if mark is None:
        return None
    return YamlPosition(NonZeroUnsignedInt(mark.line + 1), NonZeroUnsignedInt(mark.column + 1))


def _refused(refusal: RecordedRefusal | _RefusalError) -> RefusedConstructProblem:
    """The problem of a construct the subset leaves out.

    Args:
        refusal: The construct, as the scanner recorded it or as the read stopped on it.
    """
    position = _position_of_mark(refusal.mark)
    if position is None:
        # SAFETY: a refusal is marked where it is written.
        raise Unreachable('a refused construct has a mark')
    return RefusedConstructProblem(construct=refusal.construct, position=position)


def _position_of(node: NodeStart) -> YamlPosition:
    """Where a node starts, as the tree states it: one-based.

    Args:
        node: The event that starts the node.
    """
    mark = node.mark
    return YamlPosition(NonZeroUnsignedInt(mark.line + 1), NonZeroUnsignedInt(mark.column + 1))


def _read_document(parser: _EventStream) -> YamlValue | None:
    """Read the text's one document, if any.

    Args:
        parser: The text's parser, before its first event is read.

    Raises:
        MarkedYAMLError: The text is not valid YAML.
        RefusedFlowBlockError: The whole text is a flow collection.
        RefusedAliasError: The text is an alias.
        RefusedAnchorError: The text carries an anchor.
        RefusedTagError: The text carries a tag.
        RefusedCollectionKeyError: A key is a collection.
        RefusedNonStringKeyError: A key is a scalar that reads as something other than a string.
        RefusedMergeKeyError: A key is the plain merge key.
        RefusedFlowNestedCollectionError: A flow collection holds a collection.
        RefusedNestedBlockSequenceError: A block sequence holds a block sequence as an item.
        RefusedDirectiveError, RefusedDocumentMarkerError, RefusedMalformedTagError, RefusedEscapeError: The
            scanner refuses a directive, a document marker, a tag it cannot read or an escape where it reads it, and
            `RefusedAnchorError` and `RefusedAliasError` an anchor or an alias with no name.
    """
    parser.get_event()  # The stream's start.
    if parser.check_boundary(Boundary.STREAM_END):
        # An empty text, or one holding only comments, has no document at all.
        return None
    parser.get_event()  # The document's start.
    first = _peek_node_start(parser)
    if not isinstance(first, ScalarStart) and first.flow:
        raise RefusedFlowBlockError(first.mark)
    root = _read_value(parser)
    parser.get_event()  # The document's end.
    if not parser.check_boundary(Boundary.STREAM_END):
        # SAFETY: a second document starts with a `---` or a `...` marker, which the scanner refuses where it stands.
        raise Unreachable('the scanner refuses every document marker')
    return root


def _peek_node_start(parser: _EventStream) -> NodeStart:
    """The event the next value starts with, left unread, once it is known to use nothing the subset leaves out.

    Args:
        parser: The parser, whose next event starts a value.

    Raises:
        RefusedAliasError: The value is an alias, marked where it is written.
        RefusedAnchorError: The value carries an anchor.
        RefusedTagError: The value carries a tag.
    """
    event = parser.peek_event()
    if isinstance(event, Alias):
        raise RefusedAliasError(event.anchor, event.mark)
    if isinstance(event, Boundary):
        # SAFETY: only an end event or a document event is left, and the parser never gives one where a value starts.
        raise Unreachable(f'{event.name} where a value starts')
    if event.anchor is not None:
        raise RefusedAnchorError(event.anchor, event.mark)
    if event.tag is not None:
        raise RefusedTagError(event.tag, event.mark)
    return event


def _read_value(parser: _EventStream) -> YamlValue:
    """Read one value and everything in it.

    Args:
        parser: The parser, whose next event starts the value.

    Raises:
        MarkedYAMLError: The value is not valid YAML.
        RefusedAliasError: The value is an alias, or one in a collection it holds is.
        RefusedAnchorError: The value, or one in a collection it holds, carries an anchor.
        RefusedTagError: The value, or one in a collection it holds, carries a tag.
        RefusedCollectionKeyError: A key in the value is a collection.
        RefusedNonStringKeyError: A key in the value is not a string.
        RefusedMergeKeyError: A key in the value is the plain merge key.
        RefusedFlowNestedCollectionError: A flow collection in the value holds a collection.
        RefusedNestedBlockSequenceError: A block sequence in the value holds a block sequence as an item.
        RefusedMalformedTagError, RefusedEscapeError: The scanner cannot read a tag or an escape in the value.
    """
    event = _peek_node_start(parser)
    match event:
        case MappingStart():
            return _read_mapping(parser, event)
        case SequenceStart():
            return _read_sequence(parser, event)
        case ScalarStart():
            parser.get_event()
            return YamlScalar(_scalar_value(event), _position_of(event))
        case _:
            assert_never(event)


def _read_mapping(parser: _EventStream, start: MappingStart) -> YamlMapping:
    """Read one mapping, every pair in the order it is written, a repeated key once per occurrence.

    Args:
        parser: The parser, whose next event starts the mapping.
        start: The event that starts it, which says whether it is written in flow style.

    Raises:
        MarkedYAMLError: The mapping is not valid YAML.
        RefusedCollectionKeyError: A key is a collection.
        RefusedNonStringKeyError: A key is a scalar that reads as something other than a string.
        RefusedMergeKeyError: A key is the plain merge key.
        RefusedFlowNestedCollectionError: A value is a collection inside a flow mapping.
        RefusedAliasError, RefusedAnchorError, RefusedTagError: A key or a value is an alias, or carries an anchor
            or a tag.
        RefusedMalformedTagError, RefusedEscapeError: The scanner cannot read a tag or an escape in the mapping.
    """
    parser.get_event()  # The mapping's start.
    entries: list[tuple[YamlKey, YamlValue]] = []
    while not parser.check_boundary(Boundary.MAPPING_END):
        key = _read_key(parser)
        _refuse_nested_collection(parser, start)
        entries.append((key, _read_value(parser)))
    parser.get_event()  # The mapping's end.
    return YamlMapping(tuple(entries), _position_of(start))


def _read_sequence(parser: _EventStream, start: SequenceStart) -> YamlSequence:
    """Read one sequence, every item in the order it is written.

    Args:
        parser: The parser, whose next event starts the sequence.
        start: The event that starts it, which says whether it is written in flow style.

    Raises:
        MarkedYAMLError: An item is not valid YAML.
        RefusedFlowNestedCollectionError: An item is a collection inside a flow sequence.
        RefusedNestedBlockSequenceError: An item is a block sequence inside a block sequence.
        RefusedAliasError, RefusedAnchorError, RefusedTagError: An item is an alias, or carries an anchor or a tag.
        RefusedCollectionKeyError, RefusedNonStringKeyError, RefusedMergeKeyError: A mapping among the items has
            such a key.
        RefusedMalformedTagError, RefusedEscapeError: The scanner cannot read a tag or an escape in the sequence.
    """
    parser.get_event()  # The sequence's start.
    items: list[YamlValue] = []
    while not parser.check_boundary(Boundary.SEQUENCE_END):
        _refuse_nested_collection(parser, start)
        items.append(_read_value(parser))
    parser.get_event()  # The sequence's end.
    return YamlSequence(tuple(items), _position_of(start))


def _read_key(parser: _EventStream) -> YamlKey:
    """Read one key of a mapping, which must be a scalar that reads as a string.

    Args:
        parser: The parser, whose next event starts the key.

    Raises:
        RefusedAliasError: The key is an alias.
        RefusedAnchorError: The key carries an anchor.
        RefusedTagError: The key carries a tag.
        RefusedCollectionKeyError: The key is a collection.
        RefusedNonStringKeyError: The key is a scalar that reads as something other than a string.
        RefusedMergeKeyError: The key is the plain merge key.
    """
    event = _peek_node_start(parser)
    if not isinstance(event, ScalarStart):
        raise RefusedCollectionKeyError(event.mark)
    parser.get_event()
    name = _scalar_value(event)
    mark = event.mark
    if not isinstance(name, str):
        raise RefusedNonStringKeyError(event.text, mark)
    if event.plain and name == MERGE_KEY:
        # A plain `<<` is YAML 1.1's merge key, which pulls in the entries of the mapping an alias names.
        raise RefusedMergeKeyError(mark)
    return YamlKey(name, _position_of(event))


def _refuse_nested_collection(parser: _EventStream, parent: CollectionStart) -> None:
    """Refuse the next value when it is a collection `parent` does not hold.

    A flow collection holds no collection, and a block sequence holds no block sequence. A block mapping is the item
    a block sequence of records is made of, and a flow collection is one line of scalars, so those stay.

    Args:
        parser: The parser, whose next event starts a value of `parent`.
        parent: The event that started the collection the value belongs to.

    Raises:
        RefusedAliasError: The value is an alias.
        RefusedAnchorError: The value carries an anchor.
        RefusedTagError: The value carries a tag.
        RefusedFlowNestedCollectionError: The value is a collection inside a flow collection.
        RefusedNestedBlockSequenceError: The value is a block sequence that is an item of a block sequence.
    """
    event = _peek_node_start(parser)
    if isinstance(event, ScalarStart):
        return
    if parent.flow:
        raise RefusedFlowNestedCollectionError(event.mark)
    if isinstance(parent, SequenceStart) and isinstance(event, SequenceStart) and not event.flow:
        raise RefusedNestedBlockSequenceError(event.mark)


def _scalar_value(event: ScalarStart) -> YamlScalarValue:
    """What a scalar reads as: its text, unless it is plain and its whole text is a core schema null, bool or number.

    Args:
        event: The scalar's event, which carries no tag.
    """
    # A quoted scalar, and a literal `|` or folded `>` block, is not plain; only a plain one is resolved.
    if not event.plain:
        return event.text
    return resolve_plain_scalar(event.text)
