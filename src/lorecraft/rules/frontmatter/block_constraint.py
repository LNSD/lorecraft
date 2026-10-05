"""`FM010`: a frontmatter breaks a constraint its schema sets on the whole block."""

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
from lorecraft.rules.location import Note, Subdiagnostic

from .__ruleset__ import GROUP_ID, schema_note, schema_spec


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class BlockConstraint(SchemaProblemsRule):
    """A frontmatter breaks a constraint its schema sets on the whole block.

    ## What it does

    Checks for documents whose frontmatter breaks a constraint their structure specification's `frontmatter`
    schema sets on the block rather than on one field, such as `minProperties`, `maxProperties` or a
    `dependentRequired` pair. It is reported on line 1, since it concerns no one field. A skill's frontmatter is
    reported here only when the Agent Skills specification rejects it without naming a field.

    ## Why is this bad?

    The schema states what the block must hold as a whole so that every document gives an agent the same facts; a
    block outside it leaves the agent without some of them.

    ## Example

    `docs/__meta__/guide.structure.json`:

    ```json
    {
      "frontmatter": {
        "type": "object",
        "minProperties": 2
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

    Write the block the schema describes:

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
        problem: The constraint over the whole block that the frontmatter breaks.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 10)
    NAME: ClassVar[RuleName] = RuleName('block-constraint')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('0.3.0')

    problem: BlockProblem

    def message(self) -> str:
        """Say the block breaks a constraint on the whole of it; the schema's wording, a note, names the constraint."""
        return 'frontmatter breaks a constraint of the schema on the whole block'

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Give the schema's own wording, which names the constraint, and say where the schema is stated."""
        return (Note(self.problem.message), schema_note(self.spec))

    @classmethod
    def check(cls, subject: SchemaProblemsInput) -> tuple[Self, ...]:
        """One occurrence for each block constraint a schema found broken, schema by schema, in the order found.

        Args:
            subject: The problems each governing schema found.
        """
        occurrences: list[Self] = []
        for schema in subject.schemas:
            for located in schema.problems:
                problem = located.problem
                match problem:
                    case BlockProblem():
                        occurrences.append(cls(spec=schema_spec(schema.source), line=located.line, problem=problem))
                    case MissingFieldProblem() | UnknownFieldProblem() | WrongTypeProblem() | InvalidValueProblem():
                        pass  # another rule's condition
                    case _:
                        assert_never(problem)
        return tuple(occurrences)
