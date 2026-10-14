"""The immutable mapping: read like any mapping, equal and hashed by its items, and decoded data frozen and thawed.

A mapping is equal and hashed alike whatever order its items came in. Decoded data is frozen into it all the way
down, and turned back into plain data.
"""

import pytest
from pydantic import BaseModel, ConfigDict, ValidationError

from ..mapping import Frozen, FrozenMapping, NonPlainValueError, NonStringKeyError, Plain


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

    def test_eq_with_a_dict_of_the_same_items_returns_true(self) -> None:
        #: Given
        mapping = FrozenMapping({'a': 1, 'b': 2})

        #: When
        equal = mapping == {'b': 2, 'a': 1}

        #: Then
        assert equal, 'a dict with the same items is equal, in any order, as it is to the built-in frozendict'

    def test_eq_with_a_dict_of_other_items_returns_false(self) -> None:
        #: Given
        mapping = FrozenMapping({'a': 1})

        #: When
        equal = mapping == {'a': 2}

        #: Then
        assert not equal, 'a dict holding another value for a key is another mapping'

    def test_hash_with_the_same_items_in_another_order_returns_the_same_hash(self) -> None:
        #: Given
        first = FrozenMapping({'a': 1, 'b': 2})
        second = FrozenMapping({'b': 2, 'a': 1})

        #: When
        distinct = {first, second}

        #: Then
        assert len(distinct) == 1, 'equal mappings hash alike, so a set holds one'

    def test_repr_of_a_subclass_names_the_subclass(self) -> None:
        #: Given
        class Records(FrozenMapping[str, int]):
            pass

        mapping = Records({'a': 1})

        #: When
        text = repr(mapping)

        #: Then
        assert text == "Records({'a': 1})", 'a failing assertion shows the type the value was built as'


@pytest.mark.unit
class TestFrozenMappingFromPlain:
    def test_from_plain_with_nested_containers_freezes_each_one(self) -> None:
        #: Given
        mapping = {'tags': ['a', 'b'], 'meta': {'see': [{'x': 1}]}}

        #: When
        frozen = FrozenMapping.from_plain(mapping)

        #: Then
        assert frozen == FrozenMapping(
            {
                'tags': ('a', 'b'),
                'meta': FrozenMapping({'see': (FrozenMapping({'x': 1}),)}),
            }
        ), 'every mapping becomes a frozen mapping and every list a tuple, at any depth'

    def test_from_plain_with_nested_containers_returns_a_hashable_value(self) -> None:
        #: Given
        mapping = {'meta': {'see': ['a', {'x': 1}]}}
        first = FrozenMapping.from_plain(mapping)
        second = FrozenMapping.from_plain(mapping)

        #: When
        hashed_alike = hash(first) == hash(second)

        #: Then
        assert hashed_alike, 'two copies of one value are equal, so they hash alike'

    def test_from_plain_with_a_scalar_value_keeps_it_unchanged(self) -> None:
        #: Given
        value = 'guide'

        #: When
        frozen = FrozenMapping.from_plain({'name': value})

        #: Then
        assert frozen['name'] is value, 'a scalar is already immutable, so it is kept as it is'

    def test_from_plain_with_every_kind_of_scalar_keeps_each_one(self) -> None:
        #: Given
        mapping: dict[str, Plain] = {
            'name': 'guide',
            'count': 3,
            'weight': 1.5,
            'draft': True,
            'owner': None,
        }

        #: When
        frozen = FrozenMapping.from_plain(mapping)

        #: Then
        assert frozen == FrozenMapping(mapping), 'a string, a number, a bool and null are kept as they are'

    def test_from_plain_with_a_non_string_key_raises_non_string_key_error(self) -> None:
        #: Given
        mapping: dict[str, object] = {'nested': {1: 'v'}}

        #: When
        with pytest.raises(NonStringKeyError) as exc_info:
            FrozenMapping.from_plain(mapping)  # ty: ignore[invalid-argument-type]

        #: Then
        assert exc_info.value.key == 1, 'the key that is not a string is reported, at any depth'

    def test_from_plain_with_a_set_value_raises_non_plain_value_error(self) -> None:
        #: Given
        mapping: dict[str, object] = {'tags': {'a', 'b'}}

        #: When
        with pytest.raises(NonPlainValueError) as exc_info:
            FrozenMapping.from_plain(mapping)  # ty: ignore[invalid-argument-type]

        #: Then
        assert exc_info.value.value_type is set, 'a value that is not a mapping, a list or a scalar is refused'


@pytest.mark.unit
class TestFrozenMappingToPlain:
    def test_to_plain_with_a_frozen_mapping_returns_a_dict(self) -> None:
        #: Given
        frozen: FrozenMapping[str, Frozen] = FrozenMapping({'name': 'guide', 'tags': ('a',)})

        #: When
        plain = frozen.to_plain()

        #: Then
        assert plain == {'name': 'guide', 'tags': ['a']}, 'the mapping and every value in it are plain again'

    def test_to_plain_with_a_frozen_mapping_returns_the_mapping_it_was_frozen_from(self) -> None:
        #: Given
        mapping = {'tags': ['a', 'b'], 'meta': {'see': [{'x': 1}]}}
        frozen = FrozenMapping.from_plain(mapping)

        #: When
        plain = frozen.to_plain()

        #: Then
        assert plain == mapping, 'every frozen container turns back into the plain one it was copied from'

    def test_to_plain_with_nested_frozen_containers_turns_each_one_back(self) -> None:
        #: Given
        frozen: FrozenMapping[str, Frozen] = FrozenMapping({'see': (FrozenMapping({'tags': ('a',)}), 'rule')})

        #: When
        plain = frozen.to_plain()

        #: Then
        assert plain == {'see': [{'tags': ['a']}, 'rule']}, 'every frozen mapping becomes a dict and every tuple a list'

    def test_to_plain_with_a_scalar_value_keeps_it_unchanged(self) -> None:
        #: Given
        value = 'guide'
        frozen: FrozenMapping[str, Frozen] = FrozenMapping({'name': value})

        #: When
        plain = frozen.to_plain()

        #: Then
        assert plain['name'] is value, 'a scalar holds no container, so it is kept as it is'


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True)

    labels: FrozenMapping[str, str] | None = None
    tree: FrozenMapping[str, Frozen] | None = None


@pytest.mark.unit
class TestFrozenMappingAsPydanticType:
    def test_model_validate_json_with_an_object_holds_a_frozen_mapping(self) -> None:
        #: Given
        document = '{"labels": {"author": "example-org"}}'

        #: When
        model = _Model.model_validate_json(document)

        #: Then
        assert model.labels == FrozenMapping({'author': 'example-org'}), 'the object is held as a mapping'
        assert isinstance(model.labels, FrozenMapping), 'the held value is a FrozenMapping, not a dict'

    def test_model_validate_json_with_a_nested_value_freezes_it_all_the_way_down(self) -> None:
        #: Given
        document = '{"tree": {"see": [{"tags": ["a"]}, "rule"]}}'

        #: When
        model = _Model.model_validate_json(document)

        #: Then
        expected: FrozenMapping[str, Frozen] = FrozenMapping({'see': (FrozenMapping({'tags': ('a',)}), 'rule')})
        assert model.tree == expected, 'objects become mappings and arrays become tuples'
        assert hash(model) == hash(_Model.model_validate_json(document)), 'a model holding frozen data is hashable'

    def test_model_validate_json_with_a_wrong_value_type_reports_the_dict_error(self) -> None:
        #: Given
        document = '{"labels": {"version": 1}}'

        #: When
        with pytest.raises(ValidationError) as exc_info:
            _Model.model_validate_json(document)

        #: Then
        errors = exc_info.value.errors(include_url=False)
        assert [(error['loc'], error['type']) for error in errors] == [(('labels', 'version'), 'string_type')], (
            'the value is refused as the same field of a dict would be'
        )

    def test_model_dump_json_writes_the_object_it_was_read_from(self) -> None:
        #: Given
        document = '{"labels":null,"tree":{"see":[{"tags":["a"]},"rule"]}}'
        model = _Model.model_validate_json(document)

        #: When
        written = model.model_dump_json()

        #: Then
        assert written == document, 'mappings are written as objects and tuples as arrays'

    def test_model_with_a_frozen_mapping_holds_it_unchanged(self) -> None:
        #: Given
        labels = FrozenMapping({'author': 'example-org'})
        tree = FrozenMapping.from_plain({'see': [{'tags': ['a']}]})

        #: When
        model = _Model(labels=labels, tree=tree)

        #: Then
        assert model.labels == labels, 'a strict model takes the mapping its field is declared as'
        assert model.tree == tree, 'a frozen mapping of frozen values is taken as it is'

    def test_model_with_a_held_mapping_of_the_wrong_value_type_reports_the_dict_error(self) -> None:
        #: Given
        labels = FrozenMapping({'a': 1})

        #: When
        with pytest.raises(ValidationError) as exc_info:
            _Model(labels=labels)  # ty: ignore[invalid-argument-type]

        #: Then
        errors = exc_info.value.errors()
        assert [(error['type'], error['loc'][-2:]) for error in errors] == [('string_type', ('labels', 'a'))], (
            'a held mapping is held to the field value type like a dict'
        )

    def test_model_with_a_held_mapping_holding_a_list_refuses_or_freezes_it(self) -> None:
        #: Given
        tree = FrozenMapping({'see': ['x']})

        #: When
        model = _Model(tree=tree)  # ty: ignore[invalid-argument-type]

        #: Then
        assert model.tree == FrozenMapping({'see': ('x',)}), 'a list kept in a held mapping is frozen as a tuple'
        assert model.tree is not None
        assert isinstance(hash(model), int), 'the model holding it is hashable'

    def test_model_with_a_held_mapping_holding_a_set_refuses_it(self) -> None:
        #: Given
        tree = FrozenMapping({'see': {'x'}})

        #: When
        with pytest.raises(ValidationError) as exc_info:
            _Model(tree=tree)  # ty: ignore[invalid-argument-type]

        #: Then
        assert exc_info.type is ValidationError, 'a held mapping holding a set is refused as invalid'

    def test_model_json_schema_states_the_object_of_the_dict(self) -> None:
        #: Given
        model = _Model
        expected = {'type': 'object', 'additionalProperties': {'type': 'string'}}

        #: When
        schema = model.model_json_schema()

        #: Then
        assert schema['properties']['labels']['anyOf'][0] == expected, (
            'the schema is the one of the dict the field is read as'
        )
