"""`FM007`: a frontmatter holds a field its schema does not define."""

from dataclasses import dataclass, field
from typing import ClassVar, Self, assert_never

from lorecraft.core.path import RootRelativePath
from lorecraft.project.query import Query
from lorecraft.project.schemas import (
    BlockProblem,
    InvalidValueProblem,
    MissingFieldProblem,
    SchemaProblems,
    SchemaSource,
    UnknownFieldProblem,
    WrongTypeProblem,
)
from lorecraft.rules.collector import rule
from lorecraft.rules.identity import Level, Release, RuleCode, RuleName
from lorecraft.rules.location import Help, Here, Label, Note, Subdiagnostic
from lorecraft.rules.subject import QueriedFrontmatterRule

from .__ruleset__ import GROUP_ID, schema_note, schema_problems, schema_spec


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class UnknownField(QueriedFrontmatterRule[tuple[SchemaProblems, ...]]):
    """A frontmatter holds a field its schema does not define.

    ## What it does

    Checks for documents whose frontmatter holds a field their structure file's `frontmatter` schema
    neither names in `properties` nor matches in `patternProperties`, when the schema sets `additionalProperties`
    to `false`, or that no keyword of the schema evaluates, when it sets `unevaluatedProperties` to `false`; and
    for skills whose frontmatter holds a field the Agent Skills specification does not define. A document that
    several meta specs govern is reported once for each schema that does not define the field.

    The fields the schema defines are listed as a note: the `properties` of the schema that holds the keyword, or
    the fields of the Agent Skills specification. A schema that composes others with `allOf` or `$ref` may
    evaluate fields its own `properties` leave out, so for such a schema the list can be shorter than what it
    accepts, and it is left out when the schema names none.

    ## Why is this bad?

    An agent reads every field of the frontmatter, so a field no schema defines costs it tokens and offers a fact
    no other document states the same way, often a misspelling of a field the schema does define.

    ## Example

    `docs/__meta__/guide.spec.json`:

    ```json
    {
      "frontmatter": {
        "type": "object",
        "properties": {"name": {"type": "string"}, "description": {"type": "string"}},
        "additionalProperties": false
      }
    }
    ```

    `docs/guide/setup.md`:

    ```markdown
    ---
    name: setup
    desc: Install the toolkit and run it once over the repository.
    ---

    # Setup
    ```

    ## Use instead

    Spell the field as the schema defines it:

    ```markdown
    ---
    name: setup
    description: Install the toolkit and run it once over the repository.
    ---

    # Setup
    ```

    Attributes:
        spec: The structure file that states the schema, derived from `source`, so no caller states one that
            disagrees with it; `None` for the Agent Skills specification.
        source: The schema that found the problem: a structure file's, or the Agent Skills specification's.
        problem: The field the schema does not define, with the fields it does.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 7)
    NAME: ClassVar[RuleName] = RuleName('unknown-field')
    LEVEL: ClassVar[Level] = Level.WARN
    SINCE: ClassVar[Release] = Release('0.3.0')

    # The specification file is derived from `source`, so no caller can state one that disagrees with it.
    spec: RootRelativePath | None = field(init=False)
    source: SchemaSource
    problem: UnknownFieldProblem

    def __post_init__(self) -> None:
        """Derive the structure file from the schema that found the problem."""
        # The dataclass is frozen, so the field a rule derives is set the one way a frozen dataclass allows.
        object.__setattr__(self, 'spec', schema_spec(self.source))

    def message(self) -> str:
        """Name the field the schema does not define."""
        return f'unknown field `{self.problem.field}`'

    def labels(self) -> tuple[Label, ...]:
        """Say the schema does not define the field, on the field's line."""
        return (Label(Here(self.line), 'not defined by the schema'),)

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Say where the schema is stated and name the field to remove or respell, then the fields it defines."""
        parts: list[Subdiagnostic] = [
            schema_note(self.source),
            Help(f'remove `{self.problem.field}`, or respell it as a field the schema defines'),
        ]
        known_fields = self.problem.known_fields
        if known_fields:
            fields = ', '.join(f'`{field}`' for field in known_fields)
            parts.append(Note(f'the schema defines: {fields}'))
        return tuple(parts)

    @classmethod
    def query(cls) -> Query[tuple[SchemaProblems, ...]]:
        """What each schema that governs the subject rejects in its frontmatter."""
        return schema_problems

    @classmethod
    def judge(cls, facts: tuple[SchemaProblems, ...], /) -> tuple[Self, ...]:
        """One occurrence for each field a schema does not define, schema by schema, in the order found.

        Args:
            facts: What each governing schema rejects, in the order the schemas apply.
        """
        occurrences: list[Self] = []
        for schema in facts:
            for located in schema.problems:
                problem = located.problem
                match problem:
                    case UnknownFieldProblem():
                        occurrences.append(cls(source=schema.source, line=located.line, problem=problem))
                    case MissingFieldProblem() | WrongTypeProblem() | InvalidValueProblem() | BlockProblem():
                        pass  # another rule's condition
                    case _:
                        assert_never(problem)
        return tuple(occurrences)
