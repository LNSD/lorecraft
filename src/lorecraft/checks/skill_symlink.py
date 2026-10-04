"""Report a symlink of the skill layout whose chain leads outside the repository.

A workspace must be self-contained: nothing an agent loads from it may come from outside the repository, so a
repository's skills load the same for everyone who checks it out. An agent lists its skills directories, the
entries in them and the files inside each skill, and the operating system follows every symlink on the way, so a
symlink anywhere in that layout that leads outside the repository loads something the repository does not hold.

The check is pure: it takes where a symlink's chain leaves the root, as the model or a skill's resource listing
records it, and returns violations. Finding those symlinks happens below it, in the model's loader and the walk over
a skill's files, from the link targets the snapshot recorded and nothing outside the root. Whether a chain leaves
the root is decided there; the check only words the finding. It is a sibling of the frontmatter half in `skill`,
and reports in the same `SkillCheckResult`.
"""

from typing import Final

from lorecraft.project.syntax import LineNumber
from lorecraft.vfs import RootExit

from .reporting import Note, NoteKind, Violation
from .skill import SkillCheckResult

_FIRST_LINE: Final[LineNumber] = LineNumber.from_int(1)
"""Where the violation is reported: a symlink has no lines, so the finding is about the whole entry."""


def validate_outside_symlink(*, leaves_at: RootExit) -> SkillCheckResult:
    """Report one symlink whose chain leaves the repository. Pure: raises nothing.

    The symlink is `skill.symlink-outside`, on line 1, with a note naming the link its chain leaves through and
    that link's target, as the snapshot recorded it, then a help note on how to fix it.

    Args:
        leaves_at: The link the symlink's chain leaves the root through, and that link's target: the symlink itself
            when it links straight out, or one further along, or on the way to it.
    """
    violation = Violation(
        line=_FIRST_LINE,
        rule='skill.symlink-outside',
        message='symlink leads outside the repository',
        notes=(
            Note(NoteKind.NOTE, f'leaves the repository at {leaves_at.link} -> {leaves_at.target}'),
            Note(NoteKind.HELP, 'keep every file a skill loads inside the repository'),
        ),
    )
    return SkillCheckResult(violations=(violation,))
