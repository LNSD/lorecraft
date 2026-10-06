"""`FM009`: a frontmatter field's value breaks a constraint its schema sets."""

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
class InvalidValue(FrontmatterRule):
    """A frontmatter field's value breaks a constraint its schema sets.

    ## What it does

    Checks for documents whose frontmatter gives a field a value that breaks a constraint of its property in their
    structure specification's `frontmatter` schema other than its type, such as `maxLength`, `pattern` or `enum`,
    and for skills whose frontmatter breaks such a constraint of the Agent Skills specification, such as a `name`
    longer than 64 characters or not in lowercase. Anything wrong inside a field's value, such as a key a mapping
    lacks or an item of the wrong type, is that field's value at fault, and is reported here on the field's line.

    ## Why is this bad?

    The schema states the constraint so that every document's field reads the same way to an agent; a value
    outside it, such as a description too long to list or a name a tool cannot match, breaks that.

    ## Example

    `docs/__meta__/guide.structure.json`:

    ```json
    {
      "frontmatter": {
        "type": "object",
        "properties": {"name": {"type": "string", "pattern": "^[a-z-]+$"}}
      }
    }
    ```

    `docs/guide/setup.md`:

    ```markdown
    ---
    name: Setup Guide
    ---

    # Setup
    ```

    ## Use instead

    Write a value within the constraint:

    ```markdown
    ---
    name: setup-guide
    ---

    # Setup
    ```

    Attributes:
        spec: The structure specification whose frontmatter schema found the problem, or `None` for a skill, which
            the Agent Skills specification governs.
        problem: The field whose value breaks the constraint.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 9)
    NAME: ClassVar[RuleName] = RuleName('invalid-value')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('0.3.0')

    problem: InvalidValueProblem

    def message(self) -> str:
        """Name the field whose value breaks a constraint; the constraint is in the schema's wording, a note."""
        return f'field `{self.problem.field}` breaks a constraint of the schema'

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Give the schema's own wording, which names the constraint, and say where the schema is stated."""
        return (Note(self.problem.message), schema_note(self.spec))

    @classmethod
    def check(cls, subject: FrontmatterContext) -> tuple[Self, ...]:
        """One occurrence for each value a schema found breaking a constraint, schema by schema, in the order found.

        Args:
            subject: The document or the skill whose frontmatter each governing schema is applied to.
        """
        occurrences: list[Self] = []
        for schema in subject.schema_problems():
            for located in schema.problems:
                problem = located.problem
                match problem:
                    case InvalidValueProblem():
                        occurrences.append(cls(spec=schema_spec(schema.source), line=located.line, problem=problem))
                    case MissingFieldProblem() | UnknownFieldProblem() | WrongTypeProblem() | BlockProblem():
                        pass  # another rule's condition
                    case _:
                        assert_never(problem)
        return tuple(occurrences)
