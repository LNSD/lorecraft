"""JSON Schema's vocabulary for JSON values."""

from enum import StrEnum


class JsonType(StrEnum):
    """A type JSON Schema names; the value is the name its `type` keyword spells it with."""

    ARRAY = 'array'
    BOOLEAN = 'boolean'
    INTEGER = 'integer'
    NULL = 'null'
    NUMBER = 'number'
    OBJECT = 'object'
    STRING = 'string'


type JsonTypes = tuple[JsonType, *tuple[JsonType, ...]]
"""One or more JSON types: a `type` keyword names at least one, so a list of them is never empty."""
