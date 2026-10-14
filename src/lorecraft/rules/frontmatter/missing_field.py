"""`FM006`: a frontmatter lacks a field its schema requires."""

from dataclasses import dataclass, field
from typing import ClassVar, Self, assert_never

from lorecraft.core.path import RootRelativePath
from lorecraft.project.context import FrontmatterContext
from lorecraft.project.schemas import (
    BlockProblem,
    InvalidValueProblem,
    MissingFieldProblem,
    SchemaSource,
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

    `docs/__meta__/guide.spec.json`:

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
        spec: The specification file that states the schema, derived from `source`, so no caller states one that
            disagrees with it; `None` for the Agent Skills specification.
        source: The schema that found the problem: a structure specification's, or the Agent Skills specification's.
        problem: The field the schema requires and the frontmatter lacks, with what the schema states about it.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 6)
    NAME: ClassVar[RuleName] = RuleName('missing-field')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('0.3.0')

    # The specification file is derived from `source`, so no caller can state one that disagrees with it.
    spec: RootRelativePath | None = field(init=False)
    source: SchemaSource
    problem: MissingFieldProblem

    def __post_init__(self) -> None:
        """Derive the specification file from the schema that found the problem."""
        # The dataclass is frozen, so the field a rule derives is set the one way a frozen dataclass allows.
        object.__setattr__(self, 'spec', schema_spec(self.source))

    def message(self) -> str:
        """Name the required field the frontmatter lacks."""
        return f'missing required field `{self.problem.field}`'

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Say where the schema is stated and name the field to add, then what the schema states about it."""
        guidance = self.problem.guidance
        parts: list[Subdiagnostic] = [
            schema_note(self.source),
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
                        occurrences.append(cls(source=schema.source, line=located.line, problem=problem))
                    case UnknownFieldProblem() | WrongTypeProblem() | InvalidValueProblem() | BlockProblem():
                        pass  # another rule's condition
                    case _:
                        assert_never(problem)
        return tuple(occurrences)
