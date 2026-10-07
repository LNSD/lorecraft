"""`FM002`: a frontmatter block is not valid YAML."""

from dataclasses import dataclass
from typing import ClassVar, Self, assert_never

from lorecraft.project.context import FrontmatterContext
from lorecraft.project.schemas import FIRST_LINE
from lorecraft.project.syntax import (
    Frontmatter,
    InvalidYamlFrontmatter,
    LineNumber,
    MissingFrontmatter,
    NonMappingFrontmatter,
)
from lorecraft.rules.declaration import Level, Release, RuleCode, RuleName, rule
from lorecraft.rules.location import Here, Label, Subdiagnostic
from lorecraft.rules.subject import FrontmatterRule

from .__ruleset__ import GROUP_ID, owner_spec, spec_note


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class InvalidYaml(FrontmatterRule):
    """A frontmatter block is not valid YAML.

    ## What it does

    Checks for documents whose structure specification sets a `frontmatter` schema, and for skills, whose
    frontmatter block cannot be read as YAML. It is reported on the line the YAML stops being readable, or on the
    first line, the one that opens the block, when that line cannot be known, such as for collections nested too
    deeply to read.

    A document no `frontmatter` schema governs is not checked.

    ## Why is this bad?

    An agent that cannot read the block cannot read any field of it, so a single misplaced character hides the
    `name` and `description` it decides on.

    ## Example

    `docs/__meta__/guide.structure.json`:

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
    description: Setup: install the toolkit
    ---

    # Setup
    ```

    ## Use instead

    Quote a value that holds a `: `:

    ```markdown
    ---
    name: setup
    description: "Setup: install the toolkit"
    ---

    # Setup
    ```

    Attributes:
        spec: The structure specification whose frontmatter schema governs the document, or `None` for a skill,
            which the Agent Skills specification governs.
        problem: What is wrong with the YAML, in the words of the YAML reader.
        stopped_at: The line the YAML reader stopped on, which the occurrence is reported at; or `None` when it
            cannot be known, and the occurrence is reported at the line that opens the block.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 2)
    NAME: ClassVar[RuleName] = RuleName('invalid-yaml')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('0.3.0')

    problem: str
    stopped_at: LineNumber | None

    def message(self) -> str:
        """Name what the block is not; the reader's words for the problem are the label's."""
        return 'frontmatter is not valid YAML'

    def labels(self) -> tuple[Label, ...]:
        """Give the YAML reader's problem where it stopped, or else say it lies somewhere in the block."""
        if self.stopped_at is None:
            return (Label(Here(self.line), f'{self.problem}, somewhere in the block opened here'),)
        return (Label(Here(self.line), self.problem),)

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Name the specification that governs the frontmatter."""
        return (spec_note(self.spec),)

    @classmethod
    def check(cls, subject: FrontmatterContext) -> tuple[Self, ...]:
        """The one occurrence, at the line the YAML reader stopped on or else line 1, when the block is not YAML.

        Args:
            subject: The document or the skill whose frontmatter is judged.
        """
        frontmatter = subject.frontmatter()
        match frontmatter:
            case InvalidYamlFrontmatter():
                stopped_at = frontmatter.line
                line = FIRST_LINE if stopped_at is None else stopped_at
                spec = owner_spec(subject.frontmatter_owner())
                return (cls(spec=spec, line=line, problem=frontmatter.problem, stopped_at=stopped_at),)
            case MissingFrontmatter() | NonMappingFrontmatter() | Frontmatter():
                return ()
            case _:
                assert_never(frontmatter)
