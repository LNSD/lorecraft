"""`LAY001`: a symlink an agent follows in the skill layout leads outside the repository."""

from dataclasses import dataclass
from typing import ClassVar, Self

from lorecraft.project.context import LayoutContext
from lorecraft.rules.declaration import Level, Release, RuleCode, RuleName, rule
from lorecraft.rules.location import EntryHelp, EntryNote, EntrySubdiagnostic
from lorecraft.rules.subject import LayoutEntryRule
from lorecraft.vfs import RootExit

from .__ruleset__ import GROUP_ID


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class OutsideSymlink(LayoutEntryRule):
    """A symlink an agent follows in the skill layout leads outside the repository.

    ## What it does

    Checks for symlinks an agent follows to load a skill whose chain leads outside the repository: a skills
    directory, an entry in a skills directory, an entry's `SKILL.md`, or a file or directory inside a skill. The
    chain leaves when any link on it does, the symlink itself or one it leads through, by an absolute target or by
    a `..` that climbs above the repository's root. A symlink that leads elsewhere inside the repository does not
    count, nor does one that dangles inside it. Nothing behind a symlink that leaves is read, so no other rule
    judges what it leads to. The package states the rule; no specification sets or changes it.

    ## Why is this bad?

    An agent loads whatever the symlink leads to, which the repository does not hold, so the skill loads
    differently, or not at all, for everyone who checks the repository out somewhere else.

    ## Example

    `.agents/skills/review`, linked to a directory in one user's home:

    ```console
    $ ls -l .agents/skills
    review -> /home/alex/skills/review
    ```

    ## Use instead

    Keep the skill inside the repository, and link to it there:

    ```console
    $ ls -l .agents/skills
    review -> ../../skills/review
    ```

    Attributes:
        spec: Always `None`: the package states the rule.
        leaves_at: The link the symlink's chain leaves the repository through, and that link's target as the scan
            recorded it: the symlink itself when it links straight out, or another link on its chain.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 1)
    NAME: ClassVar[RuleName] = RuleName('outside-symlink')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('0.3.0')

    spec: None = None
    leaves_at: RootExit

    def message(self) -> str:
        """Name the condition."""
        return 'symlink leads outside the repository'

    def children(self) -> tuple[EntrySubdiagnostic, ...]:
        """Say what to do about the target, then name the link the chain leaves through and its target."""
        if self.leaves_at.target.is_absolute():
            help_text = (
                'an absolute target resolves differently in every checkout; move what it links to into the repository'
            )
        else:
            help_text = (
                'a `..` on the chain climbs above the repository root; move what it links to into the repository'
            )
        return (
            EntryHelp(help_text),
            EntryNote(f'leaves the repository at {self.leaves_at.link} -> {self.leaves_at.target}'),
        )

    @classmethod
    def check(cls, subject: LayoutContext) -> tuple[Self, ...]:
        """The one occurrence, at the symlink, naming where its chain leaves the repository.

        Every layout entry is a symlink whose chain leaves the repository, as the scan found it, so the rule only
        words the finding.

        Args:
            subject: The symlink judged.
        """
        return (cls(leaves_at=subject.leaves_at()),)
