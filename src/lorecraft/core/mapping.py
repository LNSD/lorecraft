"""The immutable mapping: a `Mapping` that compares and hashes by its items, so a value object can hold one.

A decoder such as `json.loads` builds its value from `dict` and `list`, both mutable and unhashable, so a value
object holding one is neither safe to share nor hashable. `Plain` is the type of that decoded data.
`FrozenMapping.from_plain` copies a string-keyed mapping of it into `FrozenMapping` and `tuple`, and
`FrozenMapping.to_plain` copies it back, for a library that reads only the plain containers.

`FrozenMapping` is also a pydantic type. A model field declared `FrozenMapping[str, str]` is read from a JSON object
as the `dict[str, str]` it would be, with the same errors and the same JSON Schema, and then held as a mapping. A
field declared `FrozenMapping[str, Frozen]` reads any JSON value and holds every object in it as a `FrozenMapping` and
every array as a tuple, so the model is hashable. It is written back as the object it was read from.
"""

from collections.abc import Iterator, Mapping, Sequence
from typing import Any, assert_never, get_args

from pydantic import GetCoreSchemaHandler, JsonValue, SerializerFunctionWrapHandler, ValidatorFunctionWrapHandler
from pydantic_core import core_schema

from .error import Error


class NonStringKeyError(Error):
    """A mapping held in plain data has a key that is not a string.

    Attributes:
        key: The rejected key.
    """

    key: object

    def __init__(self, key: object) -> None:
        self.key = key
        super().__init__(f'a mapping key must be a string, got {type(key).__name__}')


class NonPlainValueError(Error):
    """A value held in plain data is neither a mapping, a list nor a scalar.

    Attributes:
        value_type: The type of the rejected value.
    """

    value_type: type

    def __init__(self, value_type: type) -> None:
        self.value_type = value_type
        super().__init__(f'a plain value must be a mapping, a list or a scalar, got {value_type.__name__}')


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
        """The class and the items it was built from, such as `FrozenMapping({'a': 1})`; a subclass names itself."""
        return f'{type(self).__name__}({self._items!r})'

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source: type[object], handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        """How pydantic validates and serializes a field of this type: see the module's note.

        Args:
            source: The annotated type, `FrozenMapping[str, V]`: `V` is the value type the field's JSON object is
                validated with. A bare `FrozenMapping` holds any value.
            handler: Pydantic's schema generator, which builds the `dict` schema the field is read and written as.
        """
        # A field is a JSON object, whose keys are strings, so only the value type is read from the annotation.
        value_type = get_args(source)[1] if get_args(source) else Any
        if value_type is Frozen:
            # A model is validated from a JSON document or from the `dict` and `list` a caller builds, and strict
            # mode refuses a `list` where a tuple is declared. So the value is read as the JSON value it is, then
            # frozen.
            dict_schema = handler.generate_schema(dict[str, JsonValue])
            # Read as strict `dict[str, JsonValue]` first, so every key is a string and every value a JSON value,
            # and `from_plain` cannot refuse it: a domain error here would escape pydantic's validation.
            freeze = cls.from_plain
            read_held = FrozenMapping._read_held_tree
        else:
            dict_schema = handler.generate_schema(dict[str, value_type])
            freeze = cls
            read_held = FrozenMapping._read_held_items
        from_dict = core_schema.no_info_after_validator_function(freeze, dict_schema)
        return core_schema.json_or_python_schema(
            json_schema=from_dict,
            # In Python the field also takes the mapping it is declared as, which strict mode would refuse as a
            # `dict_type` error since the `dict` schema alone reads only a `dict`. A wrap rather than a union, so
            # that a value that is not one is reported by the `dict` schema alone, as it was.
            python_schema=core_schema.no_info_wrap_validator_function(read_held, from_dict),
            serialization=core_schema.wrap_serializer_function_ser_schema(
                FrozenMapping._to_dict_for_pydantic, schema=dict_schema
            ),
        )

    @staticmethod
    def _read_held_items(value: object, validate_dict: ValidatorFunctionWrapHandler) -> object:
        """A `FrozenMapping` given for the field, read as the `dict` of its items; anything else, as it is.

        Held items are validated like a `dict`'s, so a mapping built elsewhere is held to the field's value type.

        Args:
            value: What a model was given for the field.
            validate_dict: Pydantic's validator for the `dict` schema followed by the freezing step.
        """
        if isinstance(value, FrozenMapping):
            return validate_dict(dict(value))
        return validate_dict(value)

    @staticmethod
    def _read_held_tree(value: object, validate_dict: ValidatorFunctionWrapHandler) -> object:
        """A `FrozenMapping` given for a `Frozen` field, read as the JSON object it holds; anything else, as it is.

        A held value that is not a JSON value, such as a list kept inside a mapping or a set, reaches the `dict`
        schema as it is and is refused there, so no held mapping skips the check a decoded one passes.

        Args:
            value: What a model was given for the field.
            validate_dict: Pydantic's validator for the `dict` schema followed by the freezing step.
        """
        if isinstance(value, FrozenMapping):
            return validate_dict(_thaw(value))
        return validate_dict(value)

    def _to_dict_for_pydantic(
        self: 'FrozenMapping[str, Frozen]', serialize_dict: SerializerFunctionWrapHandler
    ) -> object:
        """The mapping written as the `dict` it was read as, by the `dict` schema's own serializer.

        Args:
            serialize_dict: Pydantic's serializer for the `dict` schema, which writes each value.
        """
        return serialize_dict(self.to_plain())

    @classmethod
    def from_plain(cls, mapping: 'Mapping[str, Plain]') -> 'FrozenMapping[str, Frozen]':
        """A copy of a decoded mapping with every value frozen all the way down.

        Every mapping inside it becomes a `FrozenMapping` and every list a tuple. Any other value is a scalar and is
        kept as it is.

        Args:
            mapping: The decoded mapping, holding only string-keyed mappings, lists and the scalars `Plain` names,
                at any depth; left unchanged.

        Raises:
            NonStringKeyError: If a mapping at any depth has a key that is not a string.
            NonPlainValueError: If a value at any depth is neither a mapping, a `list`, a `tuple` nor a scalar
                `Plain` names.
        """
        frozen: dict[str, Frozen] = {}
        for key, value in mapping.items():
            # The annotation promises string keys, but a decoder builds whatever the document holds, so the key is
            # checked as the `object` it may be.
            checked_key: object = key
            if not isinstance(checked_key, str):
                raise NonStringKeyError(checked_key)
            frozen[checked_key] = _to_frozen(value)
        # Built as `FrozenMapping`, not `cls`: the result holds string keys and frozen values whatever `K` and `V`
        # the class is read with.
        return FrozenMapping(frozen)

    def to_plain(self: 'FrozenMapping[str, Frozen]') -> 'dict[str, Plain]':
        """A `dict` copy of a frozen mapping with every value turned back into plain data, as `_to_plain_value` does.

        The one way frozen data leaves for code that reads only plain containers: `lorecraft.jsonschema` and strict
        pydantic models, which take objects only as `dict` and arrays only as `list`, and findings that quote a value
        as its author wrote it rather than as the tuple it is frozen into.
        """
        # The annotated `self` limits the method to a string-keyed mapping of frozen values, the only kind
        # `from_plain` builds and the only kind whose values `_to_plain_value` can turn back.
        plain: dict[str, Plain] = {}
        for key, value in self.items():
            plain[key] = _to_plain_value(value)
        return plain


type Plain = Mapping[str, Plain] | Sequence[Plain] | str | int | float | bool | None
"""A value as a decoder such as `json.loads` or a YAML loader builds it: a string-keyed mapping or a sequence of such
values, or a JSON scalar. Unlike `Frozen`, the containers may be mutable, so the value is not hashable.

The type admits any `Sequence`, so that a `list` or a `tuple` of values type-checks, but only a `list` and a `tuple`
count as sequences at run time. `bytes`, `bytearray`, `range` and `deque` are refused by `FrozenMapping.from_plain`,
though the type admits them."""

type Frozen = FrozenMapping[str, Frozen] | tuple[Frozen, ...] | str | int | float | bool | None
"""A value that never changes once built: a string-keyed mapping or a sequence frozen all the way down, or a
JSON scalar. Every part of it is hashable, so the whole value is."""


def _to_plain_value(value: Frozen) -> Plain:
    """A copy of a frozen value with every container turned back into the plain one a decoder builds.

    Every `FrozenMapping` inside it becomes a `dict` and every tuple a `list`; a scalar is kept as it is.

    Args:
        value: The frozen value, such as one held in a mapping `FrozenMapping.from_plain` returned; left unchanged.
    """
    match value:
        case FrozenMapping():
            return value.to_plain()
        case tuple():
            plain: list[Plain] = []
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
        value: A string-keyed mapping, a list or a scalar `Plain` names, as the decoder built it. Typed `object`
            because it is the boundary that refuses anything else.

    Raises:
        NonStringKeyError: If a mapping at any depth has a key that is not a string.
        NonPlainValueError: If the value, or one inside it, is not a mapping, a `list`, a `tuple` or a scalar.
    """
    # A `str` is a sequence of strings, so it is taken as a scalar before the sequences are.
    if isinstance(value, str | int | float | bool | None):
        return value
    if isinstance(value, Mapping):
        return FrozenMapping.from_plain(value)
    if isinstance(value, list | tuple):
        frozen: list[Frozen] = []
        for item in value:
            frozen.append(_to_frozen(item))
        return tuple(frozen)
    raise NonPlainValueError(type(value))


def _thaw(value: object) -> object:
    """A copy of a held value with every `FrozenMapping` a `dict` and every tuple a `list`, and anything else as it is.

    Unlike `_to_plain_value` it never raises: a value that is not frozen data stays as it is, for the schema the
    copy is validated by to refuse.

    Args:
        value: A value a model was given for a `Frozen` field.
    """
    if isinstance(value, FrozenMapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value
