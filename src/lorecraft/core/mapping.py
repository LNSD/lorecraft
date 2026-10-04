"""The immutable mapping: a `Mapping` that compares and hashes by its items, so a value object can hold one."""

from collections.abc import Iterator, Mapping


class FrozenMapping[K, V](Mapping[K, V]):
    """A mapping that never changes once built, equal to another exactly when the two hold the same items.

    Equality ignores the order the items were given in, as a `dict`'s does, and the hash is built from the items
    alone, so two mappings built from the same items in a different order are equal and hash alike. A `dict` cannot
    be a field of a frozen value: it is mutable and unhashable. A tuple of pairs can, but then the order it was built
    in decides equality. This is the third option, read like any `Mapping`.

    Every key and every value must be hashable for the mapping to be: the hash is that of its items' `frozenset`.
    The items are copied when the mapping is built, so changing the mapping it was built from changes nothing here.
    It is equal only to another `FrozenMapping`, never to a `dict` holding the same items, so that two equal values
    always hash alike.
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
        """Whether `other` is a `FrozenMapping` holding the same items, in any order.

        Args:
            other: The value compared; anything but a `FrozenMapping` is left to its own comparison.
        """
        if not isinstance(other, FrozenMapping):
            return NotImplemented
        return self._items == other._items

    def __hash__(self) -> int:
        """A hash of the items alone, whatever order they were given in."""
        return hash(frozenset(self._items.items()))

    def __repr__(self) -> str:
        """The class and the items it was built from, such as `FrozenMapping({'a': 1})`."""
        return f'FrozenMapping({self._items!r})'
