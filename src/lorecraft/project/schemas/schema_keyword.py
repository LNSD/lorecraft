"""The keyword a `jsonschema` error reports, as one typed variant per keyword this package reads.

`jsonschema` names the keyword that failed as a string in `error.validator` and types its value as `Any`, so code
that dispatches on the string reads an untyped value in every branch. `keyword_of` is the one place that reads
both: it checks the value once and returns a variant that carries it typed. A keyword the package gives no
special reading is `OtherKeyword`.
"""

from dataclasses import dataclass

from jsonschema.exceptions import ValidationError as SchemaValidationError


@dataclass(frozen=True, slots=True)
class TypeKeyword:
    """`type`: the value must be one of these JSON type names.

    Attributes:
        names: The type names, one for a keyword written as a name and several for one written as an array.
    """

    names: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RequiredKeyword:
    """`required`: every one of these fields must be written.

    Attributes:
        fields: The fields the keyword requires, in the order it names them.
    """

    fields: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DependentRequiredKeyword:
    """`dependentRequired`: a field written requires other fields to be written.

    Attributes:
        dependencies: For each field, the fields it requires, in the order the keyword names them.
    """

    dependencies: tuple[tuple[str, tuple[str, ...]], ...]


@dataclass(frozen=True, slots=True)
class AdditionalPropertiesKeyword:
    """`additionalProperties`: fields the schema does not name are refused."""


@dataclass(frozen=True, slots=True)
class UnevaluatedPropertiesKeyword:
    """`unevaluatedProperties`: fields no keyword evaluated are refused or held to a schema."""


@dataclass(frozen=True, slots=True)
class OtherKeyword:
    """Any other keyword, or one of the above whose value is not the shape the meta-schema requires."""


type Keyword = (
    TypeKeyword
    | RequiredKeyword
    | DependentRequiredKeyword
    | AdditionalPropertiesKeyword
    | UnevaluatedPropertiesKeyword
    | OtherKeyword
)


def keyword_of(error: SchemaValidationError) -> Keyword:
    """The keyword that reported an error, with its value in the type the keyword gives it.

    A keyword whose value does not have the shape the meta-schema requires is read as `OtherKeyword`, never
    raised on: the schema was checked against the meta-schema when it was loaded, so that value does not occur.

    Args:
        error: One error from validating against a schema; its `validator` names the keyword.
    """
    # The error's schema came from `FrozenMapping.to_plain()` and was checked against the meta-schema, but
    # `jsonschema` types the value as `Any`, so it is read here as the `object` it may be.
    value: object = error.validator_value
    match error.validator:
        case 'type':
            if isinstance(value, str):
                return TypeKeyword((value,))
            names = _names(value)
            if names is not None:
                return TypeKeyword(names)
        case 'required':
            fields = _names(value)
            if fields is not None:
                return RequiredKeyword(fields)
        case 'dependentRequired':
            dependencies = _dependencies(value)
            if dependencies is not None:
                return DependentRequiredKeyword(dependencies)
        case 'additionalProperties':
            return AdditionalPropertiesKeyword()
        case 'unevaluatedProperties':
            return UnevaluatedPropertiesKeyword()
    return OtherKeyword()


def _names(value: object) -> tuple[str, ...] | None:
    """The strings of an array of strings, or `None` when the value is anything else.

    Args:
        value: A keyword's value, which the meta-schema requires to be an array of names.
    """
    if not isinstance(value, list):
        return None
    names: list[str] = []
    for item in value:
        if not isinstance(item, str):
            return None
        names.append(item)
    return tuple(names)


def _dependencies(value: object) -> tuple[tuple[str, tuple[str, ...]], ...] | None:
    """The fields each field of a `dependentRequired` value requires, or `None` when the value is not that shape.

    Args:
        value: The keyword's value, which the meta-schema requires to map each field to an array of field names.
    """
    if not isinstance(value, dict):
        return None
    dependencies: list[tuple[str, tuple[str, ...]]] = []
    for field, required in value.items():
        names = _names(required)
        if not isinstance(field, str) or names is None:
            return None
        dependencies.append((field, names))
    return tuple(dependencies)
