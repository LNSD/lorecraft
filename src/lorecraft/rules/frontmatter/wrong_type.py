"""`FM008`: a frontmatter field's value is of a type its schema does not accept."""

from dataclasses import dataclass, field
from typing import ClassVar, Final, Self, assert_never

from lorecraft.core.path import RootRelativePath
from lorecraft.project.context import FrontmatterContext
from lorecraft.project.schemas import (
    BlockProblem,
    InvalidValueProblem,
    JsonType,
    MissingFieldProblem,
    SchemaSource,
    UnknownFieldProblem,
    WrongTypeProblem,
)
from lorecraft.rules.collector import rule
from lorecraft.rules.declaration import Level, Release, RuleCode, RuleName
from lorecraft.rules.location import Help, Here, Label, Subdiagnostic
from lorecraft.rules.subject import FrontmatterRule

from .__ruleset__ import GROUP_ID, example_note, schema_note, schema_spec

_SCALARS_YAML_READS_UNQUOTED: Final[frozenset[JsonType]] = frozenset(
    {JsonType.INTEGER, JsonType.NUMBER, JsonType.BOOLEAN}
)
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
    `description`, when the schema states one, is shown as help too, and its `example` as a note.

    ## Why is this bad?

    An agent and every tool that reads the field expect the type the schema states, so a value of another type,
    such as a list where a string belongs, is misread or dropped.

    ## Example

    `docs/__meta__/guide.spec.json`:

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
        spec: The specification file that states the schema, derived from `source`, so no caller states one that
            disagrees with it; `None` for the Agent Skills specification.
        source: The schema that found the problem: a structure specification's, or the Agent Skills specification's.
        problem: The field whose value is of the wrong type, with the types the schema expects and the type found.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 8)
    NAME: ClassVar[RuleName] = RuleName('wrong-type')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('0.3.0')

    # The specification file is derived from `source`, so no caller can state one that disagrees with it.
    spec: RootRelativePath | None = field(init=False)
    source: SchemaSource
    problem: WrongTypeProblem

    def __post_init__(self) -> None:
        """Derive the specification file from the schema that found the problem."""
        # The dataclass is frozen, so the field a rule derives is set the one way a frozen dataclass allows.
        object.__setattr__(self, 'spec', schema_spec(self.source))

    def message(self) -> str:
        """Name the field whose value is of the wrong type."""
        return f'field `{self.problem.field}` has a type the schema does not accept'

    def labels(self) -> tuple[Label, ...]:
        """Say the types the schema expects and the type found, on the field's line."""
        expected = ' or '.join(expected.value for expected in self.problem.expected)
        return (Label(Here(self.line), f'expected {expected}, found {self.problem.found.value}'),)

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Say where the schema is stated, how to quote a string YAML misread, then what the field is and looks like."""
        problem = self.problem
        parts: list[Subdiagnostic] = [schema_note(self.source)]
        if JsonType.STRING in problem.expected and problem.found in _SCALARS_YAML_READS_UNQUOTED:
            parts.append(Help('quote the value, so YAML reads it as a string'))
        if problem.guidance.description is not None:
            parts.append(Help(problem.guidance.description))
        if problem.guidance.example is not None:
            parts.append(example_note(problem.field, problem.guidance.example))
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
                        occurrences.append(cls(source=schema.source, line=located.line, problem=problem))
                    case MissingFieldProblem() | UnknownFieldProblem() | InvalidValueProblem() | BlockProblem():
                        pass  # another rule's condition
                    case _:
                        assert_never(problem)
        return tuple(occurrences)
