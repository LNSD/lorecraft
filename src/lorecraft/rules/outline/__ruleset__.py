"""What the `OUT` group's rules share: the group, and the notes naming a meta spec and giving an example.

A document's sections are governed by every structure file that governs the document, each on its own: a
document governed by a corpus and a namespace meta spec is reported once for each one it breaks. Every rule of
the group says which meta spec an occurrence breaks through `spec_note`, so two occurrences from two
meta specs read apart.

The title is the exception: no meta spec states it, since every governed document carries exactly one H1 title
that opens it. A rule over its being there reports a document once, with `spec` `None` and no note pointing at a
meta spec. A pattern a meta spec sets on the title is that meta spec's own, so a title
failing it is reported once per meta spec setting it, as a section is.

The rules over the headings are governed by `Facet.STRUCTURE`, so they judge every document whose corpus states a
structure file; the rules over where the sections stop matching an outline are governed by `Facet.OUTLINE`,
so they judge only a document some outline governs.
"""

from typing import Final

from lorecraft.core.path import RootRelativePath
from lorecraft.project.schemas import SectionName
from lorecraft.rules.identity import RuleGroup, RuleGroupPrefix
from lorecraft.rules.location import Elsewhere, Note

GROUP_ID: Final[RuleGroup] = RuleGroup(RuleGroupPrefix('OUT'), 'Outline checks')
"""The group of the rules over a document's sections, as a structure file states them, and over its H1
title, which every governed document carries without a key stating it."""


def spec_note(spec: RootRelativePath) -> Note:
    """The note pointing at the structure file that states the rule an occurrence breaks.

    Args:
        spec: The structure file that states the rule.
    """
    return Note('the document structure is set here', at=Elsewhere(spec))


def example_note(section: SectionName, example: str) -> Note:
    """The note giving a section's example, written under the section's heading as a document would write it.

    The example is the outline entry's, printed as the meta spec wrote it.

    Args:
        section: The name the outline entry gives the section the example is for.
        example: The sample of the section's body, without its heading.
    """
    return Note(f'for example:\n## {section}\n\n{example}')
