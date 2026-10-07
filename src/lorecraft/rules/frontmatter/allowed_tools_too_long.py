"""`FM012`: a skill's `allowed-tools` value exceeds Lorecraft's recommended length."""

from dataclasses import dataclass
from typing import ClassVar, Final, Self, assert_never

from lorecraft.project.context import SkillContext
from lorecraft.project.schemas import field_line
from lorecraft.project.syntax import Frontmatter, InvalidYamlFrontmatter, MissingFrontmatter, NonMappingFrontmatter
from lorecraft.rules.declaration import Level, Release, RuleCode, RuleName, rule
from lorecraft.rules.location import Subdiagnostic
from lorecraft.rules.subject import SkillRule

from .__ruleset__ import GROUP_ID

_CHARACTER_LIMIT: Final[int] = 500
"""Lorecraft's recommended length, matching the compatibility field's maximum."""


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class AllowedToolsTooLong(SkillRule):
    """A skill's `allowed-tools` value exceeds the recommended length.

    ## What it does

    Checks for skills whose whole `allowed-tools` value exceeds 500 characters, including whitespace and
    parenthesised patterns. Exactly 500 characters is within the recommendation. Characters count, not bytes.
    This is Lorecraft's recommendation, matching the Agent Skills specification's limit for `compatibility`;
    that specification sets no length limit for `allowed-tools`. No repository specification changes it.

    ## Why is this bad?

    A long list of pre-approved tools is harder to review for unnecessary permissions and overlapping patterns.

    ## Example

    `.agents/skills/review/SKILL.md`, with more than 500 characters in `allowed-tools`:

    ```yaml
    ---
    name: review
    description: Review a change.
    allowed-tools: >-
      Read Grep Bash(git diff *) Bash(git log *)
      # ... many more tool entries
    ---
    ```

    ## Use instead

    Keep only the permissions the skill needs:

    ```yaml
    ---
    name: review
    description: Review a change.
    allowed-tools: Read Grep Bash(git diff *)
    ---
    ```

    Attributes:
        spec: Always `None`: the package states this recommendation.
        character_count: The characters in the whole `allowed-tools` value.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 12)
    NAME: ClassVar[RuleName] = RuleName('allowed-tools-too-long')
    LEVEL: ClassVar[Level] = Level.WARN
    SINCE: ClassVar[Release] = Release('0.3.0')

    spec: None = None
    character_count: int

    def message(self) -> str:
        """Name the characters found against the recommended length."""
        return f'`allowed-tools` value too long ({self.character_count} > {_CHARACTER_LIMIT})'

    def children(self) -> tuple[Subdiagnostic, ...]:
        """No external specification sets this recommendation."""
        return ()

    @classmethod
    def check(cls, subject: SkillContext) -> tuple[Self, ...]:
        """Report an overlong value at the field's line.

        Args:
            subject: The skill whose frontmatter is judged.
        """
        frontmatter = subject.frontmatter()
        match frontmatter:
            case Frontmatter():
                pass
            case MissingFrontmatter() | InvalidYamlFrontmatter() | NonMappingFrontmatter():
                return ()
            case _:
                assert_never(frontmatter)

        value = frontmatter.data.get('allowed-tools')
        if not isinstance(value, str):
            return ()
        character_count = len(value)
        if character_count <= _CHARACTER_LIMIT:
            return ()
        return (cls(line=field_line(frontmatter, 'allowed-tools'), character_count=character_count),)
