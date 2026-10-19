"""`FM008`: a frontmatter field's value is of a type its schema does not accept."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import ClassVar, Final, Self, assert_never

from lorecraft.core.path import RootRelativePath
from lorecraft.jsonschema import JsonType
from lorecraft.project.item import ItemKind
from lorecraft.project.query import ItemQuery
from lorecraft.project.schemas import (
    BlockProblem,
    InvalidValueProblem,
    MissingFieldProblem,
    SchemaProblems,
    SchemaSource,
    UnknownFieldProblem,
    WrongTypeProblem,
)
from lorecraft.rules.collector import rule
from lorecraft.rules.identity import Level, Release, RuleCode, RuleName
from lorecraft.rules.location import Help, Here, Label, Subdiagnostic
from lorecraft.rules.subject import BySpec, Facet, Gate, QueriedItemRule

from .__ruleset__ import GROUP_ID, example_note, schema_note, schema_problems, schema_spec

_SCALARS_YAML_READS_UNQUOTED: Final[frozenset[JsonType]] = frozenset(
    {JsonType.INTEGER, JsonType.NUMBER, JsonType.BOOLEAN}
)
"""The types YAML reads an unquoted `1`, `1.0` or `yes` as, where a string was meant."""


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class WrongType(QueriedItemRule[tuple[SchemaProblems, ...]]):
    """A frontmatter field's value is of a type its schema does not accept.

    ## What it does

    Checks for documents whose frontmatter gives a field a value of a type other than the one the `type` keyword of
    its property states in their structure file's `frontmatter` schema, and for skills whose frontmatter
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
        spec: The structure file that states the schema, derived from `source`, so no caller states one that
            disagrees with it; `None` for the Agent Skills specification.
        source: The schema that found the problem: a structure file's, or the Agent Skills specification's.
        problem: The field whose value is of the wrong type, with the types the schema expects and the type found.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 8)
    NAME: ClassVar[RuleName] = RuleName('wrong-type')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('0.3.0')
    GATES: ClassVar[Mapping[ItemKind, Gate]] = MappingProxyType(
        {
            ItemKind.DOCUMENT: BySpec(Facet.FRONTMATTER),
            ItemKind.SKILL_ENTRY: BySpec(Facet.FRONTMATTER),
        }
    )

    # The specification file is derived from `source`, so no caller can state one that disagrees with it.
    spec: RootRelativePath | None = field(init=False)
    source: SchemaSource
    problem: WrongTypeProblem

    def __post_init__(self) -> None:
        """Derive the structure file from the schema that found the problem."""
        # The dataclass is frozen, so the field a rule derives is set the one way a frozen dataclass allows.
        object.__setattr__(self, 'spec', schema_spec(self.source))

    def message(self) -> str:
        """Name the field whose value is of the wrong type."""
        return f'field `{self.problem.field}` has a type the schema does not accept'

    def labels(self) -> tuple[Label, ...]:
        """Say the types the schema expects and the type found, on the field's line."""
        expected = ' or '.join(self.problem.expected)
        return (Label(Here(self.line), f'expected {expected}, found {self.problem.found}'),)

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
    def query(cls) -> ItemQuery[tuple[SchemaProblems, ...]]:
        """What each schema that governs the subject rejects in its frontmatter."""
        return schema_problems

    @classmethod
    def judge(cls, facts: tuple[SchemaProblems, ...], /) -> tuple[Self, ...]:
        """One occurrence for each value a schema found of the wrong type, schema by schema, in the order found.

        Args:
            facts: What each governing schema rejects, in the order the schemas apply.
        """
        occurrences: list[Self] = []
        for schema in facts:
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
