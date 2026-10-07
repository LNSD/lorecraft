"""What a JSON Schema states that tells a reader how to write a field, read from the schema as plain data.

Both frontmatter schemas are read here: the one a structure specification states, and the one pydantic renders from
the Agent Skills specification's model, which is JSON Schema too. A property is read for its `description`, its
first example and the values it allows; a subschema for the reason its `$comment` gives. Everything is read
defensively, never asserted: a schema owes a reader none of it, and a keyword left out reads as nothing stated.
"""

import json
from collections.abc import Mapping

import yaml

from .frontmatter_problem import FieldGuidance, JsonType


def value_text(value: object) -> str:
    """A schema value as the text a reader writes it as in YAML: a string as it is, any other value as JSON.

    A string that YAML would read as another value, such as `1.0` or `true`, is quoted, so the text written back
    in the frontmatter is the same string.

    Args:
        value: An example, or one of the values an `enum` or a `const` allows.
    """
    if isinstance(value, str) and _is_plain_yaml_string(value):
        return value
    return json.dumps(value, ensure_ascii=False)


def _is_plain_yaml_string(text: str) -> bool:
    """Whether YAML reads the text, written without quotes, back as the same string.

    Args:
        text: A string a schema states.
    """
    try:
        return yaml.safe_load(text) == text
    except yaml.YAMLError:
        return False


def json_type_of(value: object) -> JsonType:
    """The JSON type of a decoded frontmatter value.

    Args:
        value: A value a frontmatter decodes to: a mapping, a list or a JSON scalar.
    """
    if value is None:
        return JsonType.NULL
    # `bool` first: a Python `bool` is an `int`, which JSON's `boolean` is not.
    if isinstance(value, bool):
        return JsonType.BOOLEAN
    if isinstance(value, int):
        return JsonType.INTEGER
    if isinstance(value, float):
        return JsonType.NUMBER
    if isinstance(value, str):
        return JsonType.STRING
    if isinstance(value, list | tuple):
        return JsonType.ARRAY
    if isinstance(value, Mapping):
        return JsonType.OBJECT
    # The YAML decoder only yields mappings, lists and JSON scalars, and each is handled above.
    raise AssertionError(f'unreachable: a frontmatter decodes to JSON values, got {type(value)!r}')


def schema_guidance(schema: object) -> FieldGuidance:
    """What one property's schema states about the field: its description, an example, the values it allows.

    The example is the first of `examples`, or else the `const`; the allowed values are those of `enum` or `const`.

    Args:
        schema: The property's schema; anything but an object, such as a boolean schema or a property the schema
            lacks, states nothing.
    """
    if not isinstance(schema, Mapping):
        return FieldGuidance()

    description = schema.get('description')
    allowed: tuple[str, ...] = ()
    example: str | None = None

    enum = schema.get('enum')
    if isinstance(enum, list | tuple):
        allowed = tuple(value_text(value) for value in enum)
    if 'const' in schema:
        allowed = (value_text(schema['const']),)
        example = allowed[0]
    examples = schema.get('examples')
    if isinstance(examples, list | tuple) and examples:
        example = value_text(examples[0])

    return FieldGuidance(
        description=description if isinstance(description, str) else None, example=example, allowed=allowed
    )


def property_guidance(schema: object, field: str) -> FieldGuidance:
    """What the schema states about one of its properties, or nothing when it has no property of that name.

    Args:
        schema: The object schema holding `properties`; anything else states nothing.
        field: The top-level field.
    """
    return schema_guidance(_properties(schema).get(field))


def known_fields(schema: object) -> tuple[str, ...]:
    """The fields an object schema names in its `properties`, in the order it states them.

    Args:
        schema: The object schema; anything else names none.
    """
    return tuple(_properties(schema))


def schema_reason(schema: object) -> str | None:
    """The reason a subschema states in `$comment`, which this repository's schemas use to say why a branch exists.

    Args:
        schema: The subschema a keyword failed in; anything but an object states nothing.
    """
    if not isinstance(schema, Mapping):
        return None
    comment = schema.get('$comment')
    if isinstance(comment, str):
        return comment
    return None


def _properties(schema: object) -> Mapping[str, object]:
    """The `properties` of an object schema, or nothing when it has none.

    Args:
        schema: The schema read; anything but an object has none.
    """
    if not isinstance(schema, Mapping):
        return {}
    properties = schema.get('properties')
    if not isinstance(properties, Mapping):
        return {}
    return properties
