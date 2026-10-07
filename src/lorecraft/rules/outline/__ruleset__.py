"""What the `OUT` group's rules share: the group, and the note naming the specification that states a rule.

A document's sections are governed by every structure specification that governs the document, each on its own: a
document governed by a corpus and a namespace specification is reported once for each one it breaks. Every rule of
the group says which specification an occurrence breaks through `spec_note`, so two occurrences from two
specifications read apart.

The title is the exception: no specification states it, since every governed document carries exactly one H1 title
that opens it. A rule over its being there reports a document once, under its corpus's structure specification. A
pattern a specification sets on the title is that specification's own, so a title failing it is reported once per
specification setting it, as a section is.

The rules over the headings are governed by `Facet.STRUCTURE`, so they judge every document whose corpus states a
structure specification; the rules over where the sections stop matching an outline are governed by `Facet.OUTLINE`,
so they judge only a document some outline governs.
"""

from typing import Final

from lorecraft.core.path import RootRelativePath
from lorecraft.rules.declaration import RuleGroup, RuleGroupPrefix
from lorecraft.rules.location import Elsewhere, Note

GROUP_ID: Final[RuleGroup] = RuleGroup(RuleGroupPrefix('OUT'), 'Outline checks')
"""The group of the rules over a document's sections, as a structure specification states them, and over its H1
title, which every governed document carries without a key stating it."""


def spec_note(spec: RootRelativePath) -> Note:
    """The note pointing at the structure specification that states the rule an occurrence breaks.

    Args:
        spec: The structure specification file that states the rule.
    """
    return Note('the document structure is set here', at=Elsewhere(spec))
