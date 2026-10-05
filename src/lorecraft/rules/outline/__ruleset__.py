"""What the `OUT` group's rules share: the group, and the note naming the specification that states a rule.

A document's sections are governed by every structure specification that governs the document, each on its own: a
document governed by a corpus and a namespace specification is reported once for each one it breaks. Every rule of
the group says which specification an occurrence breaks through `spec_note`, so two occurrences from two
specifications read apart.
"""

from typing import Final

from lorecraft.core.path import RootRelativePath
from lorecraft.rules.declaration import RuleGroup
from lorecraft.rules.location import Elsewhere, Note

GROUP_ID: Final[RuleGroup] = RuleGroup('OUT', 'Outline checks')
"""The group of the rules over a document's sections that a structure specification states: its title among them."""


def spec_note(spec: RootRelativePath) -> Note:
    """The note pointing at the structure specification that states the rule an occurrence breaks.

    Args:
        spec: The structure specification file that states the rule.
    """
    return Note('the document structure is set here', at=Elsewhere(spec))
