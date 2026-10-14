"""`FM002`: a frontmatter block is not valid YAML."""

from dataclasses import dataclass, field
from typing import ClassVar, Self, assert_never

from lorecraft.core.path import RootRelativePath
from lorecraft.project.context import FrontmatterContext, FrontmatterOwner
from lorecraft.project.schemas import FIRST_LINE
from lorecraft.project.syntax import (
    Frontmatter,
    InvalidYamlFrontmatter,
    LineNumber,
    MissingFrontmatter,
    NonMappingFrontmatter,
)
from lorecraft.rules.declaration import Level, Release, RuleCode, RuleName, rule
from lorecraft.rules.location import Help, Here, Label, Subdiagnostic
from lorecraft.rules.subject import FrontmatterRule

from .__ruleset__ import GROUP_ID, owner_spec, spec_note


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class InvalidYaml(FrontmatterRule):
    """A frontmatter block is not valid YAML.

    ## What it does

    Checks for documents whose structure specification sets a `frontmatter` schema, and for skills, whose
    frontmatter block cannot be read as YAML, or uses a construct frontmatter does not allow, such as a tag, an
    anchor or a key that is not a string. It is reported on the line the writer fixes, with what is wrong and, for
    a syntax error, what to do, or on the first line, the one that opens the block, when that line cannot be
    known, such as for collections nested too deeply to read.

    A document no `frontmatter` schema governs is not checked.

    ## Why is this bad?

    An agent that cannot read the block cannot read any field of it, so a single misplaced character hides the
    `name` and `description` it decides on.

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
        spec: The specification file that governs the owner's frontmatter, derived from `owner`, so no caller states
            one that disagrees with it.
        owner: The document or the skill whose frontmatter is not YAML, and so which specification governs it.
        problem: What is wrong with the YAML, in lorecraft's words.
        stopped_at: The line the YAML reader stopped on, which the occurrence is reported at; or `None` when it
            cannot be known, and the occurrence is reported at the line that opens the block.
        help: What to do about it, where the problem has a fix to name.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 2)
    NAME: ClassVar[RuleName] = RuleName('invalid-yaml')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('0.3.0')

    # Reported at the line the YAML reader stopped on, or else at the line that opens the block, so it is derived
    # from `stopped_at` and no caller can state a line that disagrees with it. The specification file is derived
    # from `owner` the same way.
    line: LineNumber = field(init=False)
    spec: RootRelativePath | None = field(init=False)
    owner: FrontmatterOwner
    problem: str
    stopped_at: LineNumber | None
    help: str | None = None

    def __post_init__(self) -> None:
        """Derive the reported line from where the YAML reader stopped, and the specification from the owner."""
        # The dataclass is frozen, so the field a rule derives is set the one way a frozen dataclass allows.
        object.__setattr__(self, 'line', FIRST_LINE if self.stopped_at is None else self.stopped_at)
        object.__setattr__(self, 'spec', owner_spec(self.owner))

    def message(self) -> str:
        """Name what the block is not; the problem, in lorecraft's words, is the label's."""
        return 'frontmatter is not valid YAML'

    def labels(self) -> tuple[Label, ...]:
        """Give the problem where it is, or else say it lies somewhere in the block."""
        if self.stopped_at is None:
            return (Label(Here(self.line), f'{self.problem}, somewhere in the block opened here'),)
        return (Label(Here(self.line), self.problem),)

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Name what to do about the problem, where there is one, and the specification that governs the frontmatter."""
        if self.help is None:
            return (spec_note(self.owner),)
        return (Help(self.help), spec_note(self.owner))

    @classmethod
    def check(cls, subject: FrontmatterContext) -> tuple[Self, ...]:
        """The one occurrence, at the line the YAML reader stopped on or else line 1, when the block is not YAML.

        Args:
            subject: The document or the skill whose frontmatter is judged.
        """
        frontmatter = subject.frontmatter()
        match frontmatter:
            case InvalidYamlFrontmatter():
                return (
                    cls(
                        owner=subject.frontmatter_owner(),
                        problem=frontmatter.problem,
                        stopped_at=frontmatter.line,
                        help=frontmatter.help,
                    ),
                )
            case MissingFrontmatter() | NonMappingFrontmatter() | Frontmatter():
                return ()
            case _:
                assert_never(frontmatter)
