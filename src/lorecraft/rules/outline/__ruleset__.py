"""What the `LC3xx` group's rules share: the group, and the notes naming a spec and giving an example.

A document's sections are governed by every structure file that governs the document, each on its own: a
document governed by a corpus and a namespace spec is reported once for each one it breaks. Every rule of
the group says which spec an occurrence breaks through `spec_note`, so two occurrences from two
specs read apart.

The title is the exception: no spec states it, since every governed document carries exactly one H1 title
that opens it. A rule over its being there reports a document once, with `spec` `None` and no note pointing at a
spec. A pattern a spec sets on the title is that spec's own, so a title
failing it is reported once per spec setting it, as a section is.

The rules over the headings are governed by `SpecPart.STRUCTURE`, so they judge every document whose corpus states a
structure file; the rules over where the sections stop matching an outline are governed by `SpecPart.OUTLINE`,
so they judge only a document some outline governs.
"""

from typing import Final

from lorecraft.rules.identity import RuleGroup, RuleGroupPrefix

GROUP_ID: Final[RuleGroup] = RuleGroup(RuleGroupPrefix('LC'), 'Outline checks', range(300, 310))
"""The group of the rules over a document's sections, as a structure file states them, and over its H1
title, which every governed document carries without a key stating it."""
