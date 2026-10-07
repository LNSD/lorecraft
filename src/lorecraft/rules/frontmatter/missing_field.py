"""`FM006`: a frontmatter lacks a field its schema requires."""

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
from lorecraft.rules.location import Help, Subdiagnostic
from lorecraft.rules.subject import FrontmatterRule

from .__ruleset__ import GROUP_ID, allowed_values_help, example_note, schema_note, schema_spec


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class MissingField(FrontmatterRule):
    """A frontmatter lacks a field its schema requires.

    ## What it does

    Checks for documents whose frontmatter lacks a field the `required` list of their structure specification's
    `frontmatter` schema names, and for skills whose frontmatter lacks a field the Agent Skills specification
    requires, `name` or `description`. A document that several specifications govern, such as a corpus and a
    namespace, is held to each schema they state, and is reported once for each schema that requires the field.

    What the schema states about the field is shown as the help to write it: its `description`, the values its
    `enum` or `const` allows, and as a note its first `examples` entry. A `required` that sits in a branch, such as
    a `then`, leaves the field's `properties` to the schema around it, so nothing is shown for it.

    ## Why is this bad?

    An agent chooses which document or skill to load from its frontmatter alone, so a field left out is a fact the
    agent never sees and cannot choose by.

    ## Example

    `docs/__meta__/guide.structure.json`:

    ```json
    {
      "frontmatter": {
        "type": "object",
        "required": ["name", "description"]
      }
    }
    ```

    `docs/guide/setup.md`:

    ```markdown
    ---
    name: setup
    ---

    # Setup
    ```

    ## Use instead

    Write the field the schema requires:

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
        problem: The field the schema requires and the frontmatter lacks, with what the schema states about it.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 6)
    NAME: ClassVar[RuleName] = RuleName('missing-field')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('0.3.0')

    problem: MissingFieldProblem

    def message(self) -> str:
        """Name the required field the frontmatter lacks."""
        return f'missing required field `{self.problem.field}`'

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Say where the schema is stated and name the field to add, then what the schema states about it."""
        guidance = self.problem.guidance
        parts: list[Subdiagnostic] = [
            schema_note(self.spec),
            Help(f'add `{self.problem.field}` to the frontmatter'),
        ]
        if guidance.description is not None:
            parts.append(Help(guidance.description))
        if guidance.allowed:
            parts.append(allowed_values_help(guidance.allowed))
        if guidance.example is not None:
            parts.append(example_note(self.problem.field, guidance.example))
        return tuple(parts)

    @classmethod
    def check(cls, subject: FrontmatterContext) -> tuple[Self, ...]:
        """One occurrence for each required field a schema found missing, schema by schema, in the order found.

        Args:
            subject: The document or the skill whose frontmatter each governing schema is applied to.
        """
        occurrences: list[Self] = []
        for schema in subject.schema_problems():
            for located in schema.problems:
                problem = located.problem
                match problem:
                    case MissingFieldProblem():
                        occurrences.append(cls(spec=schema_spec(schema.source), line=located.line, problem=problem))
                    case UnknownFieldProblem() | WrongTypeProblem() | InvalidValueProblem() | BlockProblem():
                        pass  # another rule's condition
                    case _:
                        assert_never(problem)
        return tuple(occurrences)
