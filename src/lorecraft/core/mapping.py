"""The immutable mapping: a `Mapping` that compares and hashes by its items, so a value object can hold one.

A decoder such as `json.loads` builds its value from `dict` and `list`, both mutable and unhashable, so a value
object holding one is neither safe to share nor hashable. `FrozenMapping.from_plain` copies a string-keyed mapping of
such data into `FrozenMapping` and `tuple`, and `FrozenMapping.to_plain` copies it back, for a library that reads
only the plain containers.
"""

from collections.abc import Iterator, Mapping
from typing import assert_never


class FrozenMapping[K, V](Mapping[K, V]):
    """A mapping that never changes once built, equal to another exactly when the two hold the same items.

    Equality ignores the order the items were given in, as a `dict`'s does, and the hash is built from the items
    alone, so two mappings built from the same items in a different order are equal and hash alike. A `dict` cannot
    be a field of a frozen value: it is mutable and unhashable. A tuple of pairs can, but then the order it was built
    in decides equality. This is the third option, read like any `Mapping`.

    Every key and every value must be hashable for the mapping to be: the hash is that of its items' `frozenset`.
    The items are copied when the mapping is built, so changing the mapping it was built from changes nothing here.
    It is also equal to a `dict` holding the same items, as Python's own `frozendict` is (PEP 814, Python 3.15),
    whose hash it computes the same way; that cannot break the rule that equal values hash alike, since a `dict` has
    no hash. Matching it keeps the two interchangeable, so the built-in can replace this class once the package
    requires 3.15.
    """

    __slots__ = ('_items',)

    def __init__(self, items: Mapping[K, V]) -> None:
        """Copy the items; performs no other work.

        Args:
            items: The keys and their values, in any order; copied, so the caller may change it afterwards.
        """
        self._items: dict[K, V] = dict(items)

    def __getitem__(self, key: K) -> V:
        """The value held for `key`.

        Args:
            key: The key to look up.

        Raises:
            KeyError: If the mapping holds no value for `key`; the language's mapping protocol, which `get` and
                `in` rely on.
        """
        return self._items[key]

    def __iter__(self) -> Iterator[K]:
        """Every key, in the order the mapping was built from."""
        return iter(self._items)

    def __len__(self) -> int:
        """How many keys the mapping holds."""
        return len(self._items)

    def __eq__(self, other: object) -> bool:
        """Whether `other` is a `FrozenMapping` or a `dict` holding the same items, in any order.

        Args:
            other: The value compared; anything but a `FrozenMapping` or a `dict` is left to its own comparison.
        """
        if isinstance(other, FrozenMapping):
            return self._items == other._items
        if isinstance(other, dict):
            return self._items == other
        return NotImplemented

    def __hash__(self) -> int:
        """A hash of the items alone, whatever order they were given in."""
        return hash(frozenset(self._items.items()))

    def __repr__(self) -> str:
        """The class and the items it was built from, such as `FrozenMapping({'a': 1})`."""
        return f'FrozenMapping({self._items!r})'

    @classmethod
    def from_plain(cls, mapping: Mapping[str, object]) -> 'FrozenMapping[str, Frozen]':
        """A copy of a decoded mapping with every value frozen all the way down.

        Every mapping inside it becomes a `FrozenMapping` and every list a tuple. Any other value is a scalar and is
        kept as it is.

        Args:
            mapping: The decoded mapping, holding only string-keyed mappings, lists and the scalars `Frozen` names,
                at any depth; left unchanged.
        """
        frozen: dict[str, Frozen] = {}
        for key, value in mapping.items():
            frozen[key] = _to_frozen(value)
        # Built as `FrozenMapping`, not `cls`: the result holds string keys and frozen values whatever `K` and `V`
        # the class is read with.
        return FrozenMapping(frozen)

    def to_plain(self: 'FrozenMapping[str, Frozen]') -> dict[str, object]:
        """A `dict` copy of a frozen mapping with every value turned back into plain data, as `_to_plain_value` does.

        The one way frozen data leaves for code that reads only plain containers: `jsonschema`, which takes a JSON
        object only as a `dict` and an array only as a `list`, the strict pydantic models, which do the same, and a
        finding that quotes a value as its author wrote it rather than as the tuple it is frozen into.
        """
        # The annotated `self` limits the method to a string-keyed mapping of frozen values, the only kind
        # `from_plain` builds and the only kind whose values `_to_plain_value` can turn back.
        plain: dict[str, object] = {}
        for key, value in self.items():
            plain[key] = _to_plain_value(value)
        return plain


type Frozen = FrozenMapping[str, Frozen] | tuple[Frozen, ...] | str | int | float | bool | None
"""A value that never changes once built: a string-keyed mapping or a sequence frozen all the way down, or a
JSON scalar. Every part of it is hashable, so the whole value is."""


def _to_plain_value(value: Frozen) -> object:
    """A copy of a frozen value with every container turned back into the plain one a decoder builds.

    Every `FrozenMapping` inside it becomes a `dict` and every tuple a `list`; a scalar is kept as it is.

    Args:
        value: The frozen value, such as one held in a mapping `FrozenMapping.from_plain` returned; left unchanged.
    """
    match value:
        case FrozenMapping():
            return value.to_plain()
        case tuple():
            plain: list[object] = []
            for item in value:
                plain.append(_to_plain_value(item))
            return plain
        case str() | int() | float() | bool() | None:
            return value
        case _:
            assert_never(value)


def _to_frozen(value: object) -> Frozen:
    """One decoded value frozen all the way down.

    Args:
        value: A string-keyed mapping, a list or a scalar `Frozen` names, as the decoder built it.
    """
    if isinstance(value, Mapping):
        return FrozenMapping.from_plain(value)
    if isinstance(value, list):
        frozen: list[Frozen] = []
        for item in value:
            frozen.append(_to_frozen(item))
        return tuple(frozen)
    if isinstance(value, str | int | float | bool | None):
        return value
    raise AssertionError(f'unreachable: a decoder builds only mappings, lists and scalars, got {type(value)!r}')
