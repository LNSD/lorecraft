"""What a refused YAML construct is called in lorecraft's words, as `LC202` reports it.

`lorecraft.yaml` names each construct the subset leaves out as a type and never words it; this module words each as
`found <construct>, which frontmatter does not allow`, and a line separator as the character the block holds.
"""

from typing import Final, assert_never

from lorecraft.yaml.problem import (
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

_NOT_ALLOWED: Final[str] = 'which frontmatter does not allow'
"""How the problem of a refused construct ends: `found <construct>, which frontmatter does not allow`."""


def _found(construct: str) -> str:
    """The problem of a refused construct, worded from its name.

    Args:
        construct: What was found, with its article.
    """
    return f'found {construct}, {_NOT_ALLOWED}'


def describe_refusal(construct: RefusedConstruct) -> str:
    """The problem a refused construct is reported with.

    Args:
        construct: The construct the subset leaves out.
    """
    match construct:
        case Directive(name):
            return _found(f'the directive {name}')
        case DocumentMarker(marker):
            return _found(f'the document marker {marker}')
        case Alias(anchor):
            return _found(f'the alias *{anchor}')
        case Anchor(anchor):
            return _found(f'the anchor &{anchor}')
        case Tag(tag):
            return _found(f'the tag {tag!r}')
        case MergeKey():
            return _found('the merge key <<')
        case CollectionKey():
            return _found('a collection as a key')
        case NonStringKey(key):
            return _found(f'the non-string key {key}')
        case FlowCollectionRoot():
            return _found('a flow collection as the block')
        case CollectionInFlow():
            return _found('a collection inside a flow collection')
        case NestedBlockSequence():
            return _found('a block sequence as an item of a block sequence')
        case EscapeBeyondUnicode():
            return _found('an escape that names no Unicode character')
        case ExplicitKey():
            return _found('an explicit key')
        case EmptyKey():
            return _found('an empty key')
        case IndentationIndicator():
            return _found('a block scalar indentation indicator')
        case SpreadFlowCollection():
            return _found('a flow collection spread over lines')
        case LineSeparator(character):
            return f'the block holds U+{ord(character):04X}, which is not a line break here'
        case _:
            assert_never(construct)


def refusal_help(construct: RefusedConstruct) -> str | None:
    """What to do about a refused construct, or `None` where there is no more to say.

    Args:
        construct: The construct the subset leaves out.
    """
    match construct:
        case LineSeparator():
            return 'Use a line feed, or remove it'
        case (
            Directive()
            | DocumentMarker()
            | Alias()
            | Anchor()
            | Tag()
            | MergeKey()
            | CollectionKey()
            | NonStringKey()
            | FlowCollectionRoot()
            | CollectionInFlow()
            | NestedBlockSequence()
            | EscapeBeyondUnicode()
            | ExplicitKey()
            | EmptyKey()
            | IndentationIndicator()
            | SpreadFlowCollection()
        ):
            return None
        case _:
            assert_never(construct)
