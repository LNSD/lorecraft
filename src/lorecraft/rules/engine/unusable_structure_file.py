"""`LC004`: a structure file is well formed and states rules that cannot be applied."""

from dataclasses import dataclass
from typing import ClassVar, assert_never

from lorecraft.jsonschema import DIALECT
from lorecraft.project.schemas import SectionName
from lorecraft.project.schemas.structure_failure import ContradictorySkillField as ContradictorySkillFieldFailure
from lorecraft.rules.collector import rule
from lorecraft.rules.declaration import FileCondition
from lorecraft.rules.identity import EngineCode, Release, RuleName, Severity
from lorecraft.rules.location import Help, Note, Subdiagnostic, WholeSubject


@dataclass(frozen=True, slots=True)
class RepeatedOutlineSection:
    """The outline names a section more than once.

    Attributes:
        sections: The section names the outline repeats, sorted.
    """

    sections: tuple[SectionName, ...]


@dataclass(frozen=True, slots=True)
class RepeatedForbiddenSection:
    """The `forbidden` list names a section more than once.

    Attributes:
        sections: The section names the file forbids more than once, sorted.
    """

    sections: tuple[SectionName, ...]


@dataclass(frozen=True, slots=True)
class ForbiddenOutlineSection:
    """The `forbidden` list names a section the outline names too.

    Attributes:
        sections: The section names both in the outline and forbidden, sorted.
    """

    sections: tuple[SectionName, ...]


@dataclass(frozen=True, slots=True)
class AdjacentAnyRuns:
    """The outline holds two `any` entries next to each other."""


@dataclass(frozen=True, slots=True)
class InvalidTitlePattern:
    """The title pattern does not compile as a regular expression.

    Attributes:
        pattern: The pattern, exactly as written.
        problem: What the regular expression compiler rejected.
    """

    pattern: str
    problem: str


@dataclass(frozen=True, slots=True)
class InvalidFrontmatterSchema:
    """The frontmatter schema is not a valid JSON Schema.

    Attributes:
        problem: What the JSON Schema meta-schema rejected.
    """

    problem: str


@dataclass(frozen=True, slots=True)
class IdentifiedFrontmatterSchema:
    """The frontmatter schema, or a schema inside it, carries `$id`."""


@dataclass(frozen=True, slots=True)
class ForeignFrontmatterDialect:
    """The frontmatter schema, or a schema inside it, names a JSON Schema dialect other than 2020-12.

    Attributes:
        dialect: What `$schema` holds, as Python spells the value.
    """

    dialect: str


@dataclass(frozen=True, slots=True)
class UntypedFrontmatterSchema:
    """The frontmatter schema does not state `"type": "object"` at its root."""


@dataclass(frozen=True, slots=True)
class UnresolvableFrontmatterSchemaRefKeyword:
    """The frontmatter schema, or a schema inside it, holds a `$ref` that does not resolve inside it.

    Attributes:
        ref: What `$ref` holds, as Python spells the value.
    """

    ref: str


@dataclass(frozen=True, slots=True)
class CyclicFrontmatterSchemaRefKeyword:
    """A `$ref` in the frontmatter schema leads back to its own schema with no keyword in between.

    Attributes:
        ref: What the `$ref` that closes the cycle holds, as Python spells the value.
    """

    ref: str


type Cause = (
    RepeatedOutlineSection
    | RepeatedForbiddenSection
    | ForbiddenOutlineSection
    | AdjacentAnyRuns
    | InvalidTitlePattern
    | InvalidFrontmatterSchema
    | IdentifiedFrontmatterSchema
    | ForeignFrontmatterDialect
    | UnresolvableFrontmatterSchemaRefKeyword
    | CyclicFrontmatterSchemaRefKeyword
    | UntypedFrontmatterSchema
    | ContradictorySkillFieldFailure
)
"""Why the structure file cannot be applied."""


def _join(sections: tuple[SectionName, ...]) -> str:
    """The section names, comma-separated, for a note.

    Args:
        sections: The names to list, in the order given.
    """
    return ', '.join(str(name) for name in sections)


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class UnusableStructureFile(FileCondition):
    """A structure file follows the structure format and states rules that cannot be applied.

    ## What it does

    Checks for structure files that follow the structure format and still cannot be used, because a rule they state
    contradicts another, repeats itself, or cannot be applied: an outline or a forbidden list that names a section
    twice, a forbidden section the outline names, two `any` runs side by side, a title pattern that does not compile,
    or a frontmatter schema that is invalid, carries `$id`, names another dialect, holds a `$ref` that does not
    resolve inside it or that leads back to itself with no keyword in between, or states no object type. Such a file
    is reported once, at the file, and every document its spec governs is listed as skipped in coverage, with no
    rule run over it: a document that was not checked is never reported as clean. Every document the file does not
    govern is checked as if the file were fixed.

    The message says which case it is, and the note under it names what is wrong: the sections, the pattern or the
    problem the JSON Schema meta-schema found. Each case is explained below, with its fix.

    It has no level, so no configuration turns it off, and it is always reported as an error.

    ## Why is this bad?

    Until the file is fixed, the documents it governs are not checked, so a violation in them goes unreported and an
    agent loads them unreviewed.

    ## A section named twice in the outline

    `docs/__meta__/guide.spec.json`, naming `Overview` twice:

    ```json
    {
      "outline": [
        {"section": "Overview"},
        {"section": "Details"},
        {"section": "Overview"}
      ]
    }
    ```

    A document could never hold to it. Name each section once:

    ```json
    {
      "outline": [
        {"section": "Overview"},
        {"section": "Details"}
      ]
    }
    ```

    ## A section forbidden twice

    `docs/__meta__/guide.spec.json`, forbidding `Draft` twice:

    ```json
    {
      "forbidden": ["Draft", "Notes", "Draft"]
    }
    ```

    Forbid each section once:

    ```json
    {
      "forbidden": ["Draft", "Notes"]
    }
    ```

    ## A section both in the outline and forbidden

    `docs/__meta__/guide.spec.json`, requiring and forbidding `Overview`, so no document could hold to both:

    ```json
    {
      "outline": [{"section": "Overview"}],
      "forbidden": ["Overview"]
    }
    ```

    Keep each section in the outline or in the forbidden list, not both:

    ```json
    {
      "outline": [{"section": "Overview"}],
      "forbidden": ["Draft"]
    }
    ```

    ## Two `any` runs side by side

    `docs/__meta__/guide.spec.json`, with two runs in a row. Two runs side by side match exactly what one run
    matches, so the outline would mean something other than what it says:

    ```json
    {
      "outline": [
        {"any": true},
        {"any": true, "words": 200}
      ]
    }
    ```

    State one run, with the cap the two together were meant to carry:

    ```json
    {
      "outline": [
        {"any": true, "words": 200}
      ]
    }
    ```

    ## A title pattern that is not a regular expression

    `docs/__meta__/guide.spec.json`, with an unclosed bracket in `title.pattern`:

    ```json
    {
      "title": {"pattern": "[A-Z"}
    }
    ```

    Write a pattern that compiles:

    ```json
    {
      "title": {"pattern": "^[A-Z]"}
    }
    ```

    ## A frontmatter schema that is not a valid JSON Schema

    `docs/__meta__/guide.spec.json`, with `required` holding a string where a list is due. The `frontmatter` key
    must be a valid JSON Schema of the 2020-12 dialect:

    ```json
    {
      "frontmatter": {"type": "object", "required": "name"}
    }
    ```

    Write the keyword as the dialect defines it:

    ```json
    {
      "frontmatter": {"type": "object", "required": ["name"]}
    }
    ```

    ## A frontmatter schema that carries `$id`

    `docs/__meta__/guide.spec.json`, with an `$id`, in the schema or in one inside it, which would make it a
    schema resource of its own that nothing can reach:

    ```json
    {
      "frontmatter": {
        "$id": "https://example.com/guide",
        "type": "object"
      }
    }
    ```

    Leave `$id` out:

    ```json
    {
      "frontmatter": {"type": "object"}
    }
    ```

    ## A frontmatter schema in another dialect

    `docs/__meta__/guide.spec.json`, written in draft-07. A frontmatter schema, or a schema inside it, that sets
    `$schema` to anything but the 2020-12 dialect is refused, since that is the only one it is written in:

    ```json
    {
      "frontmatter": {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object"
      }
    }
    ```

    Name the 2020-12 dialect, or leave `$schema` out:

    ```json
    {
      "frontmatter": {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object"
      }
    }
    ```

    ## A frontmatter schema with a `$ref` that does not resolve

    `docs/__meta__/guide.spec.json`, with a `$ref` to a definition the schema does not hold. A `$ref` must point
    at a location inside the schema: a reference to another file or URL is never fetched:

    ```json
    {
      "frontmatter": {
        "type": "object",
        "properties": {"name": {"$ref": "#/$defs/name"}}
      }
    }
    ```

    Define what the reference names:

    ```json
    {
      "frontmatter": {
        "type": "object",
        "properties": {"name": {"$ref": "#/$defs/name"}},
        "$defs": {"name": {"type": "string"}}
      }
    }
    ```

    ## A frontmatter schema with a `$ref` cycle

    `docs/__meta__/guide.spec.json`, with a `$ref` that leads back to the schema it sits in without any keyword that
    reads the document in between. Applying such a schema would recurse without end, so it is refused whether or not
    anything refers to it, an unreferenced `$defs` entry included:

    ```json
    {
      "frontmatter": {
        "type": "object",
        "$ref": "#"
      }
    }
    ```

    State a keyword before the schema refers back. A `$ref` below `properties` or `items` is fine, since it applies
    to a smaller value:

    ```json
    {
      "frontmatter": {
        "type": "object",
        "properties": {"parent": {"$ref": "#"}}
      }
    }
    ```

    ## A frontmatter schema that states no object type

    `docs/__meta__/guide.spec.json`, with a root that states properties but no type. A document's frontmatter is
    always a mapping, so a schema that does not say so would accept values no document can hold:

    ```json
    {
      "frontmatter": {
        "properties": {"name": {"type": "string"}}
      }
    }
    ```

    State the type at the root:

    ```json
    {
      "frontmatter": {
        "type": "object",
        "properties": {"name": {"type": "string"}}
      }
    }
    ```

    Attributes:
        cause: Which rule of the file cannot be applied, with what was found.
    """

    CODE: ClassVar[EngineCode] = EngineCode(4)
    NAME: ClassVar[RuleName] = RuleName('unusable-structure-file')
    SINCE: ClassVar[Release] = Release('0.3.0')
    SEVERITY: ClassVar[Severity] = Severity.ERROR

    cause: Cause

    def message(self) -> str:
        """Name the case."""
        match self.cause:
            case RepeatedOutlineSection():
                return 'outline names a section more than once'
            case RepeatedForbiddenSection():
                return 'a section is forbidden more than once'
            case ForbiddenOutlineSection():
                return 'outline names a section the file also forbids'
            case AdjacentAnyRuns():
                return 'outline places two any runs side by side'
            case InvalidTitlePattern():
                return 'title pattern is not a valid regular expression'
            case InvalidFrontmatterSchema():
                return 'frontmatter schema is not a valid JSON Schema'
            case IdentifiedFrontmatterSchema():
                return 'frontmatter schema carries $id'
            case ForeignFrontmatterDialect():
                return 'frontmatter schema names another JSON Schema dialect'
            case UnresolvableFrontmatterSchemaRefKeyword():
                return 'frontmatter schema holds a $ref that does not resolve inside it'
            case CyclicFrontmatterSchemaRefKeyword():
                return 'frontmatter schema holds a $ref that leads back to itself with no keyword in between'
            case UntypedFrontmatterSchema():
                return 'frontmatter schema does not state "type": "object" at its root'
            case ContradictorySkillFieldFailure():
                return 'skills schema contradicts a built-in Agent Skills rule'
            case _:
                assert_never(self.cause)

    def primary(self) -> WholeSubject:
        """The structure file as a whole: no line of it is at fault."""
        return WholeSubject()

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Say how to fix the case, then what was found in it."""
        match self.cause:
            case RepeatedOutlineSection(sections=sections):
                return (Help('name each section once'), Note(f'repeated: {_join(sections)}'))
            case RepeatedForbiddenSection(sections=sections):
                return (Help('forbid each section once'), Note(f'repeated: {_join(sections)}'))
            case ForbiddenOutlineSection(sections=sections):
                return (
                    Help('keep each section in the outline or in the forbidden list, not both'),
                    Note(f'named and forbidden: {_join(sections)}'),
                )
            case AdjacentAnyRuns():
                return (Help('state one any run in their place'),)
            case InvalidTitlePattern(pattern=pattern, problem=problem):
                return (Note(f'pattern {pattern!r}: {problem}'),)
            case InvalidFrontmatterSchema(problem=problem):
                return (Note(problem),)
            case IdentifiedFrontmatterSchema():
                return (Help('remove $id from every schema in the frontmatter schema'),)
            case ForeignFrontmatterDialect(dialect=dialect):
                return (
                    Help(f'name {DIALECT}, or leave $schema out'),
                    Note(f'$schema holds {dialect}'),
                )
            case UnresolvableFrontmatterSchemaRefKeyword(ref=ref):
                return (
                    Help('point every $ref at a location inside the frontmatter schema, such as #/$defs/name'),
                    Note(f'$ref holds {ref}'),
                )
            case CyclicFrontmatterSchemaRefKeyword(ref=ref):
                return (
                    Help('point the $ref at a schema that states a keyword before it refers back'),
                    Note(f'$ref holds {ref}'),
                )
            case UntypedFrontmatterSchema():
                return (Help('add "type": "object" to the root of the frontmatter schema'),)
            case ContradictorySkillFieldFailure(contradictions=contradictions):
                return tuple(Note(f'{item.field}: contradicts built-in rule: {item.rule}') for item in contradictions)
            case _:
                assert_never(self.cause)
