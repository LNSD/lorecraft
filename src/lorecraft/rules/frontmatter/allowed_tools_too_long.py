"""`FM012`: a skill's `allowed-tools` value exceeds Lorecraft's recommended length."""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import ClassVar, Final, Self

from lorecraft.core.num import NonZeroUnsignedInt, UnsignedInt
from lorecraft.project.item import ItemType
from lorecraft.project.query import ItemQuery
from lorecraft.rules.collector import rule
from lorecraft.rules.identity import Level, Release, RuleCode, RuleName
from lorecraft.rules.location import Help, Here, Label, Note, Subdiagnostic
from lorecraft.rules.overrun import Overrun, find_overrun
from lorecraft.rules.subject import Gate, QueriedItemRule, SpecPart, WhenSpec

from .__ruleset__ import ALLOWED_TOOLS_NOTE, GROUP_ID, AllowedToolsField, allowed_tools_field

_CHARACTER_LIMIT: Final[NonZeroUnsignedInt] = NonZeroUnsignedInt(500)
"""Lorecraft's recommended length, matching the compatibility field's maximum."""


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class AllowedToolsTooLong(QueriedItemRule[AllowedToolsField | None]):
    """A skill's `allowed-tools` value exceeds the recommended length.

    ## What it does

    Checks for skills whose whole `allowed-tools` value exceeds 500 characters, including whitespace and
    parenthesised patterns. Exactly 500 characters is within the recommendation. Characters count, not bytes.
    This is Lorecraft's recommendation, matching the Agent Skills specification's limit for `compatibility`;
    that specification sets no length limit for `allowed-tools`. No repository spec changes it.

    ## Why is this bad?

    A long list of pre-approved tools hides which permissions the skill really needs: an agent running the skill holds
    every tool the list approves, so each unnecessary or overlapping entry widens what it may do without asking.

    ## Example

    `.agents/skills/review/SKILL.md`, with more than 500 characters in `allowed-tools`:

    ```markdown
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

    ```markdown
    ---
    name: review
    description: Review a change.
    allowed-tools: Read Grep Bash(git diff *)
    ---
    ```

    Attributes:
        spec: Always `None`: the package states this recommendation.
        overrun: The characters in the whole `allowed-tools` value against the recommended length.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 12)
    NAME: ClassVar[RuleName] = RuleName('allowed-tools-too-long')
    LEVEL: ClassVar[Level] = Level.WARN
    SINCE: ClassVar[Release] = Release('0.3.0')
    APPLIES_TO: ClassVar[Mapping[ItemType, Gate]] = MappingProxyType(
        {ItemType.SKILL_ENTRYPOINT: WhenSpec(SpecPart.FRONTMATTER)}
    )

    spec: None = None
    overrun: Overrun

    def message(self) -> str:
        """Name the characters found against the recommended length."""
        return f'`allowed-tools` value too long ({self.overrun.count} > {self.overrun.cap})'

    def labels(self) -> tuple[Label, ...]:
        """Say how many characters the value runs past the recommended length, on the field's line."""
        return (Label(Here(self.line), f'characters over the recommended length: {self.overrun.excess}'),)

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Say where the field is specified, how to shorten the value, and whose limit this is."""
        return (
            ALLOWED_TOOLS_NOTE,
            Help(
                'keep only the tools the skill needs, and merge patterns such as '
                '`Bash(git diff *) Bash(git log *)` into `Bash(git *)`'
            ),
            Note(
                f'Lorecraft recommends at most {self.overrun.cap} characters, the `compatibility` limit; '
                'the Agent Skills specification sets none for `allowed-tools`'
            ),
        )

    @classmethod
    def query(cls) -> ItemQuery[AllowedToolsField | None]:
        """The `allowed-tools` field and its line."""
        return allowed_tools_field

    @classmethod
    def judge(cls, facts: AllowedToolsField | None, /) -> tuple[Self, ...]:
        """Report an overlong value at the field's line.

        Args:
            facts: The field as written; `None` when the skill writes none.
        """
        if facts is None:
            return ()
        overrun = find_overrun(UnsignedInt(len(facts.tools.text)), _CHARACTER_LIMIT)
        if overrun is None:
            return ()
        return (cls(line=facts.line, overrun=overrun),)
