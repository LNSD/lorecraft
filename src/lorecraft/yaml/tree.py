"""What a YAML text says, as a tree of frozen values, each node with the position it is written at.

A mapping holds its entries in the order they are written, a key written twice included, since a reader of the tree
decides what a repeated key means. A scalar holds the value YAML 1.2's core schema reads its text as: null, a
boolean, an integer, a float or a string. Every node carries a `YamlPosition`, so a package above this one can word a
problem against a line without reaching the YAML library that read the text.
"""

from dataclasses import dataclass

from lorecraft.core.num import NonZeroUnsignedInt

type YamlScalarValue = str | int | float | bool | None
"""The values a YAML scalar can read as under YAML 1.2's core schema."""


@dataclass(frozen=True, slots=True)
class YamlPosition:
    """Where a node starts in the text it was read from. Both numbers are one-based, as an editor shows them.

    Attributes:
        line: The line the node starts on, 1 for the first line of the text.
        column: The column the node starts at, 1 for the first character of a line. It counts characters, not bytes.
    """

    line: NonZeroUnsignedInt
    column: NonZeroUnsignedInt


@dataclass(frozen=True, slots=True)
class YamlKey:
    """The key of one entry of a mapping.

    Attributes:
        name: The key's text, with any quotes read off.
        position: Where the key starts.
    """

    name: str
    position: YamlPosition


@dataclass(frozen=True, slots=True)
class YamlScalar:
    """A scalar node.

    Attributes:
        value: What the scalar's text reads as: `None`, a boolean, an integer, a float or a string. A quoted or block
            scalar is always a string. Python's equality does not tell `True` from `1`, or `1` from `1.0`, so two
            scalars with such values compare equal: a reader that must tell them apart checks the value's type.
        position: Where the scalar starts.
    """

    value: YamlScalarValue
    position: YamlPosition


@dataclass(frozen=True, slots=True)
class YamlSequence:
    """A sequence node.

    Attributes:
        items: The items in the order they are written.
        position: Where the sequence starts.
    """

    items: tuple['YamlValue', ...]
    position: YamlPosition


@dataclass(frozen=True, slots=True)
class YamlMapping:
    """A mapping node.

    Attributes:
        entries: Each key with its value, in the order they are written. A key written more than once appears once
            per occurrence.
        position: Where the mapping starts.
    """

    entries: tuple[tuple[YamlKey, 'YamlValue'], ...]
    position: YamlPosition


type YamlValue = YamlMapping | YamlSequence | YamlScalar
"""Any node of the tree."""
