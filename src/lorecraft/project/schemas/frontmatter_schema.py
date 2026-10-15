"""The frontmatter schema a structure specification states, and the problems it reports a document's frontmatter in.

`FrontmatterSchema` is the `frontmatter` key of a structure specification: a Draft 2020-12 JSON Schema a document's
frontmatter must satisfy. `parse` checks the schema once, where the specification loads, and returns the failure it
finds; `validate` then holds one decoded frontmatter to it. `validate` translates `jsonschema`'s errors into
`FrontmatterProblem` values here, because this is the one place the package reads a `jsonschema` error.

`StatedFrontmatterSchema` pairs a checked schema with the structure specification that states it, so a problem can
quote the file it comes from.

Nothing here logs: `validate` raises nothing, and `parse` returns the failure it finds.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Self, assert_never

from jsonschema import Draft202012Validator
from jsonschema._utils import find_evaluated_property_keys_by_schema
from jsonschema.exceptions import SchemaError, best_match
from jsonschema.exceptions import ValidationError as SchemaValidationError
from jsonschema.protocols import Validator

from lorecraft.core.error import Unreachable
from lorecraft.core.mapping import Frozen, FrozenMapping, Plain
from lorecraft.core.num import UnsignedInt
from lorecraft.core.path import RootRelativePath
from lorecraft.jsonschema import (
    DIALECT,
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
    find_same_instance_ref_cycle,
    is_resolved_inside,
    iter_schemas,
    keyword_of,
)

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
from .structure_failure import (
    CyclicFrontmatterSchemaRef,
    ForeignFrontmatterDialect,
    IdentifiedFrontmatterSchema,
    InvalidFrontmatterSchema,
    UnresolvableFrontmatterSchemaRef,
    UntypedFrontmatterSchema,
)

type FrontmatterSchemaFailure = (
    InvalidFrontmatterSchema
    | IdentifiedFrontmatterSchema
    | ForeignFrontmatterDialect
    | UnresolvableFrontmatterSchemaRef
    | CyclicFrontmatterSchemaRef
    | UntypedFrontmatterSchema
)
"""A reason a structure specification's `frontmatter` schema cannot be held."""


@dataclass(frozen=True, slots=True)
class FrontmatterSchema:
    """A structure specification's `frontmatter` key: a Draft 2020-12 JSON Schema describing an object.

    `parse` is the one way in for a schema that is not yet known to be usable: it checks the schema and returns the
    failure it finds instead of an instance, so an instance it returns is proof of the check and no code holding one
    checks it again. Calling `FrontmatterSchema(...)` directly is unchecked, and is only for a schema already checked.
    The file's path is the structure specification's own (`StructureSpec.path`), not kept here.

    Attributes:
        schema: The decoded schema, frozen all the way down: every object in it is a `FrozenMapping` and every
            array a tuple, so no holder can write to the schema `parse` checked, at any depth.
    """

    schema: FrozenMapping[str, Frozen]

    @classmethod
    def parse(cls, schema: FrozenMapping[str, Frozen]) -> Self | FrontmatterSchemaFailure:
        """Check a schema a structure specification can hold a document's frontmatter to.

        That is a schema that is a well-formed Draft 2020-12 schema, that does not leave it for another resource or
        dialect anywhere inside it, whose every `$ref` resolves inside it without a cycle, and that describes an object.

        Args:
            schema: The file's `frontmatter` JSON Schema, as read.

        Returns:
            The checked schema, or the failure naming what is wrong with it: the meta-schema's rejection, an `$id`, a
            dialect other than Draft 2020-12 in `$schema`, a `$ref` that does not resolve inside the schema, a `$ref`
            cycle that reaches no keyword, or a root that does not say `"type": "object"`.
        """
        # `jsonschema` takes a JSON object only as a `dict` and an array only as a `list`, so every schema and
        # frontmatter it reads is handed to it as plain data, copied from the frozen value.
        plain = schema.to_plain()
        try:
            Draft202012Validator.check_schema(plain)
        except SchemaError as exc:
            return InvalidFrontmatterSchema(exc.message)
        # No `$id` is allowed below, so the whole schema is one resource, and every `$ref` is read against it.
        for subschema in iter_schemas(plain):
            if '$id' in subschema:
                # An `$id` would make that schema a resource of its own, with its own base URI, and so change what
                # every relative `$ref` beneath it resolves to.
                return IdentifiedFrontmatterSchema()
            dialect = subschema.get('$schema', DIALECT)
            if not isinstance(dialect, str):
                # SAFETY: the meta-schema check above has refused a `$schema` that is not a string
                raise Unreachable('the meta-schema proved `$schema` is a string')
            if dialect != DIALECT:
                # The check applies every schema under Draft 2020-12, so a schema written for another dialect would
                # be read by rules it was not written for.
                return ForeignFrontmatterDialect(dialect)
            for keyword in ('$ref', '$dynamicRef'):
                ref = subschema.get(keyword)
                if ref is None:
                    continue
                if not isinstance(ref, str):
                    # SAFETY: the meta-schema check above has refused a reference that is not a string
                    raise Unreachable(f'the meta-schema proved `{keyword}` is a string')
                if not is_resolved_inside(plain, ref):
                    # `validate` raises nothing, and `jsonschema` raises when it meets a reference that does not
                    # resolve to a schema, so it is refused here, where the schema is loaded.
                    return UnresolvableFrontmatterSchemaRef(ref)
        # Every `$ref` resolves, so a cycle among them can be followed.
        cycle = find_same_instance_ref_cycle(plain)
        if cycle is not None:
            return CyclicFrontmatterSchemaRef(cycle)
        # A frontmatter is a mapping, so the schema must say so itself: a schema that left `type` out would accept
        # a list or a string where the frontmatter should be.
        if schema.get('type') != 'object':
            return UntypedFrontmatterSchema()
        return cls(schema=schema)

    def validate(self, data: FrozenMapping[str, Frozen]) -> tuple[FrontmatterProblem, ...]:
        """Hold one decoded frontmatter to the schema. Pure: raises nothing.

        The messages are `jsonschema`'s own, unlike `SkillFrontmatterSchema`'s: the schema is the
        repository's, so the validator's wording names constraints its authors wrote. Three errors `jsonschema`
        reports on the whole block are split instead, in its own wording: an absent required field, each field
        `additionalProperties` does not allow, and each field `unevaluatedProperties` rejects get a problem of
        their own, on that field.

        Args:
            data: The decoded frontmatter mapping, frozen all the way down, every key a string at any depth, as JSON
                names keys.

        Returns:
            One problem per field at fault, ordered by the field and then the message, or `()` when the
            frontmatter conforms.
        """
        # Plain data, as `parse` hands `jsonschema` the schema: it reads only a `dict` as a JSON object.
        validator = Draft202012Validator(self.schema.to_plain())
        plain = data.to_plain()
        # Sorted, unlike the skill schema's problems: `jsonschema` reports errors in the order it walks the
        # schema's keywords, which says nothing about the fields.
        errors = sorted(
            validator.iter_errors(plain),
            key=lambda error: (tuple(str(part) for part in error.path), error.message),
        )
        problems: list[FrontmatterProblem] = []
        for error in errors:
            for problem in _frontmatter_problems(validator, error, plain):
                # One `required` error names one absent field, but its record lists all the schema requires, so
                # every such error below would report every absent field again.
                if problem not in problems:
                    problems.append(problem)
        return tuple(problems)


@dataclass(frozen=True, slots=True)
class StatedFrontmatterSchema:
    """A frontmatter schema with the structure specification that states it.

    Attributes:
        spec: Root-relative path of the structure specification the schema is written in, quoted verbatim in
            every problem it reports.
        schema: The frontmatter schema that specification states.
    """

    spec: RootRelativePath
    schema: FrontmatterSchema


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
                problems.append(UnknownFieldProblem(key, message, known_fields=known_fields(schema)))
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
            problems.append(UnknownFieldProblem(key, message, known_fields=known_fields(schema)))
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
        # SAFETY: every caller passes a value the meta-schema, checked when the schema was loaded, requires an object.
        raise Unreachable('the meta-schema proved this schema value is an object')
    return schema
