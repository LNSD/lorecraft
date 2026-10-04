"""`FM002`: a frontmatter block is not valid YAML."""

from dataclasses import dataclass
from typing import ClassVar, Self, assert_never

from lorecraft.project.syntax import InvalidYamlFrontmatter, MissingFrontmatter, NonMappingFrontmatter
from lorecraft.rules.declaration import Level, Release, RuleCode, RuleName, rule
from lorecraft.rules.inputs import FrontmatterBlockInput, FrontmatterBlockRule, FrontmatterFields
from lorecraft.rules.location import Subdiagnostic

from .__ruleset__ import FIRST_LINE, GROUP_ID, owner_spec, spec_note


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class InvalidYaml(FrontmatterBlockRule):
    """A frontmatter block is not valid YAML.

    ## What it does

    Checks for documents whose structure specification sets a `frontmatter` schema, and for skills, whose
    frontmatter block cannot be read as YAML. It is reported on the line the YAML stops being readable, or on the
    first line when that line cannot be known, such as for collections nested too deeply to read.

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
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 2)
    NAME: ClassVar[RuleName] = RuleName('invalid-yaml')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('0.3.0')

    problem: str

    def message(self) -> str:
        """Name what is wrong with the YAML."""
        return f'frontmatter is not valid YAML ({self.problem})'

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Name the specification that governs the frontmatter."""
        return (spec_note(self.spec),)

    @classmethod
    def check(cls, subject: FrontmatterBlockInput) -> tuple[Self, ...]:
        """The one occurrence, at the line the YAML reader stopped on or else line 1, when the block is not YAML.

        Args:
            subject: The subject's frontmatter block, and the subject it opens.
        """
        frontmatter = subject.frontmatter
        match frontmatter:
            case InvalidYamlFrontmatter():
                line = FIRST_LINE if frontmatter.line is None else frontmatter.line
                return (cls(spec=owner_spec(subject.owner), line=line, problem=frontmatter.problem),)
            case MissingFrontmatter() | NonMappingFrontmatter() | FrontmatterFields():
                return ()
            case _:
                assert_never(frontmatter)
