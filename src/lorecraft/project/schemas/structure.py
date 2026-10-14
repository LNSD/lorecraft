r"""The structure specification: its file's decoded JSON, and the rules it is decoded into.

The repository reads a `<name>.spec.json` file's text, a `StructureSchema`, which proves nothing about
it. `StructureSpec.parse` is the check, in two steps at the edge. It deserializes the text straight into the
strict, frozen `StructureFile` model, so JSON that is malformed or not the dialect's shape is refused before
any rule is read. Then it maps the model to typed rules, and refuses a set of rules that checks nothing or
contradicts itself, which no shape can state. So every `StructureSpec` that `parse` returns states usable rules.

A document's outline is a sequence whose length varies, and JSON Schema cannot state an order over one, so a
structure specification is not JSON Schema. It is this small dialect, whose fields `structure_file` declares:

    {
      "$schema": "../schemas/structure.spec.json",
      "description": "what this file governs, for whoever opens it",
      "title": {"words": 8, "chars": 60, "pattern": "^[A-Z]"},
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
- `title` holds the checks a document's H1 title is held to: `words` caps the title's own words, counted as a
  section's prose words are, `chars` caps its characters, counted as code points with inline markup stripped, and
  `pattern` is a regular expression the title's text must match, searched for anywhere in it as JSON Schema's
  `pattern` is. A pattern that does not compile is refused when the file loads. It
  states at least one check, since an empty `title` would check nothing.
- `empty_sections`, whose one value is `"forbidden"`, reports a section left without content.
- `tokens` is the token budget: the most tokens the whole file may hold, frontmatter, code and tables
  included, since that is what loading it costs an agent. The count is `o200k_base`, the same whichever agent
  reads it. The budget check applies it, not the structure check: it reads the raw file, not the parse tree.
- `frontmatter` is a Draft 2020-12 JSON Schema the document's frontmatter must satisfy. Unlike the rest of the
  file it is JSON Schema, not the dialect: a frontmatter is a mapping, which JSON Schema states well. Its root must
  say `"type": "object"` outright, and no schema in it, at any depth, may carry `$id` or name another dialect
  in `$schema`. The frontmatter check applies it, not the structure check: it reads the frontmatter, not the
  headings. `FrontmatterSchema.validate` translates `jsonschema`'s errors into `FrontmatterProblem` values
  in `frontmatter_schema`, because that is the one place the package reads a `jsonschema` error.
  `FrontmatterSchema` is its own concern and lives in this module only for now: it is built from the
  `frontmatter` field of `StructureFile`, so it stays beside that model until it moves to a module of its own.
- `outline` is the order of the document's sections. A `section` entry names one and is required unless
  `optional`; an `any` entry matches a run of sections the outline does not name. An entry's `words` caps
  the prose words of each section it matches, H3 subsections included: on an `any` entry that is every section
  in the run alone, not the run's total. An entry without `words` caps nothing. A word is a whitespace-delimited
  token of prose; fenced code and table rows are not counted. A `section` entry's `description` says what the
  section holds and its `examples` are Markdown samples of its body; when a document lacks the section, the
  structure check reports the description and the first example as notes, and leaves the rest to a reader.
- `forbidden` names sections that must not appear at all.

No key states that the title is there: a document a structure specification governs always carries exactly one H1
title, and it opens the document. `title` only adds checks on it.

A section name, in an outline entry or in `forbidden`, is a `SectionName`: one line of heading text with no
whitespace at either end, since a heading's text never has any.

Nothing here logs: the command that loads the model catches every `Error` that escapes it and reports it.
"""

import re
from dataclasses import dataclass
from itertools import pairwise
from typing import NewType, Self, assert_never

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from pydantic import ValidationError
from referencing import Registry
from referencing.jsonschema import DRAFT202012

from lorecraft.core.mapping import Frozen, FrozenMapping
from lorecraft.core.num import NonZeroUnsignedInt
from lorecraft.core.path import RootRelativePath
from lorecraft.project.syntax import SectionHeading

from .frontmatter_problem import (
    FrontmatterProblem,
)
from .frontmatter_schema import _frontmatter_problems, _iter_schemas_within, _resolves_inside
from .section_name import SectionName
from .spec_file import SpecFileType, StructureSpecFile, spec_filename
from .structure_failure import (
    AdjacentAnyRuns,
    EmptyStructureSpec,
    ForbiddenOutlineSections,
    ForeignFrontmatterDialect,
    FrontmatterSchemaId,
    InvalidFrontmatterSchema,
    InvalidTitlePattern,
    RepeatedForbiddenSections,
    RepeatedOutlineSections,
    StructureSpecFailure,
    StructureSpecProblem,
    StructureSpecRuleFailure,
    UndecodableStructureSpec,
    UnresolvableFrontmatterSchemaRef,
    UntypedFrontmatterSchema,
)
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


@dataclass(frozen=True, slots=True)
class TitlePattern:
    """A regular expression a document's title text must match, compiled when its specification loads.

    It is held compiled, so a pattern that does not compile cannot be held at all: `parse` refuses it with
    `InvalidTitlePattern`. It is Python's `re` syntax, matched as JSON Schema's
    `pattern` is: searched for anywhere in the text, so `Guide` matches `The Guide`, and a pattern that must hold
    the whole title anchors itself with `^` and `$`.

    Attributes:
        regex: The compiled pattern.
    """

    regex: re.Pattern[str]

    @classmethod
    def parse(cls, pattern: str) -> Self | InvalidTitlePattern:
        """Compile a title pattern as a structure specification writes it.

        Args:
            pattern: The pattern, exactly as written.

        Returns:
            The compiled pattern, or the failure naming the pattern and what the compiler rejected when it does not
            compile.
        """
        try:
            regex = re.compile(pattern)
        except re.error as exc:
            return InvalidTitlePattern(pattern, exc.msg)
        return cls(regex)

    def is_found_in(self, text: str) -> bool:
        """True when the pattern is found anywhere in `text`.

        Args:
            text: A title's text, without its `#` marker or inline markup.
        """
        return self.regex.search(text) is not None

    def __str__(self) -> str:
        """The pattern, exactly as written."""
        return self.regex.pattern


@dataclass(frozen=True, slots=True)
class PatternedTitleChecks:
    """Title checks that include a pattern, with or without either cap.

    Attributes:
        words: The most words the title's text may hold, or None for no cap.
        chars: The most characters the title's text may hold, or None for no cap.
        pattern: The pattern the title's text must match.
    """

    pattern: TitlePattern
    words: NonZeroUnsignedInt | None = None
    chars: NonZeroUnsignedInt | None = None


@dataclass(frozen=True, slots=True)
class WordCappedTitleChecks:
    """Title checks that include a word cap and no pattern, with or without a character cap.

    Attributes:
        words: The most words the title's text may hold.
        chars: The most characters the title's text may hold, or None for no cap.
        pattern: Always None: a title that states a pattern is a `PatternedTitleChecks`.
    """

    words: NonZeroUnsignedInt
    chars: NonZeroUnsignedInt | None = None
    pattern: None = None


@dataclass(frozen=True, slots=True)
class CharCappedTitleChecks:
    """Title checks that state a character cap and nothing else.

    Attributes:
        words: Always None: a title that states a word cap is a `WordCappedTitleChecks` or a `PatternedTitleChecks`.
        chars: The most characters the title's text may hold.
        pattern: Always None: a title that states a pattern is a `PatternedTitleChecks`.
    """

    chars: NonZeroUnsignedInt
    words: None = None
    pattern: None = None


# The checks a structure specification holds a document's H1 title to, beyond its being there. Each check is optional
# and independent of the others, but at least one is set: every case that sets one is a record of its own, so a
# `title` that states no check cannot be built. Every record carries `words`, `chars` and `pattern`, so a reader
# asks each of them without telling the records apart.
type TitleChecks = PatternedTitleChecks | WordCappedTitleChecks | CharCappedTitleChecks


@dataclass(frozen=True, slots=True)
class SectionEntry:
    """An outline entry naming one section, and fixing its position against every other name in the outline.

    Attributes:
        name: The name the entry gives the section.
        optional: True when a document may leave the section out; False, the default, when it must carry it.
        words: The most prose words the section may hold, its H3 subsections included, or None, the default, for
            no cap.
        description: What the section holds, reported as help when a document lacks the section, or None, the
            default, for no help.
        examples: Markdown samples of the section's body, each without its heading, or empty, the default, for
            none. The first is reported as a note when a document lacks the section; the rest are for a reader of
            the specification.
    """

    name: SectionName
    optional: bool = False
    words: NonZeroUnsignedInt | None = None
    description: str | None = None
    examples: tuple[str, ...] = ()

    def names(self, heading: SectionHeading) -> bool:
        """Whether the heading is the section this entry names.

        Args:
            heading: The heading of an H2 section of the document.
        """
        return self.name.names(heading)


@dataclass(frozen=True, slots=True)
class AnySections:
    """An outline entry matching a run, of any length, of sections the outline does not name.

    The run stops at any section the outline names, which pins that name to its own entry wherever it turns up.

    Attributes:
        words: The most prose words each section in the run may hold, its H3 subsections included, or None, the
            default, for no cap. It caps every section alone, not the run's total.
    """

    words: NonZeroUnsignedInt | None = None


type OutlineEntry = SectionEntry | AnySections
"""One entry of a structure specification's outline."""


type FrontmatterSchemaFailure = (
    InvalidFrontmatterSchema
    | FrontmatterSchemaId
    | ForeignFrontmatterDialect
    | UnresolvableFrontmatterSchemaRef
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
        dialect anywhere inside it, whose every `$ref` resolves inside it, and that describes an object.

        Args:
            schema: The file's `frontmatter` JSON Schema, as read.

        Returns:
            The checked schema, or the failure naming what is wrong with it: the meta-schema's rejection, an `$id`, a
            dialect other than Draft 2020-12 in `$schema`, a `$ref` that does not resolve inside the schema, or a
            root that does not say `"type": "object"`.
        """
        # `jsonschema` takes a JSON object only as a `dict` and an array only as a `list`, so every schema and
        # frontmatter it reads is handed to it as plain data, copied from the frozen value.
        plain = schema.to_plain()
        try:
            Draft202012Validator.check_schema(plain)
        except SchemaError as exc:
            return InvalidFrontmatterSchema(exc.message)
        # No `$id` is allowed below, so the whole schema is one resource, and every `$ref` is read against it.
        registry = Registry().with_resource('', DRAFT202012.create_resource(plain))
        for subschema in _iter_schemas_within(schema):
            if '$id' in subschema:
                # An `$id` would make that schema a resource of its own, with its own base URI, and so change what
                # every relative `$ref` beneath it resolves to.
                return FrontmatterSchemaId()
            dialect = subschema.get('$schema', JSON_SCHEMA_DIALECT)
            # The meta-schema check above has refused a `$schema` that is not a string.
            assert isinstance(dialect, str), 'unreachable: the meta-schema proved `$schema` is a string'
            if dialect != JSON_SCHEMA_DIALECT:
                # The check applies every schema under Draft 2020-12, so a schema written for another dialect would
                # be read by rules it was not written for.
                return ForeignFrontmatterDialect(dialect)
            for keyword in ('$ref', '$dynamicRef'):
                ref = subschema.get(keyword)
                if ref is None:
                    continue
                # The meta-schema check above has refused a reference that is not a string.
                if not isinstance(ref, str):
                    raise AssertionError(f'unreachable: the meta-schema proved `{keyword}` is a string')
                if not _resolves_inside(registry, ref):
                    # `validate` raises nothing, and `jsonschema` raises when it meets a reference that does not
                    # resolve to a schema, so it is refused here, where the schema is loaded.
                    return UnresolvableFrontmatterSchemaRef(ref)
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
        # Plain data, as `__post_init__` hands `jsonschema` the schema: it reads only a `dict` as a JSON object.
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


@dataclass(frozen=True, slots=True)
class StructureSpec:
    """One structure specification's rules, proved usable.

    `parse` is the one way in for rules not yet known to be usable: it checks them and returns the failure it finds
    instead of an instance, so an instance it returns is proof of them and no code holding a `StructureSpec` checks
    them again. Calling `StructureSpec(...)` directly is unchecked, and is only for a specification already checked.

    Attributes:
        file: The JSON file, `<name>.spec.json`, at its parsed specification filename; the prose it is the
            machine-checkable half of is `<name>.md` beside it, which `authority` names.
        title: The checks the document's title is held to, or None when the specification states none.
        forbid_empty_sections: True when every section must hold content.
        outline: The section order, matched against a document's sections left to right; may be empty.
        forbidden: Sections that must not appear at all, each named once.
        tokens: The token budget: the most tokens the whole file may hold, frontmatter, code and tables
            included, or None for no budget.
        frontmatter: The JSON Schema a document's frontmatter must satisfy, or None when the specification states
            none.
    """

    file: StructureSpecFile
    title: TitleChecks | None
    forbid_empty_sections: bool
    outline: tuple[OutlineEntry, ...]
    forbidden: tuple[SectionName, ...]
    tokens: NonZeroUnsignedInt | None
    frontmatter: FrontmatterSchema | None

    @property
    def path(self) -> RootRelativePath:
        """Root-relative path of the JSON file, `<name>.spec.json`."""
        return self.file.path

    @property
    def authority(self) -> str:
        """The filename of the prose this file is the machine-checkable half of, such as `code.md`.

        Every finding quotes it, so a reader is sent to the rule rather than to the JSON.
        """
        return spec_filename(self.file.name, SpecFileType.PROSE)

    def section_names(self) -> list[SectionName]:
        """The names of the outline's section entries, in outline order."""
        names: list[SectionName] = []
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
    def parse(cls, file: StructureSpecFile, schema: StructureSchema) -> Self | StructureSpecFailure:
        """Deserialize a structure specification's text into its rules.

        Args:
            file: The structure specification file the text was read from; every rejection names its path.
            schema: The file's text.

        Returns:
            The rules, or the failure naming why the text cannot be used: it is not JSON or not the dialect's shape,
            a title `pattern` does not compile, the frontmatter schema cannot be held, or the rules are not usable.
        """
        try:
            structure_file = StructureFile.model_validate_json(schema)
        except ValidationError as exc:
            return UndecodableStructureSpec(_problems(exc))

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

        title = _title_checks(structure_file.title)
        if isinstance(title, InvalidTitlePattern):
            return title
        frontmatter = _frontmatter_schema(structure_file.frontmatter)
        if frontmatter is not None and not isinstance(frontmatter, FrontmatterSchema):
            return frontmatter

        spec = cls(
            file=file,
            title=title,
            forbid_empty_sections=structure_file.empty_sections == 'forbidden',
            outline=tuple(outline),
            forbidden=structure_file.forbidden,
            tokens=structure_file.tokens,
            frontmatter=frontmatter,
        )
        rule_failure = _rule_failure(spec)
        if rule_failure is not None:
            return rule_failure
        return spec


def _rule_failure(spec: StructureSpec) -> StructureSpecRuleFailure | None:
    """The way a specification's rules are not usable, or None when they are.

    A rule is not usable when it checks nothing, or when it contradicts itself.

    A frontmatter schema is checked when it is parsed, before the structure specification is, and so is a
    cap or a budget: each is a `NonZeroUnsignedInt`, at least 1. So is a section name: each is a
    `SectionName`, one line with no whitespace at either end.

    Args:
        spec: The specification whose rules are checked.
    """
    # The title is held to one H1 opening the document whatever the specification states. A `title` always holds
    # a check (every `TitleChecks` record sets one), so a `title` alone states a rule.
    states_no_rule = (
        spec.title is None
        and not spec.forbid_empty_sections
        and spec.tokens is None
        and spec.frontmatter is None
        and not spec.outline
        and not spec.forbidden
    )
    if states_no_rule:
        return EmptyStructureSpec()

    named = spec.section_names()
    repeated = sorted({name for name in named if named.count(name) > 1}, key=str)
    if repeated:
        return RepeatedOutlineSections(tuple(repeated))

    repeated_forbidden = sorted({name for name in spec.forbidden if spec.forbidden.count(name) > 1}, key=str)
    if repeated_forbidden:
        return RepeatedForbiddenSections(tuple(repeated_forbidden))

    contradicted = sorted(set(named) & set(spec.forbidden), key=str)
    if contradicted:
        return ForbiddenOutlineSections(tuple(contradicted))

    for earlier, later in pairwise(spec.outline):
        # Two runs side by side match exactly what one run matches, so an outline written this way means
        # something other than what it says.
        if isinstance(earlier, AnySections) and isinstance(later, AnySections):
            return AdjacentAnyRuns()
    return None


def _title_checks(title: StructureFileTitle | None) -> TitleChecks | InvalidTitlePattern | None:
    """The checks a file's `title` key states on the title, or None when the file leaves the key out.

    Args:
        title: The file's `title` key, as read; `None` when the file leaves it out.

    Returns:
        The checks, None, or the failure naming a `pattern` that does not compile.
    """
    if title is None:
        return None
    if title.pattern is not None:
        pattern = TitlePattern.parse(title.pattern)
        if isinstance(pattern, InvalidTitlePattern):
            return pattern
        return PatternedTitleChecks(pattern=pattern, words=title.words, chars=title.chars)
    if title.words is not None:
        return WordCappedTitleChecks(words=title.words, chars=title.chars)
    if title.chars is not None:
        return CharCappedTitleChecks(chars=title.chars)
    raise AssertionError('unreachable: `StructureFileTitle` refuses a `title` that states no check')


def _frontmatter_schema(
    schema: FrozenMapping[str, Frozen] | None,
) -> FrontmatterSchema | FrontmatterSchemaFailure | None:
    """The frontmatter schema a file's `frontmatter` key states, or None when the file states none.

    Args:
        schema: The file's `frontmatter` JSON Schema, as read; `None` when the file leaves it out.

    Returns:
        The checked schema, None, or the failure naming what is wrong with the schema.
    """
    if schema is None:
        return None
    return FrontmatterSchema.parse(schema)


def _problems(error: ValidationError) -> tuple[StructureSpecProblem, ...]:
    """Every problem pydantic found in one file.

    Args:
        error: The validation error raised for one structure file.
    """
    return tuple(
        StructureSpecProblem(location=detail['loc'], message=detail['msg'])
        for detail in error.errors(include_url=False)
    )
