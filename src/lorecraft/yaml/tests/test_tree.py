"""The YAML value tree: frozen nodes that compare by what they hold and carry their position."""

from dataclasses import FrozenInstanceError

import pytest

from lorecraft.core.num import NonZeroUnsignedInt

from ..tree import YamlKey, YamlMapping, YamlPosition, YamlScalar, YamlSequence, YamlValue


def _at(line: int, column: int = 1) -> YamlPosition:
    return YamlPosition(NonZeroUnsignedInt(line), NonZeroUnsignedInt(column))


def _build_tree() -> YamlValue:
    items = YamlSequence((YamlScalar(1, _at(2, 5)), YamlScalar(None, _at(3, 5))), _at(2, 3))
    return YamlMapping(((YamlKey('items', _at(1)), items),), _at(1))


@pytest.mark.unit
class TestYamlPosition:
    def test_yaml_position_with_the_same_line_and_column_compares_equal(self) -> None:
        #: Given
        first = _at(3, 5)
        second = _at(3, 5)

        #: When
        equal = first == second

        #: Then
        assert equal, f'two positions with one line and column are one position, got {first} and {second}'

    def test_yaml_position_with_the_same_line_and_column_hashes_alike(self) -> None:
        #: Given
        first = _at(3, 5)
        second = _at(3, 5)
        expected = hash(first)

        #: When
        hashed = hash(second)

        #: Then
        assert hashed == expected, 'equal positions must hash alike so a tree can be a key'


@pytest.mark.unit
class TestYamlTree:
    def test_yaml_mapping_with_a_repeated_key_keeps_both_entries_in_written_order(self) -> None:
        #: Given
        first = (YamlKey('name', _at(1)), YamlScalar('one', _at(1, 7)))
        second = (YamlKey('name', _at(2)), YamlScalar('two', _at(2, 7)))

        #: When
        mapping = YamlMapping((first, second), _at(1))

        #: Then
        assert mapping.entries == (first, second), f'a key written twice appears once per occurrence, got {mapping}'

    def test_yaml_value_with_a_nested_tree_compares_structurally(self) -> None:
        #: Given
        first = _build_tree()
        second = _build_tree()

        #: When
        equal = first == second

        #: Then
        assert equal, 'two trees read from the same text must be equal'

    def test_yaml_value_with_a_nested_tree_hashes_alike(self) -> None:
        #: Given
        first = _build_tree()
        second = _build_tree()
        expected = hash(first)

        #: When
        hashed = hash(second)

        #: Then
        assert hashed == expected, 'equal trees must hash alike'

    def test_yaml_scalar_with_a_different_position_is_a_different_value(self) -> None:
        #: Given
        here = YamlScalar('x', _at(1))
        there = YamlScalar('x', _at(2))

        #: When
        equal = here == there

        #: Then
        assert not equal, 'a scalar is its value and where it is written'

    def test_yaml_scalar_assigning_its_value_raises_frozen_instance_error(self) -> None:
        #: Given
        scalar = YamlScalar(True, _at(1))

        #: When
        with pytest.raises(FrozenInstanceError) as raised:
            scalar.value = False  # ty: ignore[invalid-assignment]

        #: Then
        assert isinstance(raised.value, FrozenInstanceError), 'a node is frozen, so its value cannot be assigned'
