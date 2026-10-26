"""The frontmatter schema a structure specification states, and the problems it reports a document's frontmatter in.

`FrontmatterSchema` is the `frontmatter` key of a structure specification: a Draft 2020-12 JSON Schema a document's
frontmatter must satisfy. `parse` checks the schema once, where the specification loads, and returns the failure it
finds; `validate` then holds one decoded frontmatter to it. It maps the library-independent violations returned by
`lorecraft.jsonschema` into project-owned `FrontmatterProblem` values.

`StatedFrontmatterSchema` pairs a checked schema with the structure specification that states it, so a problem can
quote the file it comes from.

Nothing here logs: `validate` raises nothing, and `parse` returns the failure it finds.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Self, assert_never

from lorecraft.core.error import Unreachable
from lorecraft.core.mapping import Frozen, FrozenMapping, Plain
from lorecraft.core.num import UnsignedInt
from lorecraft.core.path import RootRelativePath
from lorecraft.jsonschema import (
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
    SchemaHasIdentifier,
    SchemaHasSameInstanceReferenceCycle,
    SchemaHasUnresolvableReference,
    SchemaMetaError,
    SchemaUsesForeignDialect,
    TypeKeyword,
    UnevaluatedPropertiesKeyword,
    Violation,
    additional_message,
    best_violation,
    check_schema,
    dependency_message,
    required_message,
    unevaluated_message,
    validate,
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
    CyclicFrontmatterSchemaRefKeyword,
    ForeignFrontmatterDialect,
    IdentifiedFrontmatterSchema,
    InvalidFrontmatterSchema,
    UnresolvableFrontmatterSchemaRefKeyword,
    UntypedFrontmatterSchema,
)

type FrontmatterSchemaFailure = (
    InvalidFrontmatterSchema
    | IdentifiedFrontmatterSchema
    | ForeignFrontmatterDialect
    | UnresolvableFrontmatterSchemaRefKeyword
    | CyclicFrontmatterSchemaRefKeyword
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
        plain = schema.to_plain()
        failure = check_schema(plain)
        match failure:
            case SchemaMetaError(message):
                return InvalidFrontmatterSchema(message)
            case SchemaHasIdentifier():
                return IdentifiedFrontmatterSchema()
            case SchemaUsesForeignDialect(dialect):
                return ForeignFrontmatterDialect(dialect)
            case SchemaHasUnresolvableReference(reference):
                return UnresolvableFrontmatterSchemaRefKeyword(reference)
            case SchemaHasSameInstanceReferenceCycle(reference):
                return CyclicFrontmatterSchemaRefKeyword(reference)
            case None:
                pass
            case _:
                assert_never(failure)
        # A frontmatter is a mapping, so the schema must say so itself: a schema that left `type` out would accept
        # a list or a string where the frontmatter should be.
        if schema.get('type') != 'object':
            return UntypedFrontmatterSchema()
        return cls(schema=schema)

    def validate(self, data: FrozenMapping[str, Frozen]) -> tuple[FrontmatterProblem, ...]:
        """Hold one decoded frontmatter to the schema. Pure: raises nothing.

        The messages are `jsonschema`'s own, unlike `AgentSkillsFrontmatterSchema`'s: the schema is the
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
        plain = data.to_plain()
        root_schema = self.schema.to_plain()
        problems: list[FrontmatterProblem] = []
        for violation in validate(root_schema, plain):
            for problem in _frontmatter_problems(violation, root_schema, plain):
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
    violation: Violation, root_schema: Mapping[str, Plain], data: Mapping[str, Plain]
) -> list[FrontmatterProblem]:
    """The problems one `jsonschema` error in `data` reports, each on the top-level field it concerns.

    Besides what is wrong, each problem carries what the schema states that tells a reader how to put it right: the
    field's description and example, the values it allows, the fields the schema defines, the reason a subschema
    gives in its `$comment`.

    Args:
        root_schema: The complete schema, read by project-owned schema guidance.
        violation: The validator details that select and describe the problem.
        data: The frontmatter that was validated, as plain data, read to tell which fields are at fault.
    """
    keyword = violation.keyword
    schema = _thaw(violation.schema)
    if violation.path:
        # Anything wrong below the top-level field, such as a key its value lacks, is that field's value at fault.
        field = str(violation.path[0])
        if len(violation.path) == 1 and isinstance(keyword, TypeKeyword):
            return [
                WrongTypeProblem(
                    field,
                    violation.message,
                    keyword.names,
                    json_type_of(violation.instance),
                    guidance=property_guidance(root_schema, field),
                )
            ]
        return [_invalid_value(violation, root_schema, keyword, field)]
    # `jsonschema` reports a key `propertyNames` rejects as the error of the keyword inside it, with the key as the
    # instance and no path, so it is told apart by the schema path. The key is written, so it has a line.
    if 'propertyNames' in violation.schema_path:
        return [_invalid_value(violation, root_schema, keyword, str(violation.instance))]
    # Past this point the error has no path, so the value it is about is `data` itself: read that rather than
    # `error.instance`, which `jsonschema` types as `Any`.
    match keyword:
        case RequiredKeyword(fields):
            problems: list[FrontmatterProblem] = []
            for field in fields:
                if field not in data:
                    message = required_message(field)
                    # The schema the keyword sits in, which holds no `properties` when `required` is a branch's.
                    problems.append(MissingFieldProblem(field, message, guidance=property_guidance(schema, field)))
            return problems
        case DependentRequiredKeyword():
            return _dependency_problems(violation, root_schema, keyword, data)
        case AdditionalPropertiesKeyword():
            # `jsonschema` types `error.schema` to allow a boolean schema, but a keyword only fires inside an object
            # one.
            object_schema = _schema_object(schema)
            problems = []
            for key in _additional_keys(object_schema, data):
                message = additional_message(key)
                problems.append(UnknownFieldProblem(key, message, known_fields=known_fields(object_schema)))
            return problems
        case UnevaluatedPropertiesKeyword():
            return _unevaluated_problems(violation, _schema_object(schema), root_schema, data)
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
                    violation.message,
                    _block_constraint(keyword),
                    # A length is never negative, so building the `UnsignedInt` cannot raise `NegativeIntError` here.
                    FieldCount(UnsignedInt(len(data))),
                    description=schema_guidance(root_schema).description,
                )
            ]
        case _:
            assert_never(keyword)


def _invalid_value(
    violation: Violation, root_schema: Mapping[str, Plain], keyword: Keyword, field: str
) -> InvalidValueProblem:
    """The problem of a value breaking a constraint, on the field it is written at.

    Args:
        violation: The validator details for the value's failed constraint.
        root_schema: The complete schema, read by project-owned schema guidance.
        keyword: The keyword that reported the error.
        field: The top-level field at fault.
    """
    return InvalidValueProblem(
        field,
        violation.message,
        _value_constraint(keyword, nested=len(violation.path) > 1),
        reason=schema_reason(_thaw(violation.schema)),
        guidance=property_guidance(root_schema, field),
    )


def _dependency_problems(
    violation: Violation, root_schema: Mapping[str, Plain], keyword: DependentRequiredKeyword, data: Mapping[str, Plain]
) -> list[FrontmatterProblem]:
    """One problem per written field whose `dependentRequired` fields are not all written, on the written field.

    `jsonschema` words one error for each missing dependency, naming only the dependency in its record, so the
    pairs are found the way the keyword finds them, and a pair two errors report is reported once.

    Args:
        violation: The validator details, whose schema states the dependencies.
        root_schema: The complete schema, read by project-owned schema guidance.
        keyword: The error's keyword, which maps each field to the fields it requires.
        data: The frontmatter that was validated, as plain data.
    """
    problems: list[FrontmatterProblem] = []
    for field, dependencies in keyword.dependencies:
        if field not in data:
            continue
        for dependency in dependencies:
            if dependency not in data:
                message = dependency_message(field, dependency)
                problems.append(
                    InvalidValueProblem(
                        field,
                        message,
                        OtherValueConstraint(),
                        reason=schema_reason(_thaw(violation.schema)),
                        guidance=property_guidance(root_schema, field),
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
            return MinFields(FieldLimit(limit))
        case MaxPropertiesKeyword(limit):
            return MaxFields(FieldLimit(limit))
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
    violation: Violation,
    schema: Mapping[str, Plain],
    root_schema: Mapping[str, Plain],
    data: Mapping[str, Plain],
) -> list[FrontmatterProblem]:
    """One problem per field the `unevaluatedProperties` rule of `schema` rejects.

    A field no keyword evaluated is unknown when the rule is `false`, and its value invalid when the rule is a
    schema the value breaks.

    Args:
        violation: The validator details, including properties evaluated by this schema.
        schema: The object schema whose `unevaluatedProperties` rule fired.
        root_schema: The complete schema that supplies local reference targets.
        data: The frontmatter that was validated, as plain data.
    """
    # `jsonschema` names the rejected fields only in its message, and which fields are evaluated depends on every
    # `allOf`, `$ref` and `if` the schema composes, so they are found the way the keyword itself finds them, with
    # a helper `jsonschema` keeps private. Its major version is pinned, and the tests over a composed schema
    # fail if the helper changes.
    evaluated = violation.evaluated_properties
    rule = schema['unevaluatedProperties']
    problems: list[FrontmatterProblem] = []
    for key in data:
        if key in evaluated:
            continue
        if rule is False:
            message = unevaluated_message(key)
            problems.append(UnknownFieldProblem(key, message, known_fields=known_fields(schema)))
        elif isinstance(rule, Mapping):
            reason = best_violation(rule, data[key], root_schema=root_schema)
            if reason is not None:
                # The rule describes every field it evaluates, so its description is the key's.
                problems.append(
                    InvalidValueProblem(
                        key,
                        reason.message,
                        # The error is about the key's value itself, so a path in it leads inside that value.
                        _value_constraint(reason.keyword, nested=len(reason.path) > 0),
                        reason=schema_reason(_thaw(reason.schema)),
                        guidance=schema_guidance(rule),
                    )
                )
        # A rule of `true` accepts every value, so it never fires.
    return problems


def _thaw(value: Frozen) -> Plain:
    """Copy an owned frozen JSON value into the plain containers project guidance reads.

    Args:
        value: A frozen scalar, tuple, or `FrozenMapping` read from a `Violation`.
    """
    match value:
        case FrozenMapping():
            return value.to_plain()
        case tuple():
            return [_thaw(item) for item in value]
        case str():
            return value
        case bool():
            return value
        case int():
            return value
        case float():
            return value
        case None:
            return None
        case _:
            assert_never(value)


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
