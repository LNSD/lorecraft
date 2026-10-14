"""`FM010`: a frontmatter breaks a constraint its schema sets on the whole block."""

from dataclasses import dataclass, field
from typing import ClassVar, Self, assert_never

from lorecraft.core.path import RootRelativePath
from lorecraft.project.context import FrontmatterContext
from lorecraft.project.schemas import (
    BlockProblem,
    InvalidValueProblem,
    MaxFields,
    MinFields,
    MissingFieldProblem,
    SchemaSource,
    UnknownFieldProblem,
    WrongTypeProblem,
)
from lorecraft.rules.collector import rule
from lorecraft.rules.identity import Level, Release, RuleCode, RuleName
from lorecraft.rules.location import Help, Label, Note, Subdiagnostic
from lorecraft.rules.subject import FrontmatterRule

from .__ruleset__ import GROUP_ID, schema_note, schema_spec


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class InvalidFrontmatter(FrontmatterRule):
    """A frontmatter breaks a constraint its schema sets on the whole block.

    ## What it does

    Checks for documents whose frontmatter breaks a constraint their structure file's `frontmatter`
    schema sets on the block rather than on one field. It is reported on line 1, since it concerns no one field. A
    block with fewer fields than `minProperties` requires is reported by `too-few-fields`, and one with more than
    `maxProperties` allows by `too-many-fields`. A skill's frontmatter is reported here only when the Agent Skills
    meta spec rejects it without naming a field.

    A constraint that names a key is not the block's: a key `propertyNames` rejects, and a field whose
    `dependentRequired` fields are missing, are reported by `invalid-value` on that key's line.

    The help is the description the schema states for the block, when it states one, and the schema's own wording
    is shown as a note.

    ## Why is this bad?

    The schema states what the block must hold as a whole so that every document gives an agent the same facts; a
    block outside it leaves the agent without some of them.

    ## Example

    `docs/__meta__/guide.spec.json`:

    ```json
    {
      "frontmatter": {
        "type": "object",
        "anyOf": [
          {"required": ["summary"]},
          {"required": ["description"]}
        ]
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
    description: Install the toolkit and run it once over the repository.
    ---

    # Setup
    ```

    Attributes:
        spec: The structure file that states the schema, derived from `source`, so no caller states one that
            disagrees with it; `None` for the Agent Skills specification.
        source: The schema that found the problem: a structure file's, or the Agent Skills specification's.
        problem: The constraint over the whole block that the frontmatter breaks, with the number of fields it holds.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 10)
    NAME: ClassVar[RuleName] = RuleName('invalid-frontmatter')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('0.3.0')

    # The specification file is derived from `source`, so no caller can state one that disagrees with it.
    spec: RootRelativePath | None = field(init=False)
    source: SchemaSource
    problem: BlockProblem

    def __post_init__(self) -> None:
        """Derive the structure file from the schema that found the problem."""
        # The dataclass is frozen, so the field a rule derives is set the one way a frozen dataclass allows.
        object.__setattr__(self, 'spec', schema_spec(self.source))

    def message(self) -> str:
        """Say the block breaks a constraint on the whole of it."""
        return 'frontmatter breaks a constraint of the schema on the whole block'

    def labels(self) -> tuple[Label, ...]:
        """Label nothing: the constraint has no typed limit to name."""
        return ()

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Say where the schema is stated and what it describes, then the validator's own wording."""
        problem = self.problem
        parts: list[Subdiagnostic] = [schema_note(self.source)]
        if problem.description is not None:
            parts.append(Help(problem.description))
        parts.append(Note(problem.message))
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
                    case BlockProblem(constraint=MinFields()):
                        pass  # `too-few-fields`'s condition
                    case BlockProblem(constraint=MaxFields()):
                        pass  # `too-many-fields`'s condition
                    case BlockProblem():
                        occurrences.append(cls(source=schema.source, line=located.line, problem=problem))
                    case MissingFieldProblem() | UnknownFieldProblem() | WrongTypeProblem() | InvalidValueProblem():
                        pass  # another rule's condition
                    case _:
                        assert_never(problem)
        return tuple(occurrences)
