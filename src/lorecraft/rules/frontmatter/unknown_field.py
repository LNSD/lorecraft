"""`FM007`: a frontmatter holds a field its schema does not define."""

from dataclasses import dataclass
from typing import ClassVar, Self, assert_never

from lorecraft.project.schemas import (
    BlockProblem,
    InvalidValueProblem,
    MissingFieldProblem,
    UnknownFieldProblem,
    WrongTypeProblem,
)
from lorecraft.rules.declaration import Level, Release, RuleCode, RuleName, rule
from lorecraft.rules.inputs import SchemaProblemsInput, SchemaProblemsRule
from lorecraft.rules.location import Help, Subdiagnostic

from .__ruleset__ import GROUP_ID, schema_note, schema_spec


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class UnknownField(SchemaProblemsRule):
    """A frontmatter holds a field its schema does not define.

    ## What it does

    Checks for documents whose frontmatter holds a field their structure specification's `frontmatter` schema
    neither names in `properties` nor matches in `patternProperties`, when the schema sets `additionalProperties`
    to `false`; and for skills whose frontmatter holds a field the Agent Skills specification does not define. A
    document that several specifications govern is reported once for each schema that does not define the field.

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
        problem: The field the schema does not define.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 7)
    NAME: ClassVar[RuleName] = RuleName('unknown-field')
    LEVEL: ClassVar[Level] = Level.WARN
    SINCE: ClassVar[Release] = Release('0.3.0')

    problem: UnknownFieldProblem

    def message(self) -> str:
        """Name the field the schema does not define."""
        return f'unknown field `{self.problem.field}`'

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Say where the schema is stated, and name the field to remove or respell."""
        return (
            schema_note(self.spec),
            Help(f'remove `{self.problem.field}`, or respell it as a field the schema defines'),
        )

    @classmethod
    def check(cls, subject: SchemaProblemsInput) -> tuple[Self, ...]:
        """One occurrence for each field a schema does not define, schema by schema, in the order found.

        Args:
            subject: The problems each governing schema found.
        """
        occurrences: list[Self] = []
        for schema in subject.schemas:
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
