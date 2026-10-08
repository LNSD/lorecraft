"""`LINK004`: a relative link in a skill's file climbs above the skill root."""

from dataclasses import dataclass
from typing import ClassVar, Self
from urllib.parse import unquote

from lorecraft.project.context import SkillFileContext
from lorecraft.rules.declaration import Level, Release, RuleCode, RuleName, rule
from lorecraft.rules.location import Help, Subdiagnostic
from lorecraft.rules.subject import SkillFileRule

from .__ruleset__ import GROUP_ID, skill_note


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class EscapingLink(SkillFileRule):
    """A relative link in a skill's file climbs above the skill root.

    ## What it does

    Checks for relative links and images in a skill's `SKILL.md` and in each Markdown file inside the skill whose
    path, read from the skill root, leads above it. The Agent Skills specification has every file of a skill name
    another by its path from the skill root, wherever the file lies: in `references/guide.md`, `SKILL.md` names the
    skill's own `SKILL.md`, and `../SKILL.md` leads out of the skill. No specification key states the rule: every
    skill is held to it.

    The path alone decides, never where the skill lies in the repository: `../../skills/review/SKILL.md` leaves the
    skill even when it leads back into it. A path that climbs and comes back down inside the skill, such as
    `references/../SKILL.md`, stays inside. A URL with a scheme, an absolute link and a link to a heading of the same
    file spell no relative path, so none of them is reported. A document is never judged: its links are read from
    its own directory, and may climb out of it.

    ## Why is this bad?

    A skill is installed on its own, wherever an agent keeps its skills, and carries only its own files. A link
    above the skill root points at a file the installed skill does not carry, so an agent that follows it reads
    nothing, or a file that happens to lie there.

    ## Example

    `.agents/skills/review/references/checklist.md`:

    ```markdown
    # Checklist

    Start from [the review steps](../SKILL.md).
    ```

    ## Use instead

    Name the file by its path from the skill root:

    ```markdown
    # Checklist

    Start from [the review steps](SKILL.md).
    ```

    Attributes:
        spec: Always `None`: the package states the rule, after the Agent Skills specification.
        url: The link's destination as the Markdown parser encodes it, which the message shows percent-decoded.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 4)
    NAME: ClassVar[RuleName] = RuleName('escaping-link')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('0.3.0')

    spec: None = None
    url: str

    def message(self) -> str:
        """Name the destination, percent-decoded as the author wrote it."""
        # The parser percent-encodes a destination, so `[x](<../a b>)` arrives as `../a%20b`; the message shows
        # `../a b`.
        return f'`{unquote(self.url)}` leaves the skill root'

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Point at the specification that reads the link from the skill root, then say how to name the file."""
        return (skill_note(), Help('link a file inside the skill, relative to the skill root'))

    @classmethod
    def check(cls, subject: SkillFileContext) -> tuple[Self, ...]:
        """One occurrence for each relative link whose path climbs above the skill root, on its line, in file order.

        Args:
            subject: The skill's `SKILL.md` or one of its resources, whose links are read from the skill root.
        """
        occurrences: list[Self] = []
        for link in subject.parse().links:
            # Lexical on purpose, rather than a containment check of resolved paths: a rule performs no I/O, and the
            # link is text read from the skill root, not a filesystem path. The path alone decides, never joined to
            # the skill's directory first: a link that climbs out and back in by the repository's own path, such as
            # `../../skills/review/SKILL.md`, depends on where the skill is installed, so it escapes too.
            normalised = link.to_normalised_relative_path()
            # A URL with a scheme, an absolute or a fragment-only link spells no relative path, so it never escapes.
            if normalised is None:
                continue
            # Normalising leaves a `..` only at the start, so the first component alone decides. A slice, not
            # `parts[0]`: `references/..` normalises to `.`, whose `parts` is empty.
            if normalised.parts[:1] == ('..',):
                occurrences.append(cls(line=link.line, url=link.url))
        return tuple(occurrences)
