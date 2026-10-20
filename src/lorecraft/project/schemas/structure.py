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
      "lines": 500,
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
- `lines` is the line budget: the most lines the whole file may hold, frontmatter, code and blank lines
  included. The count uses the project's CommonMark line endings.
- `frontmatter` is a Draft 2020-12 JSON Schema the document's frontmatter must satisfy. Unlike the rest of the
  file it is JSON Schema, not the dialect: a frontmatter is a mapping, which JSON Schema states well. Its root must
  say `"type": "object"` outright, and no schema in it, at any depth, may carry `$id` or name another dialect
  in `$schema`. The frontmatter check applies it, not the structure check: it reads the frontmatter, not the
  headings. `frontmatter_schema` holds the schema, its checks and the translation of JSON Schema violations.
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

from pydantic import ValidationError

from lorecraft.core.error import Unreachable
from lorecraft.core.mapping import Frozen, FrozenMapping
from lorecraft.core.num import NonZeroUnsignedInt
from lorecraft.core.path import RootRelativePath
from lorecraft.project.syntax import SectionHeading
from lorecraft.schemas import SchemaRef

from .frontmatter_schema import FrontmatterSchema, FrontmatterSchemaFailure
from .section_name import SectionName
from .spec_file import SpecFileType, StructureSpecFile, spec_filename
from .structure_failure import (
    AdjacentAnyRuns,
    EmptyStructureSpec,
    ForbiddenOutlineSections,
    InvalidTitlePattern,
    RepeatedForbiddenSections,
    RepeatedOutlineSections,
    StructureSpecFailure,
    StructureSpecProblem,
    StructureSpecRuleFailure,
    UndecodableStructureSpec,
)
from .structure_file import (
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

    def is_name_of(self, heading: SectionHeading) -> bool:
        """Whether the heading is the section this entry names.

        Args:
            heading: The heading of an H2 section of the document.
        """
        return self.name.is_name_of(heading)


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
        lines: The line budget for the whole file, frontmatter and blank lines included, or None for no budget.
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
    lines: NonZeroUnsignedInt | None = None
    frontmatter_schema_ref: SchemaRef | None = None

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
            lines=structure_file.lines,
            frontmatter=frontmatter,
        )
        rule_failure = _rule_failure(spec)
        if rule_failure is not None:
            return rule_failure
        return spec


def _section_names(outline: tuple[OutlineEntry, ...]) -> list[SectionName]:
    """The names of an outline's section entries, in outline order."""
    names: list[SectionName] = []
    for entry in outline:
        match entry:
            case SectionEntry():
                names.append(entry.name)
            case AnySections():
                pass  # a run names no section
            case _:
                assert_never(entry)
    return names


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
        and spec.lines is None
        and spec.frontmatter is None
        and not spec.outline
        and not spec.forbidden
    )
    if states_no_rule:
        return EmptyStructureSpec()

    named = _section_names(spec.outline)
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
    # SAFETY: `StructureFileTitle` refuses a `title` that states no check
    raise Unreachable('a `title` states a check')


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
