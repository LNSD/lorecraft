"""`FM008`: a frontmatter field's value is of a type its schema does not accept."""

from dataclasses import dataclass
from typing import ClassVar, Final, Self, assert_never

from lorecraft.project.context import FrontmatterContext
from lorecraft.project.schemas import (
    BlockProblem,
    InvalidValueProblem,
    JsonType,
    MissingFieldProblem,
    UnknownFieldProblem,
    WrongTypeProblem,
)
from lorecraft.rules.declaration import Level, Release, RuleCode, RuleName, rule
from lorecraft.rules.location import Help, Here, Label, Subdiagnostic
from lorecraft.rules.subject import FrontmatterRule

from .__ruleset__ import GROUP_ID, schema_note, schema_spec

_SCALARS_YAML_READS_UNQUOTED: Final[tuple[JsonType, ...]] = (JsonType.INTEGER, JsonType.NUMBER, JsonType.BOOLEAN)
"""The types YAML reads an unquoted `1`, `1.0` or `yes` as, where a string was meant."""


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

    The label says the types expected and the type found. A number or a boolean written where a string is
    expected is the usual YAML pitfall, as in `version: 1.0`, so the help says to quote it; the field's
    `description`, when the schema states one, is shown as help too.

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
        problem: The field whose value is of the wrong type, with the types the schema expects and the type found.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 8)
    NAME: ClassVar[RuleName] = RuleName('wrong-type')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('0.3.0')

    problem: WrongTypeProblem

    def message(self) -> str:
        """Name the field whose value is of the wrong type."""
        return f'field `{self.problem.field}` has a type the schema does not accept'

    def labels(self) -> tuple[Label, ...]:
        """Say the types the schema expects and the type found, on the field's line."""
        expected = ' or '.join(expected.value for expected in self.problem.expected)
        return (Label(Here(self.line), f'expected {expected}, found {self.problem.found.value}'),)

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Say where the schema is stated, how to write a string YAML read as another type, and what the field is."""
        problem = self.problem
        parts: list[Subdiagnostic] = [schema_note(self.spec)]
        if JsonType.STRING in problem.expected and problem.found in _SCALARS_YAML_READS_UNQUOTED:
            parts.append(Help('quote the value, so YAML reads it as a string'))
        if problem.guidance.description is not None:
            parts.append(Help(problem.guidance.description))
        return tuple(parts)

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
