"""The structure aspect: a structure specification file's decoded JSON, and the rules it is decoded into.

The repository reads a ``<stem>.structure.json`` file's text, a ``StructureSchema``, which proves nothing about
it. ``StructureAspect.parse`` is the check, in two steps at the edge. It deserializes the text straight into the
strict, frozen ``StructureFile`` model, so JSON that is malformed or not the dialect's shape is refused before
any rule is read. Then it maps the model to typed rules, and building the aspect refuses a set of rules that
checks nothing or contradicts itself, which no shape can state. So every ``StructureAspect`` that exists states
usable rules, however it was built.

A document's outline is a sequence whose length varies, and JSON Schema cannot state an order over one, so a
structure specification is not JSON Schema. It is this small dialect, whose fields ``structure_file`` declares:

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
        {"section": "Checklist", "words": 250}
      ],
      "forbidden": ["Changelog"]
    }

The file does not name the prose it is the machine-checkable half of: that is ``<stem>.md`` beside it, and every
finding quotes it.

- ``$schema`` points editors at ``docs/schemas/structure.spec.json``, the JSON Schema ``just gen`` renders from
  ``structure_file``; it is not kept. That schema states the shape only: the rules ``StructureAspect`` refuses
  below it cannot state.
- ``description`` is read by people only, and is not kept.
- ``title`` states how many H1 titles a document carries, and whether one opens it ahead of every section.
- ``empty_sections``, whose one value is ``"forbidden"``, reports a section left without content.
- ``tokens`` is the token budget: the most tokens the whole file may hold, frontmatter, code and tables
  included, since that is what loading it costs an agent. The count is ``o200k_base``, the same whichever agent
  reads it. The budget check applies it, not the structure check: it reads the raw file, not the parse tree.
- ``frontmatter`` is a Draft 2020-12 JSON Schema the document's frontmatter must satisfy. Unlike the rest of the
  file it is JSON Schema, not the dialect: a frontmatter is a mapping, which JSON Schema states well. Its root must
  say ``"type": "object"`` outright, and no schema in it, at any depth, may carry ``$id`` or name another dialect
  in ``$schema``. The
  frontmatter check applies it, not the structure check: it reads the frontmatter, not the headings.
- ``outline`` is the order of the document's sections. A ``section`` entry names one and is required unless
  ``optional``; an ``any`` entry matches a run of sections the outline does not name. An entry's ``words`` caps
  the prose words of each section it matches, H3 subsections included: on an ``any`` entry that is every section
  in the run alone, not the run's total. An entry without ``words`` caps nothing. A word is a whitespace-delimited
  token of prose; fenced code and table rows are not counted.
- ``forbidden`` names sections that must not appear at all.

Nothing here logs: the command that loads the model catches every ``Error`` that escapes it and reports it.
"""

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from itertools import pairwise
from typing import NewType, Self

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from pydantic import JsonValue, ValidationError
from referencing.jsonschema import DRAFT202012

from lorecraft.core.error import Error
from lorecraft.core.path import RootRelativePath

from .spec_file import (
    DottedSpecStemError,
    InvalidSpecStemError,
    NotASpecFileError,
    NotASpecStemError,
    UnknownSpecAspectError,
    parse_spec_file,
    prose_filename,
)
from .structure_file import JSON_SCHEMA_DIALECT, StructureFile, StructureFileAny, StructureFileTitle

# The text of a structure specification file as read, not yet known to be JSON, the dialect's shape or usable
# rules. A NewType only keeps it apart from other text; `StructureAspect.parse` is what proves it.
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


class StructureSpecFilenameError(Error):
    """A structure specification file does not sit at a specification filename.

    Attributes:
        path: Root-relative path of the rejected file.
        source: Why the filename is not a specification filename.
    """

    path: RootRelativePath
    source: NotASpecFileError | UnknownSpecAspectError | NotASpecStemError | DottedSpecStemError | InvalidSpecStemError

    def __init__(
        self,
        path: RootRelativePath,
        *,
        source: NotASpecFileError
        | UnknownSpecAspectError
        | NotASpecStemError
        | DottedSpecStemError
        | InvalidSpecStemError,
    ) -> None:
        self.path = path
        self.source = source
        super().__init__(f'invalid structure schema {path}: is not at a specification filename')
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
        count: The number of H1 titles; at least 1, which ``StructureAspect`` checks.
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
            no cap; at least 1, which ``StructureAspect`` checks.
    """

    name: str
    optional: bool = False
    # Checked by the enclosing `StructureAspect` rather than here, so a bad cap is refused as an
    # `InvalidWordCapError` naming the specification file, which this record does not know.
    words: int | None = None


@dataclass(frozen=True, slots=True)
class AnySections:
    """An outline entry matching a run, of any length, of sections the outline does not name.

    The run stops at any section the outline names, which pins that name to its own entry wherever it turns up.

    Attributes:
        words: The most prose words each section in the run may hold, its H3 subsections included, or None, the
            default, for no cap. It caps every section alone, not the run's total; at least 1, which
            ``StructureAspect`` checks.
    """

    # Checked by the enclosing `StructureAspect` rather than here, so a bad cap is refused as an
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

    Frozen for equality only: ``schema`` is a dict, so instances are not hashable and must not be put in a set or
    used as a key.

    Attributes:
        path: Root-relative path of the structure specification the schema is written in, quoted verbatim in
            every violation it yields.
        schema: The decoded schema. Values are ``object`` because a JSON Schema is recursive and JSON decodes each
            value to its own Python type.
    """

    path: RootRelativePath
    schema: dict[str, object]

    def __post_init__(self) -> None:
        """Refuse a schema that is not a well-formed Draft 2020-12 schema, that leaves it for another resource or
        dialect anywhere inside it, or that does not describe an object.

        Raises:
            InvalidFrontmatterSchemaError: If the schema is rejected by the Draft 2020-12 meta-schema.
            FrontmatterSchemaIdError: If any schema in it carries ``$id``.
            ForeignFrontmatterDialectError: If any schema in it names a dialect other than Draft 2020-12 in
                ``$schema``.
            UntypedFrontmatterSchemaError: If its root does not say ``"type": "object"``.
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


def _schemas_within(schema: Mapping[str, object]) -> Iterator[Mapping[str, object]]:
    """The schema itself, then every object subschema inside it, at any depth.

    Only the places Draft 2020-12 reads a schema from are walked, such as ``properties`` or ``items``, so a value
    under ``enum`` or ``const`` that happens to hold ``$id`` is data, not a schema, and is not visited. A boolean
    subschema holds no keyword, so it is skipped.
    """
    yield schema
    for subschema in DRAFT202012.subresources_of(schema):
        if isinstance(subschema, Mapping):
            yield from _schemas_within(subschema)


@dataclass(frozen=True, slots=True)
class StructureAspect:
    """One structure specification's rules, proved usable.

    Construction checks the rules, so an instance is proof of them: no code holding a ``StructureAspect``
    checks them again.

    Not hashable when it states a frontmatter schema, since ``FrontmatterSchema`` holds a dict.

    Attributes:
        path: Root-relative path of the JSON file, ``<stem>.structure.json``; the prose it is the
            machine-checkable half of is ``<stem>.md`` beside it, which ``authority`` names.
        title: The title rule, or None when the specification states none.
        forbid_empty_sections: True when every section must hold content.
        outline: The section order, matched against a document's sections left to right; may be empty.
        forbidden: Sections that must not appear at all.
        tokens: The token budget: the most tokens the whole file may hold, frontmatter, code and tables
            included, or None for no budget; at least 1.
        frontmatter: The JSON Schema a document's frontmatter must satisfy, or None when the specification states
            none.
        authority: The filename of the prose this file is the machine-checkable half of, such as ``code.md``,
            derived from ``path`` at construction. Every finding quotes it, so a reader is sent to the rule rather
            than to the JSON.
    """

    path: RootRelativePath
    title: TitleRule | None
    forbid_empty_sections: bool
    outline: tuple[OutlineEntry, ...]
    forbidden: tuple[str, ...]
    # The token budget and the outline's word caps stay plain ints rather than value objects: construction checks
    # their one invariant, at least 1, and the budget check calls a document's count `token_count`, so it cannot
    # be mistaken for this budget.
    tokens: int | None
    frontmatter: FrontmatterSchema | None
    authority: str = field(init=False)

    def __post_init__(self) -> None:
        """Derive the authority from the path, then refuse rules that check nothing, that no count, cap or budget
        satisfies, or that contradict themselves.

        A frontmatter schema is checked when it is built, before the aspect is.

        Raises:
            StructureSpecFilenameError: If the path is not a specification filename.
            EmptyStructureSpecError: If the aspect states no rule.
            InvalidTitleCountError: If its title count is below 1.
            InvalidTokenBudgetError: If its token budget is below 1.
            InvalidWordCapError: If a word cap in its outline is below 1.
            RepeatedOutlineSectionError: If its outline names a section twice.
            ForbiddenOutlineSectionError: If it forbids a section its own outline names.
            AdjacentAnyRunsError: If its outline places two ``any`` runs side by side.
        """
        try:
            spec_file = parse_spec_file(self.path)
        except (
            NotASpecFileError,
            UnknownSpecAspectError,
            NotASpecStemError,
            DottedSpecStemError,
            InvalidSpecStemError,
        ) as exc:
            raise StructureSpecFilenameError(self.path, source=exc) from exc
        # `authority` is derived from `path` rather than passed in, so the two cannot disagree. A frozen dataclass
        # refuses plain assignment, and `object.__setattr__` is the one way to set a field during construction.
        object.__setattr__(self, 'authority', prose_filename(spec_file.name))

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

    def section_names(self) -> list[str]:
        """The names of the outline's section entries, in outline order."""
        names: list[str] = []
        for entry in self.outline:
            if isinstance(entry, SectionEntry):
                names.append(entry.name)
        return names

    @classmethod
    def parse(cls, path: RootRelativePath, schema: StructureSchema) -> Self:
        """Deserialize a structure specification's text into its rules.

        Args:
            path: Where the text was read from; every rejection names it.
            schema: The file's text.

        Raises:
            StructureSpecDecodeError: If the text is not JSON or does not have the dialect's shape.
            InvalidFrontmatterSchemaError: If its frontmatter schema is rejected by the meta-schema.
            FrontmatterSchemaIdError: If a schema in its frontmatter schema carries ``$id``.
            ForeignFrontmatterDialectError: If a schema in its frontmatter schema names another dialect.
            UntypedFrontmatterSchemaError: If its frontmatter schema's root does not state an object.
            StructureSpecFilenameError: If the path is not a specification filename.
            EmptyStructureSpecError: If it states no rule.
            InvalidTitleCountError: If its title count is below 1.
            InvalidTokenBudgetError: If its token budget is below 1.
            InvalidWordCapError: If a word cap in its outline is below 1.
            RepeatedOutlineSectionError: If its outline names a section twice.
            ForbiddenOutlineSectionError: If it forbids a section its own outline names.
            AdjacentAnyRunsError: If its outline places two ``any`` runs side by side.
        """
        try:
            file = StructureFile.model_validate_json(schema)
        except ValidationError as exc:
            raise StructureSpecDecodeError(path, _problems(exc), source=exc) from exc

        outline: list[OutlineEntry] = []
        for entry in file.outline:
            if isinstance(entry, StructureFileAny):
                outline.append(AnySections(words=entry.words))
            else:
                outline.append(SectionEntry(name=entry.section, optional=entry.optional, words=entry.words))

        return cls(
            path=path,
            title=_title_rule(file.title),
            forbid_empty_sections=file.empty_sections == 'forbidden',
            outline=tuple(outline),
            forbidden=file.forbidden,
            tokens=file.tokens,
            frontmatter=_frontmatter_schema(path, file.frontmatter),
        )


def _title_rule(title: StructureFileTitle | None) -> TitleRule | None:
    """The title rule a file's ``title`` field states, or None when the file states none."""
    if title is None:
        return None
    return TitleRule(count=title.count, first=title.first)


def _frontmatter_schema(path: RootRelativePath, schema: dict[str, JsonValue] | None) -> FrontmatterSchema | None:
    """The frontmatter schema a file's ``frontmatter`` key states, or None when the file states none.

    Raises:
        InvalidFrontmatterSchemaError: If the schema is rejected by the meta-schema.
        FrontmatterSchemaIdError: If a schema in it carries ``$id``.
        ForeignFrontmatterDialectError: If a schema in it names another dialect.
        UntypedFrontmatterSchemaError: If its root does not state an object.
    """
    if schema is None:
        return None
    # The copy only widens the value type from `JsonValue` to `object`, which `dict` would otherwise keep invariant.
    widened: dict[str, object] = dict(schema)
    return FrontmatterSchema(path=path, schema=widened)


def _describe_entry(entry: OutlineEntry) -> str:
    """How an outline entry is named in a rejection: its section name, or ``any`` for a run."""
    if isinstance(entry, SectionEntry):
        return f'section {entry.name!r}'
    return 'an `any` run'


def _problems(error: ValidationError) -> tuple[str, ...]:
    """Every problem pydantic found in one file, each as ``<field path>: <message>``."""
    problems: list[str] = []
    for detail in error.errors(include_url=False):
        location = '.'.join(str(part) for part in detail['loc'])
        if location:
            problems.append(f'{location}: {detail["msg"]}')
        else:
            problems.append(detail['msg'])
    return tuple(problems)
