"""The translation of `jsonschema`'s errors into `FrontmatterProblem` values, and the walk of a schema it reads.

The one place the package reads a `jsonschema` error: `FrontmatterSchema.validate` hands each error it finds to
`_frontmatter_problems`. `_iter_schemas_within` and `_resolves_inside` walk a frontmatter schema's subschemas and
resolve its `$ref` values, which is how `FrontmatterSchema.parse` finds an `$id`, a foreign dialect or a reference
that leaves the schema.
"""

import re
from collections.abc import Iterator, Mapping
from typing import assert_never

from jsonschema._utils import find_evaluated_property_keys_by_schema
from jsonschema.exceptions import ValidationError as SchemaValidationError
from jsonschema.exceptions import best_match
from jsonschema.protocols import Validator
from referencing import Registry
from referencing.exceptions import Unresolvable
from referencing.jsonschema import DRAFT202012

from lorecraft.core.mapping import Plain
from lorecraft.core.num import UnsignedInt

from .frontmatter_problem import (
    BlockLimit,
    BlockProblem,
    FieldCount,
    FieldLimit,
    FrontmatterProblem,
    InvalidValueProblem,
    MaxFields,
    MinFields,
    MissingFieldProblem,
    OneOfValues,
    OtherBlockConstraint,
    OtherValueConstraint,
    PatternMismatch,
    UnknownFieldProblem,
    ValueConstraint,
    WrongTypeProblem,
)
from .schema_guidance import (
    find_object,
    json_type_of,
    known_fields,
    property_guidance,
    schema_guidance,
    schema_reason,
    value_text,
)
from .schema_keyword import (
    AdditionalPropertiesKeyword,
    ConstKeyword,
    DependentRequiredKeyword,
    EnumKeyword,
    Keyword,
    MaxPropertiesKeyword,
    MinPropertiesKeyword,
    OtherKeyword,
    PatternKeyword,
    RequiredKeyword,
    TypeKeyword,
    UnevaluatedPropertiesKeyword,
    keyword_of,
)


def _frontmatter_problems(
    validator: Validator, error: SchemaValidationError, data: Mapping[str, Plain]
) -> list[FrontmatterProblem]:
    """The problems one `jsonschema` error in `data` reports, each on the top-level field it concerns.

    Besides what is wrong, each problem carries what the schema states that tells a reader how to put it right: the
    field's description and example, the values it allows, the fields the schema defines, the reason a subschema
    gives in its `$comment`.

    Args:
        validator: The validator that reported the error, holding the whole schema.
        error: One error from validating `data` against the schema; its path and validator pick the problems.
        data: The frontmatter that was validated, as plain data, read to tell which fields are at fault.
    """
    keyword = keyword_of(error)
    if error.path:
        # Anything wrong below the top-level field, such as a key its value lacks, is that field's value at fault.
        field = str(error.path[0])
        if len(error.path) == 1 and isinstance(keyword, TypeKeyword):
            return [
                WrongTypeProblem(
                    field,
                    error.message,
                    keyword.names,
                    json_type_of(error.instance),
                    guidance=property_guidance(validator.schema, field),
                )
            ]
        return [_invalid_value(validator, error, keyword, field)]
    # `jsonschema` reports a key `propertyNames` rejects as the error of the keyword inside it, with the key as the
    # instance and no path, so it is told apart by the schema path. The key is written, so it has a line.
    if 'propertyNames' in error.relative_schema_path:
        return [_invalid_value(validator, error, keyword, str(error.instance))]
    # Past this point the error has no path, so the value it is about is `data` itself: read that rather than
    # `error.instance`, which `jsonschema` types as `Any`.
    match keyword:
        case RequiredKeyword(fields):
            problems: list[FrontmatterProblem] = []
            for field in fields:
                if field not in data:
                    message = f'{field!r} is a required property'
                    # The schema the keyword sits in, which holds no `properties` when `required` is a branch's.
                    problems.append(
                        MissingFieldProblem(field, message, guidance=property_guidance(error.schema, field))
                    )
            return problems
        case DependentRequiredKeyword():
            return _dependency_problems(validator, error, keyword, data)
        case AdditionalPropertiesKeyword():
            # `jsonschema` types `error.schema` to allow a boolean schema, but a keyword only fires inside an object
            # one.
            schema = _schema_object(error.schema)
            problems = []
            for key in _additional_keys(schema, data):
                # `jsonschema`'s wording for one unexpected key.
                message = f'Additional properties are not allowed ({key!r} was unexpected)'
                problems.append(UnknownFieldProblem(key, message, known_fields(schema)))
            return problems
        case UnevaluatedPropertiesKeyword():
            return _unevaluated_problems(validator, _schema_object(error.schema), data)
        case (
            TypeKeyword()
            | EnumKeyword()
            | ConstKeyword()
            | PatternKeyword()
            | MinPropertiesKeyword()
            | MaxPropertiesKeyword()
            | OtherKeyword()
        ):
            # A rule over the whole block, such as `minProperties`, concerns no field.
            return [
                BlockProblem(
                    error.message,
                    _block_constraint(keyword),
                    # A length is never negative, so building the `UnsignedInt` cannot raise `NegativeIntError` here.
                    FieldCount(UnsignedInt(len(data))),
                    description=schema_guidance(validator.schema).description,
                )
            ]
        case _:
            assert_never(keyword)


def _invalid_value(
    validator: Validator, error: SchemaValidationError, keyword: Keyword, field: str
) -> InvalidValueProblem:
    """The problem of a value breaking a constraint, on the field it is written at.

    Args:
        validator: The validator that reported the error, holding the whole schema the field's property is read from.
        error: The error the value's constraint reported; its schema is the subschema that states the constraint.
        keyword: The keyword that reported the error.
        field: The top-level field at fault.
    """
    return InvalidValueProblem(
        field,
        error.message,
        _value_constraint(keyword, nested=len(error.path) > 1),
        reason=schema_reason(error.schema),
        guidance=property_guidance(validator.schema, field),
    )


def _dependency_problems(
    validator: Validator, error: SchemaValidationError, keyword: DependentRequiredKeyword, data: Mapping[str, Plain]
) -> list[FrontmatterProblem]:
    """One problem per written field whose `dependentRequired` fields are not all written, on the written field.

    `jsonschema` words one error for each missing dependency, naming only the dependency in its record, so the
    pairs are found the way the keyword finds them, and a pair two errors report is reported once.

    Args:
        validator: The validator that reported the error, holding the whole schema.
        error: The `dependentRequired` error, which reports one missing dependency of one field.
        keyword: The error's keyword, which maps each field to the fields it requires.
        data: The frontmatter that was validated, as plain data.
    """
    problems: list[FrontmatterProblem] = []
    for field, dependencies in keyword.dependencies:
        if field not in data:
            continue
        for dependency in dependencies:
            if dependency not in data:
                message = f'{dependency!r} is a dependency of {field!r}'
                problems.append(
                    InvalidValueProblem(
                        field,
                        message,
                        OtherValueConstraint(),
                        reason=schema_reason(error.schema),
                        guidance=property_guidance(validator.schema, field),
                    )
                )
    return problems


def _value_constraint(keyword: Keyword, *, nested: bool) -> ValueConstraint:
    """The constraint a value broke, as far as a typed one describes the keyword that reported it.

    Args:
        keyword: The keyword that reported the value's constraint.
        nested: Whether the constraint sits below the field's own value, such as on the items of a list. The allowed
            values and the pattern then are not the field's, so no typed constraint names them.
    """
    if nested:
        return OtherValueConstraint()
    match keyword:
        case EnumKeyword(allowed):
            return OneOfValues(tuple(value_text(value) for value in allowed))
        case ConstKeyword(allowed):
            return OneOfValues((value_text(allowed),))
        case PatternKeyword(pattern):
            return PatternMismatch(pattern)
        case (
            TypeKeyword()
            | RequiredKeyword()
            | DependentRequiredKeyword()
            | AdditionalPropertiesKeyword()
            | UnevaluatedPropertiesKeyword()
            | MinPropertiesKeyword()
            | MaxPropertiesKeyword()
            | OtherKeyword()
        ):
            return OtherValueConstraint()
        case _:
            assert_never(keyword)


def _block_constraint(keyword: Keyword) -> BlockLimit:
    """The constraint over the whole block, as far as a typed one describes the keyword that reported it.

    Args:
        keyword: The keyword that reported the block's constraint.
    """
    match keyword:
        case MinPropertiesKeyword(limit):
            return MinFields(FieldLimit(UnsignedInt(limit)))
        case MaxPropertiesKeyword(limit):
            return MaxFields(FieldLimit(UnsignedInt(limit)))
        case (
            TypeKeyword()
            | RequiredKeyword()
            | DependentRequiredKeyword()
            | AdditionalPropertiesKeyword()
            | UnevaluatedPropertiesKeyword()
            | EnumKeyword()
            | ConstKeyword()
            | PatternKeyword()
            | OtherKeyword()
        ):
            return OtherBlockConstraint()
        case _:
            assert_never(keyword)


def _additional_keys(schema: Mapping[str, Plain], instance: Mapping[str, Plain]) -> list[str]:
    """The keys of `instance` that neither `properties` nor `patternProperties` of `schema` names.

    Args:
        schema: The object schema whose `additionalProperties` rule fired.
        instance: The mapping that was validated; its keys are checked in order.
    """
    # Absent, either keyword names nothing.
    properties = _schema_object(schema.get('properties', {}))
    pattern_properties = _schema_object(schema.get('patternProperties', {}))
    keys: list[str] = []
    for key in instance:
        if key in properties:
            continue
        if any(re.search(str(pattern), key) for pattern in pattern_properties):
            continue
        keys.append(key)
    return keys


def _unevaluated_problems(
    validator: Validator, schema: Mapping[str, Plain], data: Mapping[str, Plain]
) -> list[FrontmatterProblem]:
    """One problem per field the `unevaluatedProperties` rule of `schema` rejects.

    A field no keyword evaluated is unknown when the rule is `false`, and its value invalid when the rule is a
    schema the value breaks.

    Args:
        validator: The validator that reported the rule's error, holding the whole schema.
        schema: The object schema whose `unevaluatedProperties` rule fired.
        data: The frontmatter that was validated, as plain data.
    """
    # `jsonschema` names the rejected fields only in its message, and which fields are evaluated depends on every
    # `allOf`, `$ref` and `if` the schema composes, so they are found the way the keyword itself finds them, with
    # a helper `jsonschema` keeps private. Its major version is pinned, and the tests over a composed schema
    # fail if the helper changes.
    evaluated = find_evaluated_property_keys_by_schema(validator, data, schema)
    rule = schema['unevaluatedProperties']
    problems: list[FrontmatterProblem] = []
    for key in data:
        if key in evaluated:
            continue
        if rule is False:
            # `jsonschema`'s wording for one unexpected key.
            message = f'Unevaluated properties are not allowed ({key!r} was unexpected)'
            problems.append(UnknownFieldProblem(key, message, known_fields(schema)))
        elif isinstance(rule, Mapping):
            reason = best_match(validator.evolve(schema=rule).iter_errors(data[key]))
            if reason is not None:
                # The rule describes every field it evaluates, so its description is the key's.
                problems.append(
                    InvalidValueProblem(
                        key,
                        reason.message,
                        # The error is about the key's value itself, so a path in it leads inside that value.
                        _value_constraint(keyword_of(reason), nested=len(reason.path) > 0),
                        reason=schema_reason(reason.schema),
                        guidance=schema_guidance(rule),
                    )
                )
        # A rule of `true` accepts every value, so it never fires.
    return problems


def _schema_object(value: Plain) -> Mapping[str, Plain]:
    """A schema value the meta-schema proved is a JSON object.

    Such a value is a subschema a keyword fired in, or the value of a keyword the meta-schema requires to be an
    object, such as `properties`. `jsonschema` types both loosely, so this is the one place the module turns one
    into a `Mapping`: the proof is `FrontmatterSchema`'s construction, which `ty` cannot see.

    Args:
        value: A value read from a schema a `FrontmatterSchema` holds, or from an error validating against one.
    """
    schema = find_object(value)
    if schema is None:
        # Every caller passes a value the meta-schema, checked when the schema was loaded, requires to be an object.
        raise AssertionError('unreachable: the meta-schema proved this schema value is an object')
    return schema


def _resolves_inside(registry: Registry, ref: str) -> bool:
    """Whether a `$ref` or `$dynamicRef` names a schema inside the one schema the registry holds.

    Only a reference that is empty or opens with `#` can: any other names another resource, which is never fetched,
    so it is refused without being looked up. What it names must be a schema, an object or a boolean, as `jsonschema`
    raises when it reads anything else, such as `#/required/0`, as one.

    Args:
        registry: A registry holding the schema alone, under the empty base URI.
        ref: What the reference holds, as written; the empty reference is the schema itself, as `#` is.
    """
    if ref and not ref.startswith('#'):
        return False
    try:
        target = registry.resolver().lookup(ref).contents
    except Unresolvable:
        return False
    return isinstance(target, Mapping | bool)


def _iter_schemas_within(schema: Mapping[str, Plain]) -> Iterator[Mapping[str, Plain]]:
    """The schema itself, then every object subschema inside it, at any depth.

    Only the places Draft 2020-12 reads a schema from are walked, such as `properties` or `items`, so a value
    under `enum` or `const` that happens to hold `$id` is data, not a schema, and is not visited. A boolean
    subschema holds no keyword, so it is skipped.

    Args:
        schema: The schema to walk; it is yielded first, unchanged.
    """
    yield schema
    for subschema in DRAFT202012.subresources_of(schema):
        if isinstance(subschema, Mapping):
            yield from _iter_schemas_within(subschema)
