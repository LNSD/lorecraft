"""`FM001`: a document or a skill does not open with a frontmatter block."""

from dataclasses import dataclass
from typing import ClassVar, Self, assert_never

# The module, not its classes: this rule's own name is the syntax's `MissingFrontmatter`.
from lorecraft.project import syntax
from lorecraft.project.schemas import FIRST_LINE
from lorecraft.rules.declaration import Level, Release, RuleCode, RuleName, rule
from lorecraft.rules.inputs import FrontmatterBlockInput, FrontmatterBlockRule, FrontmatterFields
from lorecraft.rules.location import Subdiagnostic

from .__ruleset__ import GROUP_ID, owner_spec, spec_note


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class MissingFrontmatter(FrontmatterBlockRule):
    """A document or a skill does not open with a frontmatter block.

    ## What it does

    Checks for documents whose structure specification sets a `frontmatter` schema, and for skills, whose
    `SKILL.md` the Agent Skills specification requires to open with frontmatter, that do not open with a block
    between two `---` lines. A file whose first line is not `---`, or whose block is never closed by a second
    `---` line, has none.

    A document no `frontmatter` schema governs is not checked.

    ## Why is this bad?

    An agent decides whether to load a document or a skill from its frontmatter, its `name` and `description`
    among them; without a block it has nothing to decide on, and loads the file blind or never.

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
    # Setup

    Install the toolkit, then run it once over the repository.
    ```

    ## Use instead

    Open the file with the block:

    ```markdown
    ---
    name: setup
    description: Install the toolkit and run it for the first time.
    ---

    # Setup

    Install the toolkit, then run it once over the repository.
    ```

    Attributes:
        spec: The structure specification whose frontmatter schema governs the document, or `None` for a skill,
            which the Agent Skills specification governs.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 1)
    NAME: ClassVar[RuleName] = RuleName('missing-frontmatter')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('0.3.0')

    def message(self) -> str:
        """Name the block that is missing."""
        return 'no `---` delimited frontmatter block'

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Name the specification that governs the frontmatter."""
        return (spec_note(self.spec),)

    @classmethod
    def check(cls, subject: FrontmatterBlockInput) -> tuple[Self, ...]:
        """The one occurrence, on line 1, when the subject has no frontmatter block; none otherwise.

        Args:
            subject: The subject's frontmatter block, and the subject it opens.
        """
        frontmatter = subject.frontmatter
        match frontmatter:
            case syntax.MissingFrontmatter():
                return (cls(spec=owner_spec(subject.owner), line=FIRST_LINE),)
            case syntax.InvalidYamlFrontmatter() | syntax.NonMappingFrontmatter() | FrontmatterFields():
                return ()
            case _:
                assert_never(frontmatter)
