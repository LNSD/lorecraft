"""`FM008`: a frontmatter field's value is of a type its schema does not accept."""

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
from lorecraft.rules.location import Note, Subdiagnostic
from lorecraft.rules.subject import FrontmatterRule

from .__ruleset__ import GROUP_ID, schema_note, schema_spec


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class WrongType(FrontmatterRule):
    """A frontmatter field's value is of a type its schema does not accept.

    ## What it does

    Checks for documents whose frontmatter gives a field a value of a type other than the one the `type` keyword of
    its property states in their structure specification's `frontmatter` schema, and for skills whose frontmatter
    gives a field a value other than the string, or the mapping of strings to strings for `metadata`, the Agent
    Skills specification requires. A value of the right type that breaks another constraint, such as a length
    limit, is not this rule's.

    ## Why is this bad?

    An agent and every tool that reads the field expect the type the schema states, so a value of another type,
    such as a list where a string belongs, is misread or dropped.

    ## Example

    `docs/__meta__/guide.structure.json`:

    ```json
    {
      "frontmatter": {
        "type": "object",
        "properties": {"description": {"type": "string"}}
      }
    }
    ```

    `docs/guide/setup.md`:

    ```markdown
    ---
    description:
      - Install the toolkit.
      - Run it once over the repository.
    ---

    # Setup
    ```

    ## Use instead

    Write the value as the type the schema states:

    ```markdown
    ---
    description: Install the toolkit, then run it once over the repository.
    ---

    # Setup
    ```

    Attributes:
        spec: The structure specification whose frontmatter schema found the problem, or `None` for a skill, which
            the Agent Skills specification governs.
        problem: The field whose value is of the wrong type, with the schema's wording of the type it expects.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 8)
    NAME: ClassVar[RuleName] = RuleName('wrong-type')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('0.3.0')

    problem: WrongTypeProblem

    def message(self) -> str:
        """Name the field whose value is of the wrong type."""
        return f'field `{self.problem.field}` has a type the schema does not accept'

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Give the schema's wording of the type it expects, and say where the schema is stated."""
        return (Note(self.problem.message), schema_note(self.spec))

    @classmethod
    def check(cls, subject: FrontmatterContext) -> tuple[Self, ...]:
        """One occurrence for each value a schema found of the wrong type, schema by schema, in the order found.

        Args:
            subject: The document or the skill whose frontmatter each governing schema is applied to.
        """
        occurrences: list[Self] = []
        for schema in subject.schema_problems():
            for located in schema.problems:
                problem = located.problem
                match problem:
                    case WrongTypeProblem():
                        occurrences.append(cls(spec=schema_spec(schema.source), line=located.line, problem=problem))
                    case MissingFieldProblem() | UnknownFieldProblem() | InvalidValueProblem() | BlockProblem():
                        pass  # another rule's condition
                    case _:
                        assert_never(problem)
        return tuple(occurrences)
