r"""The structure specification: its file's decoded JSON, and the rules it is decoded into.

The repository reads a `<name>.structure.json` file's text, a `StructureSchema`, which proves nothing about
it. `StructureSpec.parse` is the check, in two steps at the edge. It deserializes the text straight into the
strict, frozen `StructureFile` model, so JSON that is malformed or not the dialect's shape is refused before
any rule is read. Then it maps the model to typed rules, and building the specification refuses a set of rules that
checks nothing or contradicts itself, which no shape can state. So every `StructureSpec` that exists states
usable rules, however it was built.

A document's outline is a sequence whose length varies, and JSON Schema cannot state an order over one, so a
structure specification is not JSON Schema. It is this small dialect, whose fields `structure_file` declares:

    {
      "$schema": "../schemas/structure.spec.json",
      "description": "what this file governs, for whoever opens it",
      "title": {"count": 1, "first": true},
      "empty_sections": "forbidden",
      "tokens": 5000,
      "frontmatter": {"type": "object", "required": ["name"], "properties": {"name": {"type": "string"}}},
      "outline": [
        {"section": "Table of Contents", "optional": true},
        {"any": true, "words": 350},
        {
          "section": "Checklist",
          "words": 250,
          "description": "The items a reviewer verifies before committing a change the document governs.",
          "examples": ["- [ ] Every new record is a `@dataclass`\n- [ ] Every record used as a key is frozen"]
        }
      ],
      "forbidden": ["Changelog"]
    }

The file does not name the prose it is the machine-checkable half of: that is `<name>.md` beside it, and every
finding quotes it.

- `$schema` points editors at `docs/schemas/structure.spec.json`, the JSON Schema `just gen` renders from
  `structure_file`; it is not kept. That schema states the shape only: the rules `StructureSpec` refuses
  below it cannot state.
- `description` is read by people only, and is not kept.
- `title` states how many H1 titles a document carries, and whether one opens it ahead of every section.
- `empty_sections`, whose one value is `"forbidden"`, reports a section left without content.
- `tokens` is the token budget: the most tokens the whole file may hold, frontmatter, code and tables
  included, since that is what loading it costs an agent. The count is `o200k_base`, the same whichever agent
  reads it. The budget check applies it, not the structure check: it reads the raw file, not the parse tree.
- `frontmatter` is a Draft 2020-12 JSON Schema the document's frontmatter must satisfy. Unlike the rest of the
  file it is JSON Schema, not the dialect: a frontmatter is a mapping, which JSON Schema states well. Its root must
  say `"type": "object"` outright, and no schema in it, at any depth, may carry `$id` or name another dialect
  in `$schema`. The frontmatter check applies it, not the structure check: it reads the frontmatter, not the
  headings. `FrontmatterSchema.validate` translates `jsonschema`'s errors into `FrontmatterProblem` values
  here, beside the decoding, because this is the one place the package reads a `jsonschema` error.
- `outline` is the order of the document's sections. A `section` entry names one and is required unless
  `optional`; an `any` entry matches a run of sections the outline does not name. An entry's `words` caps
  the prose words of each section it matches, H3 subsections included: on an `any` entry that is every section
  in the run alone, not the run's total. An entry without `words` caps nothing. A word is a whitespace-delimited
  token of prose; fenced code and table rows are not counted. A `section` entry's `description` says what the
  section holds and its `examples` are Markdown samples of its body; when a document lacks the section, the
  structure check reports the description and the first example as notes, and leaves the rest to a reader.
- `forbidden` names sections that must not appear at all.

Nothing here logs: the command that loads the model catches every `Error` that escapes it and reports it.
"""

import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from itertools import pairwise
from typing import NewType, Self, assert_never

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from jsonschema.exceptions import ValidationError as SchemaValidationError
from pydantic import JsonValue, ValidationError
from referencing.jsonschema import DRAFT202012

from lorecraft.core.error import Error
from lorecraft.core.path import RootRelativePath

from .frontmatter_problem import (
    BlockProblem,
    FrontmatterProblem,
    InvalidValueProblem,
    MissingFieldProblem,
    NonStringKeyProblem,
    UnknownFieldProblem,
    WrongTypeProblem,
)
from .spec_file import SpecFileType, StructureSpecFile, spec_filename
from .structure_file import (
    JSON_SCHEMA_DIALECT,
    StructureFile,
    StructureFileAny,
    StructureFileSection,
    StructureFileTitle,
)

# The text of a structure specification file as read, not yet known to be JSON, the dialect's shape or usable
# rules. A NewType only keeps it apart from other text; `StructureSpec.parse` is what proves it.
StructureSchema = NewType('StructureSchema', str)


class StructureSpecDecodeError(Error):
    """A structure specification file is not JSON, or does not have the structure dialect's shape.

    Attributes:
        path: Root-relative path of the rejected file.
        problems: Every problem found, as ``<field path>: <message>``, read from the validation error.
        source: The validation error.
    """

    path: RootRelativePath
    problems: tuple[str, ...]
    source: ValidationError

    def __init__(self, path: RootRelativePath, problems: tuple[str, ...], *, source: ValidationError) -> None:
        self.path = path
        self.problems = problems
        self.source = source
        super().__init__(f'invalid structure schema {path}: {"; ".join(problems)}')
        self.__cause__ = source


class EmptyStructureSpecError(Error):
    """A structure specification states no rule, so it would check nothing.

    Attributes:
        path: Root-relative path of the rejected file.
    """

    path: RootRelativePath

    def __init__(self, path: RootRelativePath) -> None:
        self.path = path
        super().__init__(f'invalid structure schema {path}: states no rule, so it would check nothing')


class InvalidTitleCountError(Error):
    """A structure specification's title count is below 1.

    Attributes:
        path: Root-relative path of the rejected file.
        count: The count it states.
    """

    path: RootRelativePath
    count: int

    def __init__(self, path: RootRelativePath, count: int) -> None:
        self.path = path
        self.count = count
        super().__init__(f'invalid structure schema {path}: title count must be at least 1, got {count}')


class InvalidTokenBudgetError(Error):
    """A structure specification's token budget is below 1.

    Attributes:
        path: Root-relative path of the rejected file.
        tokens: The budget it states.
    """

    path: RootRelativePath
    tokens: int

    def __init__(self, path: RootRelativePath, tokens: int) -> None:
        self.path = path
        self.tokens = tokens
        super().__init__(f'invalid structure schema {path}: token budget must be at least 1, got {tokens}')


class InvalidWordCapError(Error):
    """An outline entry's word cap is below 1.

    Attributes:
        path: Root-relative path of the rejected file.
        entry: The outline entry that states the cap.
        words: The cap it states.
    """

    path: RootRelativePath
    entry: 'OutlineEntry'
    words: int

    def __init__(self, path: RootRelativePath, entry: 'OutlineEntry', words: int) -> None:
        self.path = path
        self.entry = entry
        self.words = words
        super().__init__(
            f'invalid structure schema {path}: outline word cap must be at least 1, got {words} on '
            f'{_describe_entry(entry)}'
        )


class RepeatedOutlineSectionError(Error):
    """An outline names one section more than once.

    Attributes:
        path: Root-relative path of the rejected file.
        sections: The repeated section names, sorted.
    """

    path: RootRelativePath
    sections: tuple[str, ...]

    def __init__(self, path: RootRelativePath, sections: tuple[str, ...]) -> None:
        self.path = path
        self.sections = sections
        super().__init__(
            f'invalid structure schema {path}: names sections more than once in the outline: {list(sections)}'
        )


class ForbiddenOutlineSectionError(Error):
    """A structure specification forbids a section its own outline names.

    Attributes:
        path: Root-relative path of the rejected file.
        sections: The sections both named and forbidden, sorted.
    """

    path: RootRelativePath
    sections: tuple[str, ...]

    def __init__(self, path: RootRelativePath, sections: tuple[str, ...]) -> None:
        self.path = path
        self.sections = sections
        super().__init__(f'invalid structure schema {path}: forbids sections its own outline names: {list(sections)}')


class AdjacentAnyRunsError(Error):
    """An outline places two ``any`` runs side by side, which match exactly what one run matches.

    Attributes:
        path: Root-relative path of the rejected file.
    """

    path: RootRelativePath

    def __init__(self, path: RootRelativePath) -> None:
        self.path = path
        super().__init__(f'invalid structure schema {path}: places two `any` runs side by side')


class InvalidFrontmatterSchemaError(Error):
    """A frontmatter schema is rejected by the Draft 2020-12 meta-schema.

    Attributes:
        path: Root-relative path of the structure specification the schema is written in.
        problem: What the meta-schema rejected, read from the schema error.
        source: The schema error.
    """

    path: RootRelativePath
    problem: str
    source: SchemaError

    def __init__(self, path: RootRelativePath, problem: str, *, source: SchemaError) -> None:
        self.path = path
        self.problem = problem
        self.source = source
        super().__init__(f'invalid structure schema {path}: frontmatter is not a valid JSON Schema: {problem}')
        self.__cause__ = source


class FrontmatterSchemaIdError(Error):
    """A schema inside a frontmatter schema carries ``$id``, which would make it a resource of its own.

    Attributes:
        path: Root-relative path of the structure specification the schema is written in.
    """

    path: RootRelativePath

    def __init__(self, path: RootRelativePath) -> None:
        self.path = path
        super().__init__(f'invalid structure schema {path}: frontmatter schema may not carry $id')


class ForeignFrontmatterDialectError(Error):
    """A schema inside a frontmatter schema names a dialect other than Draft 2020-12 in ``$schema``.

    Attributes:
        path: Root-relative path of the structure specification the schema is written in.
        dialect: The dialect it names.
    """

    path: RootRelativePath
    dialect: object

    def __init__(self, path: RootRelativePath, dialect: object) -> None:
        self.path = path
        self.dialect = dialect
        super().__init__(
            f'invalid structure schema {path}: frontmatter schema names {dialect!r} in $schema; only '
            f'{JSON_SCHEMA_DIALECT} is allowed'
        )


class UntypedFrontmatterSchemaError(Error):
    """A frontmatter schema's root does not state ``"type": "object"``.

    Attributes:
        path: Root-relative path of the structure specification the schema is written in.
    """

    path: RootRelativePath

    def __init__(self, path: RootRelativePath) -> None:
        self.path = path
        super().__init__(f'invalid structure schema {path}: frontmatter schema root must state "type": "object"')


@dataclass(frozen=True, slots=True)
class TitleRule:
    """How many H1 titles a document carries, and whether one opens it.

    Attributes:
        count: The number of H1 titles; at least 1, which `StructureSpec` checks.
        first: True when an H1 title must come before any other heading.
    """

    count: int
    first: bool


@dataclass(frozen=True, slots=True)
class SectionEntry:
    """An outline entry naming one section, and fixing its position against every other name in the outline.

    Attributes:
        name: The section's heading text.
        optional: True when a document may leave the section out; False, the default, when it must carry it.
        words: The most prose words the section may hold, its H3 subsections included, or None, the default, for
            no cap; at least 1, which `StructureSpec` checks.
        description: What the section holds, reported as help when a document lacks the section, or None, the
            default, for no help.
        examples: Markdown samples of the section's body, each without its heading, or empty, the default, for
            none. The first is reported as a note when a document lacks the section; the rest are for a reader of
            the specification.
    """

    name: str
    optional: bool = False
    # Checked by the enclosing `StructureSpec` rather than here, so a bad cap is refused as an
    # `InvalidWordCapError` naming the specification file, which this record does not know.
    words: int | None = None
    description: str | None = None
    examples: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AnySections:
    """An outline entry matching a run, of any length, of sections the outline does not name.

    The run stops at any section the outline names, which pins that name to its own entry wherever it turns up.

    Attributes:
        words: The most prose words each section in the run may hold, its H3 subsections included, or None, the
            default, for no cap. It caps every section alone, not the run's total; at least 1, which
            `StructureSpec` checks.
    """

    # Checked by the enclosing `StructureSpec` rather than here, so a bad cap is refused as an
    # `InvalidWordCapError` naming the specification file, which this record does not know.
    words: int | None = None


type OutlineEntry = SectionEntry | AnySections
"""One entry of a structure specification's outline."""


@dataclass(frozen=True, slots=True)
class FrontmatterSchema:
    """A structure specification's ``frontmatter`` key: a Draft 2020-12 JSON Schema describing an object.

    Construction checks the schema, so an instance is proof of it: no code holding a ``FrontmatterSchema`` checks
    it again. A malformed schema is refused with an error naming the specification file,
    like every other rule of that file.

    Frozen for equality only: ``schema`` holds a dict, so instances are not hashable and must not be put in a set or
    used as a key.

    Attributes:
        path: Root-relative path of the structure specification the schema is written in, quoted verbatim in
            every violation it yields.
        schema: The decoded schema. Values are ``object`` because a JSON Schema is recursive and JSON decodes each
            value to its own Python type. A ``Mapping``, not a ``dict``, so no holder can write to the schema
            the construction checked.
    """

    path: RootRelativePath
    schema: Mapping[str, object]

    def __post_init__(self) -> None:
        """Refuse a schema a structure specification cannot hold a document's frontmatter to.

        That is a schema that is not a well-formed Draft 2020-12 schema, that leaves it for another resource or
        dialect anywhere inside it, or that does not describe an object.

        Raises:
            InvalidFrontmatterSchemaError: If the schema is rejected by the Draft 2020-12 meta-schema.
            FrontmatterSchemaIdError: If any schema in it carries `$id`.
            ForeignFrontmatterDialectError: If any schema in it names a dialect other than Draft 2020-12 in
                `$schema`.
            UntypedFrontmatterSchemaError: If its root does not say `"type": "object"`.
        """
        try:
            Draft202012Validator.check_schema(self.schema)
        except SchemaError as exc:
            raise InvalidFrontmatterSchemaError(self.path, exc.message, source=exc) from exc
        for subschema in _schemas_within(self.schema):
            if '$id' in subschema:
                # An `$id` would make that schema a resource of its own, with its own base URI, and so change what
                # every relative `$ref` beneath it resolves to.
                raise FrontmatterSchemaIdError(self.path)
            dialect = subschema.get('$schema', JSON_SCHEMA_DIALECT)
            if dialect != JSON_SCHEMA_DIALECT:
                # The check applies every schema under Draft 2020-12, so a schema written for another dialect would
                # be read by rules it was not written for.
                raise ForeignFrontmatterDialectError(self.path, dialect)
        # A frontmatter is a mapping, so the schema must say so itself: a schema that left `type` out would accept
        # a list or a string where the frontmatter should be.
        if self.schema.get('type') != 'object':
            raise UntypedFrontmatterSchemaError(self.path)

    def validate(self, data: Mapping[object, object]) -> tuple[FrontmatterProblem, ...]:
        """Hold one decoded frontmatter to the schema. Pure: raises nothing.

        The messages are `jsonschema`'s own, unlike `SkillFrontmatterSchema`'s: the schema is the
        repository's, so the validator's wording names constraints its authors wrote. Two errors `jsonschema`
        reports on the whole block are split instead, in its own wording: an absent required field, and each
        field the schema does not allow, get a problem of their own, on that field.

        Args:
            data: The decoded frontmatter mapping. Keys that are not strings are reported, not rejected.

        Returns:
            One problem per field at fault, ordered by the field and then the message, or ``()`` when the
            frontmatter conforms.
        """
        validator = Draft202012Validator(self.schema)
        # Sorted, unlike the skill schema's problems: `jsonschema` reports errors in the order it walks the
        # schema's keywords, which says nothing about the fields.
        errors = sorted(
            validator.iter_errors(data),
            key=lambda error: (tuple(str(part) for part in error.path), error.message),
        )
        problems: list[FrontmatterProblem] = []
        for error in errors:
            for problem in _frontmatter_problems(error, data):
                # One `required` error names one absent field, but its record lists all the schema requires, so
                # every such error below would report every absent field again.
                if problem not in problems:
                    problems.append(problem)
        return tuple(problems)


def _frontmatter_problems(error: SchemaValidationError, data: Mapping[object, object]) -> list[FrontmatterProblem]:
    """The problems one `jsonschema` error in `data` reports, each on the top-level field it concerns.

    Args:
        error: One error from validating `data` against the schema; its path and validator pick the problems.
        data: The frontmatter that was validated, read to tell which required fields are absent.
    """
    if error.path:
        # Anything wrong below the top-level field, such as a key its value lacks, is that field's value at fault.
        field = str(error.path[0])
        if len(error.path) == 1 and error.validator == 'type':
            return [WrongTypeProblem(field, error.message)]
        return [InvalidValueProblem(field, error.message)]
    # Past this point the error has no path, so the value it is about is `data` itself: read that rather than
    # `error.instance`, which `jsonschema` types as `Any`.
    if error.validator == 'required':
        # `jsonschema` types `error.validator_value` as `Any`; the meta-schema proved `required` is an array.
        if not isinstance(error.validator_value, list):
            raise AssertionError('unreachable: `required` is an array of field names')
        problems: list[FrontmatterProblem] = []
        for required in error.validator_value:
            field = str(required)
            if field not in data:
                message = f'{field!r} is a required property'
                problems.append(MissingFieldProblem(field, message))
        return problems
    if error.validator == 'additionalProperties':
        # `jsonschema` types `error.schema` to allow a boolean schema, but a keyword only fires inside an object one.
        problems = []
        for key in _additional_keys(_schema_object(error.schema), data):
            # `jsonschema`'s wording for one unexpected key; a key that is not a string names no field.
            message = f'Additional properties are not allowed ({key!r} was unexpected)'
            if isinstance(key, str):
                problems.append(UnknownFieldProblem(key, message))
            else:
                problems.append(NonStringKeyProblem(message))
        return problems
    # A rule over the whole block, such as `minProperties`, concerns no field.
    return [BlockProblem(error.message)]


def _additional_keys(schema: Mapping[str, object], instance: Mapping[object, object]) -> list[object]:
    """The keys of `instance` that neither `properties` nor `patternProperties` of `schema` names.

    Args:
        schema: The object schema whose `additionalProperties` rule fired.
        instance: The mapping that was validated; its keys are checked in order.
    """
    # Absent, either keyword names nothing.
    properties = _schema_object(schema.get('properties', {}))
    pattern_properties = _schema_object(schema.get('patternProperties', {}))
    keys: list[object] = []
    for key in instance:
        if key in properties:
            continue
        if isinstance(key, str) and any(re.search(str(pattern), key) for pattern in pattern_properties):
            continue
        keys.append(key)
    return keys


def _schema_object(value: object) -> Mapping[str, object]:
    """A schema value the meta-schema proved is a JSON object.

    Such a value is a subschema a keyword fired in, or the value of a keyword the meta-schema requires to be an
    object, such as `properties`. `jsonschema` types both loosely, so this is the one place the module turns one
    into a `Mapping`: the proof is `FrontmatterSchema`'s construction, which `ty` cannot see.

    Args:
        value: A value read from a schema a `FrontmatterSchema` holds, or from an error validating against one.
    """
    if not isinstance(value, Mapping):
        raise AssertionError('unreachable: the meta-schema proved this schema value is an object')
    return value


def _schemas_within(schema: Mapping[str, object]) -> Iterator[Mapping[str, object]]:
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
            yield from _schemas_within(subschema)


@dataclass(frozen=True, slots=True)
class StructureSpec:
    """One structure specification's rules, proved usable.

    Construction checks the rules, so an instance is proof of them: no code holding a `StructureSpec`
    checks them again.

    Not hashable when it states a frontmatter schema, since `FrontmatterSchema` holds a dict.

    Attributes:
        file: The JSON file, `<name>.structure.json`, at its parsed specification filename; the prose it is the
            machine-checkable half of is `<name>.md` beside it, which `authority` names.
        title: The title rule, or None when the specification states none.
        forbid_empty_sections: True when every section must hold content.
        outline: The section order, matched against a document's sections left to right; may be empty.
        forbidden: Sections that must not appear at all.
        tokens: The token budget: the most tokens the whole file may hold, frontmatter, code and tables
            included, or None for no budget; at least 1.
        frontmatter: The JSON Schema a document's frontmatter must satisfy, or None when the specification states
            none.
    """

    file: StructureSpecFile
    title: TitleRule | None
    forbid_empty_sections: bool
    outline: tuple[OutlineEntry, ...]
    forbidden: tuple[str, ...]
    # The token budget and the outline's word caps stay plain ints rather than value objects: construction checks
    # their one invariant, at least 1, and the budget check calls a document's count `token_count`, so it cannot
    # be mistaken for this budget.
    tokens: int | None
    frontmatter: FrontmatterSchema | None

    def __post_init__(self) -> None:
        """Refuse rules that are not usable.

        A rule is not usable when it checks nothing, when no count, cap or budget satisfies it, or when it
        contradicts itself.

        A frontmatter schema is checked when it is built, before the structure specification is.

        Raises:
            EmptyStructureSpecError: If the specification states no rule.
            InvalidTitleCountError: If its title count is below 1.
            InvalidTokenBudgetError: If its token budget is below 1.
            InvalidWordCapError: If a word cap in its outline is below 1.
            RepeatedOutlineSectionError: If its outline names a section twice.
            ForbiddenOutlineSectionError: If it forbids a section its own outline names.
            AdjacentAnyRunsError: If its outline places two `any` runs side by side.
        """
        states_no_rule = (
            self.title is None
            and not self.forbid_empty_sections
            and self.tokens is None
            and self.frontmatter is None
            and not self.outline
            and not self.forbidden
        )
        if states_no_rule:
            raise EmptyStructureSpecError(self.path)
        if self.title is not None and self.title.count < 1:
            raise InvalidTitleCountError(self.path, self.title.count)
        if self.tokens is not None and self.tokens < 1:
            raise InvalidTokenBudgetError(self.path, self.tokens)
        for entry in self.outline:
            if entry.words is not None and entry.words < 1:
                raise InvalidWordCapError(self.path, entry, entry.words)

        named = self.section_names()
        repeated = sorted({name for name in named if named.count(name) > 1})
        if repeated:
            raise RepeatedOutlineSectionError(self.path, tuple(repeated))

        contradicted = sorted(set(named) & set(self.forbidden))
        if contradicted:
            raise ForbiddenOutlineSectionError(self.path, tuple(contradicted))

        for earlier, later in pairwise(self.outline):
            # Two runs side by side match exactly what one run matches, so an outline written this way means
            # something other than what it says.
            if isinstance(earlier, AnySections) and isinstance(later, AnySections):
                raise AdjacentAnyRunsError(self.path)

    @property
    def path(self) -> RootRelativePath:
        """Root-relative path of the JSON file, `<name>.structure.json`."""
        return self.file.path

    @property
    def authority(self) -> str:
        """The filename of the prose this file is the machine-checkable half of, such as `code.md`.

        Every finding quotes it, so a reader is sent to the rule rather than to the JSON.
        """
        return spec_filename(self.file.name, SpecFileType.PROSE)

    def section_names(self) -> list[str]:
        """The names of the outline's section entries, in outline order."""
        names: list[str] = []
        for entry in self.outline:
            match entry:
                case SectionEntry():
                    names.append(entry.name)
                case AnySections():
                    pass  # a run names no section
                case _:
                    assert_never(entry)
        return names

    @classmethod
    def parse(cls, file: StructureSpecFile, schema: StructureSchema) -> Self:
        """Deserialize a structure specification's text into its rules.

        Args:
            file: The structure specification file the text was read from; every rejection names its path.
            schema: The file's text.

        Raises:
            StructureSpecDecodeError: If the text is not JSON or does not have the dialect's shape.
            InvalidFrontmatterSchemaError: If its frontmatter schema is rejected by the meta-schema.
            FrontmatterSchemaIdError: If a schema in its frontmatter schema carries ``$id``.
            ForeignFrontmatterDialectError: If a schema in its frontmatter schema names another dialect.
            UntypedFrontmatterSchemaError: If its frontmatter schema's root does not state an object.
            EmptyStructureSpecError: If it states no rule.
            InvalidTitleCountError: If its title count is below 1.
            InvalidTokenBudgetError: If its token budget is below 1.
            InvalidWordCapError: If a word cap in its outline is below 1.
            RepeatedOutlineSectionError: If its outline names a section twice.
            ForbiddenOutlineSectionError: If it forbids a section its own outline names.
            AdjacentAnyRunsError: If its outline places two ``any`` runs side by side.
        """
        try:
            structure_file = StructureFile.model_validate_json(schema)
        except ValidationError as exc:
            raise StructureSpecDecodeError(file.path, _problems(exc), source=exc) from exc

        outline: list[OutlineEntry] = []
        for entry in structure_file.outline:
            match entry:
                case StructureFileAny():
                    outline.append(AnySections(words=entry.words))
                case StructureFileSection():
                    outline.append(
                        SectionEntry(
                            name=entry.section,
                            optional=entry.optional,
                            words=entry.words,
                            description=entry.description,
                            examples=entry.examples or (),
                        )
                    )
                case _:
                    assert_never(entry)

        return cls(
            file=file,
            title=_title_rule(structure_file.title),
            forbid_empty_sections=structure_file.empty_sections == 'forbidden',
            outline=tuple(outline),
            forbidden=structure_file.forbidden,
            tokens=structure_file.tokens,
            frontmatter=_frontmatter_schema(file.path, structure_file.frontmatter),
        )


def _title_rule(title: StructureFileTitle | None) -> TitleRule | None:
    """The title rule a file's `title` field states, or None when the file states none.

    Args:
        title: The file's `title` field, as read; `None` when the file leaves it out.
    """
    if title is None:
        return None
    return TitleRule(count=title.count, first=title.first)


def _frontmatter_schema(path: RootRelativePath, schema: dict[str, JsonValue] | None) -> FrontmatterSchema | None:
    """The frontmatter schema a file's `frontmatter` key states, or None when the file states none.

    Args:
        path: Root-relative path of the structure file, carried into the schema and any error it raises.
        schema: The file's `frontmatter` JSON Schema, as read; `None` when the file leaves it out.

    Raises:
        InvalidFrontmatterSchemaError: If the schema is rejected by the meta-schema.
        FrontmatterSchemaIdError: If a schema in it carries ``$id``.
        ForeignFrontmatterDialectError: If a schema in it names another dialect.
        UntypedFrontmatterSchemaError: If its root does not state an object.
    """
    if schema is None:
        return None
    return FrontmatterSchema(path=path, schema=schema)


def _describe_entry(entry: OutlineEntry) -> str:
    """How an outline entry is named in a rejection: its section name, or `any` for a run.

    Args:
        entry: The outline entry being named.
    """
    match entry:
        case SectionEntry():
            return f'section {entry.name!r}'
        case AnySections():
            return 'an `any` run'
        case _:
            assert_never(entry)


def _problems(error: ValidationError) -> tuple[str, ...]:
    """Every problem pydantic found in one file, each as `<field path>: <message>`.

    Args:
        error: The validation error raised for one structure file; a problem with no location is the bare message.
    """
    problems: list[str] = []
    for detail in error.errors(include_url=False):
        location = '.'.join(str(part) for part in detail['loc'])
        if location:
            problems.append(f'{location}: {detail["msg"]}')
        else:
            problems.append(detail['msg'])
    return tuple(problems)
