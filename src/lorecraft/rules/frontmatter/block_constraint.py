"""`FM010`: a frontmatter breaks a constraint its schema sets on the whole block."""

from dataclasses import dataclass
from typing import ClassVar, Self, assert_never

from lorecraft.project.context import FrontmatterContext
from lorecraft.project.schemas import (
    BlockProblem,
    InvalidValueProblem,
    MaxFields,
    MinFields,
    MissingFieldProblem,
    OtherBlockConstraint,
    UnknownFieldProblem,
    WrongTypeProblem,
)
from lorecraft.rules.declaration import Level, Release, RuleCode, RuleName, rule
from lorecraft.rules.location import Help, Here, Label, Note, Subdiagnostic
from lorecraft.rules.subject import FrontmatterRule

from .__ruleset__ import GROUP_ID, schema_note, schema_spec


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class BlockConstraint(FrontmatterRule):
    """A frontmatter breaks a constraint its schema sets on the whole block.

    ## What it does

    Checks for documents whose frontmatter breaks a constraint their structure specification's `frontmatter`
    schema sets on the block rather than on one field, such as `minProperties` or `maxProperties`. It is reported
    on line 1, since it concerns no one field. A skill's frontmatter is reported here only when the Agent Skills
    specification rejects it without naming a field.

    A constraint that names a key is not the block's: a key `propertyNames` rejects, and a field whose
    `dependentRequired` fields are missing, are reported by `invalid-value` on that key's line.

    The label says how many fields the block holds against the limit, for `minProperties` and `maxProperties`, and
    the help is the description the schema states for the block, when it states one. The validator's own wording
    is shown as a note only for another keyword.

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
        problem: The constraint over the whole block that the frontmatter breaks, with the number of fields it holds.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 10)
    NAME: ClassVar[RuleName] = RuleName('block-constraint')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('0.3.0')

    problem: BlockProblem

    def message(self) -> str:
        """Say the block breaks a constraint on the whole of it; the label names the constraint."""
        return 'frontmatter breaks a constraint of the schema on the whole block'

    def labels(self) -> tuple[Label, ...]:
        """Say how many fields the block holds against the limit, for a limit on their number; else none."""
        constraint = self.problem.constraint
        fields = _fields(self.problem.field_count)
        match constraint:
            case MinFields():
                return (
                    Label(Here(self.line), f'has {fields}; the schema requires at least {_fields(constraint.limit)}'),
                )
            case MaxFields():
                return (Label(Here(self.line), f'has {fields}; the schema allows at most {_fields(constraint.limit)}'),)
            case OtherBlockConstraint():
                return ()
            case _:
                assert_never(constraint)

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Say where the schema is stated and what it describes, then for another keyword its own wording."""
        problem = self.problem
        parts: list[Subdiagnostic] = [schema_note(self.spec)]
        if problem.description is not None:
            parts.append(Help(problem.description))
        constraint = problem.constraint
        match constraint:
            case OtherBlockConstraint():
                parts.append(Note(problem.message))
            case MinFields() | MaxFields():
                pass  # the label says it
            case _:
                assert_never(constraint)
        return tuple(parts)

    @classmethod
    def check(cls, subject: FrontmatterContext) -> tuple[Self, ...]:
        """One occurrence for each block constraint a schema found broken, schema by schema, in the order found.

        Args:
            subject: The document or the skill whose frontmatter each governing schema is applied to.
        """
        occurrences: list[Self] = []
        for schema in subject.schema_problems():
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


def _fields(count: int) -> str:
    """A number of fields, in the singular for one.

    Args:
        count: The number of fields.
    """
    if count == 1:
        return '1 field'
    return f'{count} fields'
