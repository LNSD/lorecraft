"""`FM007`: a frontmatter holds a field its schema does not define."""

from dataclasses import dataclass
from typing import ClassVar, Self, assert_never

from lorecraft.project.context import FrontmatterContext
from lorecraft.project.schemas import (
    BlockProblem,
    InvalidValueProblem,
    MissingFieldProblem,
    UnknownFieldProblem,
    WrongTypeProblem,
)
from lorecraft.rules.declaration import Level, Release, RuleCode, RuleName, rule
from lorecraft.rules.location import Help, Here, Label, Note, Subdiagnostic
from lorecraft.rules.subject import FrontmatterRule

from .__ruleset__ import GROUP_ID, schema_note, schema_spec


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class UnknownField(FrontmatterRule):
    """A frontmatter holds a field its schema does not define.

    ## What it does

    Checks for documents whose frontmatter holds a field their structure specification's `frontmatter` schema
    neither names in `properties` nor matches in `patternProperties`, when the schema sets `additionalProperties`
    to `false`, or that no keyword of the schema evaluates, when it sets `unevaluatedProperties` to `false`; and
    for skills whose frontmatter holds a field the Agent Skills specification does not define. A document that
    several specifications govern is reported once for each schema that does not define the field.

    The fields the schema defines are listed as a note: the `properties` of the schema that holds the keyword, or
    the fields of the Agent Skills specification. A schema that composes others with `allOf` or `$ref` may
    evaluate fields its own `properties` leave out, so for such a schema the list can be shorter than what it
    accepts, and it is left out when the schema names none.

    ## Why is this bad?

    An agent reads every field of the frontmatter, so a field no schema defines costs it tokens and offers a fact
    no other document states the same way, often a misspelling of a field the schema does define.

    ## Example

    `docs/__meta__/guide.structure.json`:

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
        spec: The structure specification whose frontmatter schema found the problem, or `None` for a skill, which
            the Agent Skills specification governs.
        problem: The field the schema does not define, with the fields it does.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 7)
    NAME: ClassVar[RuleName] = RuleName('unknown-field')
    LEVEL: ClassVar[Level] = Level.WARN
    SINCE: ClassVar[Release] = Release('0.3.0')

    problem: UnknownFieldProblem

    def message(self) -> str:
        """Name the field the schema does not define."""
        return f'unknown field `{self.problem.field}`'

    def labels(self) -> tuple[Label, ...]:
        """Say the schema does not define the field, on the field's line."""
        return (Label(Here(self.line), 'not defined by the schema'),)

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Say where the schema is stated and name the field to remove or respell, then the fields it defines."""
        parts: list[Subdiagnostic] = [
            schema_note(self.spec),
            Help(f'remove `{self.problem.field}`, or respell it as a field the schema defines'),
        ]
        known_fields = self.problem.known_fields
        if known_fields:
            fields = ', '.join(f'`{field}`' for field in known_fields)
            parts.append(Note(f'the schema defines: {fields}'))
        return tuple(parts)

    @classmethod
    def check(cls, subject: FrontmatterContext) -> tuple[Self, ...]:
        """One occurrence for each field a schema does not define, schema by schema, in the order found.

        Args:
            subject: The document or the skill whose frontmatter each governing schema is applied to.
        """
        occurrences: list[Self] = []
        for schema in subject.schema_problems():
            for located in schema.problems:
                problem = located.problem
                match problem:
                    case UnknownFieldProblem():
                        occurrences.append(cls(spec=schema_spec(schema.source), line=located.line, problem=problem))
                    case MissingFieldProblem() | WrongTypeProblem() | InvalidValueProblem() | BlockProblem():
                        pass  # another rule's condition
                    case _:
                        assert_never(problem)
        return tuple(occurrences)
