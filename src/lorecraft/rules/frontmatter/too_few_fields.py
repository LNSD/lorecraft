"""`FM014`: a frontmatter holds fewer fields than its schema requires."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import ClassVar, Self, assert_never

from lorecraft.core.path import RootRelativePath
from lorecraft.project.item import ItemKind
from lorecraft.project.query import ItemQuery
from lorecraft.project.schemas import (
    BlockProblem,
    FieldCount,
    FieldLimit,
    InvalidValueProblem,
    MinFields,
    MissingFieldProblem,
    SchemaProblems,
    SchemaSource,
    UnknownFieldProblem,
    WrongTypeProblem,
)
from lorecraft.rules.collector import rule
from lorecraft.rules.identity import Level, Release, RuleCode, RuleName
from lorecraft.rules.location import Help, Here, Label, Subdiagnostic
from lorecraft.rules.subject import ByMetaSpec, Gate, MetaSpecPart, QueriedItemRule

from .__ruleset__ import GROUP_ID, schema_note, schema_problems, schema_spec


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class TooFewFields(QueriedItemRule[tuple[SchemaProblems, ...]]):
    """A frontmatter holds fewer fields than its schema requires.

    ## What it does

    Checks for documents whose frontmatter holds fewer fields than their structure file's `frontmatter`
    schema requires with `minProperties`. It is reported on line 1, since it concerns no one field. The message says
    how many fields the block holds against the least the schema requires, and the help is the description the
    schema states for the block, when it states one.

    ## Why is this bad?

    The schema sets a floor on the block so that every document gives an agent the same few details, and a block under
    the floor leaves the agent without some of them.

    ## Example

    `docs/__meta__/guide.spec.json`:

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

    Write the fields the schema requires:

    ```markdown
    ---
    name: setup
    description: Install the toolkit and run it once over the repository.
    ---

    # Setup
    ```

    Attributes:
        spec: The structure file that states the schema, derived from `source`, so no caller states one that
            disagrees with it; `None` for the Agent Skills specification.
        source: The schema that found the problem: a structure file's, or the Agent Skills specification's.
        limit: The least fields the schema requires.
        field_count: The number of fields the frontmatter holds.
        description: What the schema says the block describes, as it wrote it, or `None` when it states none.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 14)
    NAME: ClassVar[RuleName] = RuleName('too-few-fields')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('0.3.0')
    GATES: ClassVar[Mapping[ItemKind, Gate]] = MappingProxyType(
        {
            ItemKind.DOCUMENT: ByMetaSpec(MetaSpecPart.FRONTMATTER),
            ItemKind.SKILL_ENTRY: ByMetaSpec(MetaSpecPart.FRONTMATTER),
        }
    )

    # The specification file is derived from `source`, so no caller can state one that disagrees with it.
    spec: RootRelativePath | None = field(init=False)
    source: SchemaSource
    limit: FieldLimit
    field_count: FieldCount
    description: str | None = None

    def __post_init__(self) -> None:
        """Derive the structure file from the schema that found the problem."""
        # The dataclass is frozen, so the field a rule derives is set the one way a frozen dataclass allows.
        object.__setattr__(self, 'spec', schema_spec(self.source))

    def message(self) -> str:
        """State the number of fields the block holds against the least the schema requires."""
        return f'too few fields ({self.field_count} < {self.limit})'

    def labels(self) -> tuple[Label, ...]:
        """Say how many fields the block falls short of the limit, on line 1."""
        return (Label(Here(self.line), f'fields short of the limit: {self.limit.value - self.field_count.value}'),)

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Say where the schema is stated, then what it describes, when it says."""
        parts: list[Subdiagnostic] = [schema_note(self.source)]
        if self.description is not None:
            parts.append(Help(self.description))
        return tuple(parts)

    @classmethod
    def query(cls) -> ItemQuery[tuple[SchemaProblems, ...]]:
        """What each schema that governs the subject rejects in its frontmatter."""
        return schema_problems

    @classmethod
    def judge(cls, facts: tuple[SchemaProblems, ...], /) -> tuple[Self, ...]:
        """One occurrence for each schema that finds fewer fields than it requires, in the order found.

        Args:
            facts: What each governing schema rejects, in the order the schemas apply.
        """
        occurrences: list[Self] = []
        for schema in facts:
            for located in schema.problems:
                problem = located.problem
                match problem:
                    case BlockProblem(constraint=MinFields() as constraint):
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
                        pass  # `invalid-frontmatter`'s or `too-many-fields`'s condition
                    case MissingFieldProblem() | UnknownFieldProblem() | WrongTypeProblem() | InvalidValueProblem():
                        pass  # another rule's condition
                    case _:
                        assert_never(problem)
        return tuple(occurrences)
