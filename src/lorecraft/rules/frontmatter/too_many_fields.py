"""`FM013`: a frontmatter holds more fields than its schema allows."""

from dataclasses import dataclass, field
from typing import ClassVar, Self, assert_never

from lorecraft.core.path import RootRelativePath
from lorecraft.project.context import FrontmatterContext
from lorecraft.project.schemas import (
    BlockProblem,
    FieldCount,
    FieldLimit,
    InvalidValueProblem,
    MaxFields,
    MissingFieldProblem,
    SchemaSource,
    UnknownFieldProblem,
    WrongTypeProblem,
)
from lorecraft.rules.collector import rule
from lorecraft.rules.identity import Level, Release, RuleCode, RuleName
from lorecraft.rules.location import Help, Here, Label, Subdiagnostic
from lorecraft.rules.subject import FrontmatterRule

from .__ruleset__ import GROUP_ID, schema_note, schema_spec


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class TooManyFields(FrontmatterRule):
    """A frontmatter holds more fields than its schema allows.

    ## What it does

    Checks for documents whose frontmatter holds more fields than their structure specification's `frontmatter`
    schema allows with `maxProperties`. It is reported on line 1, since it concerns no one field. The message says
    how many fields the block holds against the most the schema allows, and the help is the description the schema
    states for the block, when it states one.

    ## Why is this bad?

    The schema caps the block so that every document gives an agent the same few facts, and a block past the cap
    carries fields the schema did not plan for.

    ## Example

    `docs/__meta__/guide.spec.json`:

    ```json
    {
      "frontmatter": {
        "type": "object",
        "maxProperties": 1
      }
    }
    ```

    `docs/guide/setup.md`:

    ```markdown
    ---
    name: setup
    description: Install the toolkit and run it once over the repository.
    ---

    # Setup
    ```

    ## Use instead

    Keep the fields the schema allows:

    ```markdown
    ---
    name: setup
    ---

    # Setup
    ```

    Attributes:
        spec: The specification file that states the schema, derived from `source`, so no caller states one that
            disagrees with it; `None` for the Agent Skills specification.
        source: The schema that found the problem: a structure specification's, or the Agent Skills specification's.
        limit: The most fields the schema allows.
        field_count: The number of fields the frontmatter holds.
        description: What the schema says the block describes, as it wrote it, or `None` when it states none.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 13)
    NAME: ClassVar[RuleName] = RuleName('too-many-fields')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('0.3.0')

    # The specification file is derived from `source`, so no caller can state one that disagrees with it.
    spec: RootRelativePath | None = field(init=False)
    source: SchemaSource
    limit: FieldLimit
    field_count: FieldCount
    description: str | None = None

    def __post_init__(self) -> None:
        """Derive the specification file from the schema that found the problem."""
        # The dataclass is frozen, so the field a rule derives is set the one way a frozen dataclass allows.
        object.__setattr__(self, 'spec', schema_spec(self.source))

    def message(self) -> str:
        """State the number of fields the block holds against the most the schema allows."""
        return f'too many fields ({self.field_count} > {self.limit})'

    def labels(self) -> tuple[Label, ...]:
        """Say how many fields the block holds past the limit, on line 1."""
        return (Label(Here(self.line), f'fields over the limit: {self.field_count.value - self.limit.value}'),)

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Say where the schema is stated, then what it describes, when it says."""
        parts: list[Subdiagnostic] = [schema_note(self.source)]
        if self.description is not None:
            parts.append(Help(self.description))
        return tuple(parts)

    @classmethod
    def check(cls, subject: FrontmatterContext) -> tuple[Self, ...]:
        """One occurrence for each schema that finds more fields than it allows, in the order found.

        Args:
            subject: The document or the skill whose frontmatter each governing schema is applied to.
        """
        occurrences: list[Self] = []
        for schema in subject.schema_problems():
            for located in schema.problems:
                problem = located.problem
                match problem:
                    case BlockProblem(constraint=MaxFields() as constraint):
                        occurrences.append(
                            cls(
                                source=schema.source,
                                line=located.line,
                                limit=constraint.limit,
                                field_count=problem.field_count,
                                description=problem.description,
                            )
                        )
                    case BlockProblem():
                        pass  # `invalid-frontmatter`'s condition
                    case MissingFieldProblem() | UnknownFieldProblem() | WrongTypeProblem() | InvalidValueProblem():
                        pass  # another rule's condition
                    case _:
                        assert_never(problem)
        return tuple(occurrences)
