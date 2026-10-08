"""What the `LEN` group's rules share: the group, the specification note, and the help for a title.

A document's limits come from its structure specifications: a token budget, a word cap on a section or the title, a
character cap on the title. Every rule of the group that holds a document to one points at the file that sets it
through `spec_note`. A document that more than one specification governs is reported once for each limit it exceeds,
and the note is what tells those occurrences apart. The one rule over a skill, `LEN002`, is held to a limit the Agent
Skills specification states, which no file in the repository holds, so it words its own note.
"""

from typing import Final

from lorecraft.core.path import RootRelativePath
from lorecraft.rules.declaration import RuleGroup, RuleGroupPrefix
from lorecraft.rules.location import Elsewhere, Help, Note

GROUP_ID: Final[RuleGroup] = RuleGroup(RuleGroupPrefix('LEN'), 'Length limits')
"""The group of the rules that hold a subject to a length limit: a document's token budget among them."""

TITLE_HELP: Final[Help] = Help('name what the document is about, and leave the rest to its first paragraph')
"""How to bring a title under any of its caps, whichever of them it exceeds."""


def spec_note(spec: RootRelativePath) -> Note:
    """The note pointing at the structure specification that sets the limit an occurrence exceeds.

    Args:
        spec: The structure specification file that sets the limit.
    """
    return Note('the limit is set here', at=Elsewhere(spec))
