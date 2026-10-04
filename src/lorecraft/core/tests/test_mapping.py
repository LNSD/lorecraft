"""The immutable mapping: read like any mapping, equal and hashed by its items whatever order they came in."""

import pytest

from ..mapping import FrozenMapping


@pytest.mark.unit
class TestFrozenMapping:
    def test_getitem_with_a_held_key_returns_its_value(self) -> None:
        #: Given
        mapping = FrozenMapping({'a': 1, 'b': 2})

        #: When
        value = mapping['b']

        #: Then
        assert value == 2, 'a held key reads its value, as in any mapping'

    def test_getitem_with_a_missing_key_raises_key_error(self) -> None:
        #: Given
        mapping = FrozenMapping({'a': 1})

        #: When
        with pytest.raises(KeyError) as exc_info:
            mapping['b']

        #: Then
        assert exc_info.value.args == ('b',), 'the error names the missing key, as the mapping protocol does'

    def test_get_with_a_missing_key_returns_none(self) -> None:
        #: Given
        mapping = FrozenMapping({'a': 1})

        #: When
        value = mapping.get('b')

        #: Then
        assert value is None, 'the mapping methods built on lookup work as on any mapping'

    def test_len_with_two_items_returns_two(self) -> None:
        #: Given
        mapping = FrozenMapping({'a': 1, 'b': 2})

        #: When
        size = len(mapping)

        #: Then
        assert size == 2, 'the length is the number of keys'

    def test_iter_with_keys_given_out_of_order_returns_them_in_the_order_given(self) -> None:
        #: Given
        mapping = FrozenMapping({'b': 2, 'a': 1})

        #: When
        keys = list(mapping)

        #: Then
        assert keys == ['b', 'a'], 'the keys come in the order the mapping was built from'

    def test_init_with_a_dict_changed_afterwards_keeps_the_items_given(self) -> None:
        #: Given
        source = {'a': 1}
        mapping = FrozenMapping(source)

        #: When
        source['b'] = 2

        #: Then
        assert mapping == FrozenMapping({'a': 1}), 'the items are copied, so a later change to the source is not seen'

    def test_eq_with_the_same_items_in_another_order_returns_true(self) -> None:
        #: Given
        first = FrozenMapping({'a': 1, 'b': 2})
        second = FrozenMapping({'b': 2, 'a': 1})

        #: When
        equal = first == second

        #: Then
        assert equal, 'two mappings holding the same items are equal, whatever order they were given in'

    def test_eq_with_another_value_returns_false(self) -> None:
        #: Given
        first = FrozenMapping({'a': 1})
        second = FrozenMapping({'a': 2})

        #: When
        equal = first == second

        #: Then
        assert not equal, 'a key holding another value makes another mapping'

    def test_eq_with_a_dict_of_the_same_items_returns_false(self) -> None:
        #: Given
        mapping = FrozenMapping({'a': 1})

        #: When
        equal = mapping == {'a': 1}

        #: Then
        assert not equal, 'a dict is unhashable, so it is never equal to a value that hashes'

    def test_hash_with_the_same_items_in_another_order_returns_the_same_hash(self) -> None:
        #: Given
        first = FrozenMapping({'a': 1, 'b': 2})
        second = FrozenMapping({'b': 2, 'a': 1})

        #: When
        distinct = {first, second}

        #: Then
        assert len(distinct) == 1, 'equal mappings hash alike, so a set holds one'
