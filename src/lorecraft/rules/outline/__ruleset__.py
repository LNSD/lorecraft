"""What the `OUT` group's rules share: the group, and the notes naming a spec and giving an example.

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

from lorecraft.core.path import RootRelativePath
from lorecraft.project.query import ItemPrimitives, item_line_count
from lorecraft.project.schemas import OutlineDivergenceSpec, SectionName, match_outlines, outline_alignment
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

    The example is the outline entry's, printed as the spec wrote it.

    Args:
        section: The name the outline entry gives the section the example is for.
        example: The sample of the section's body, without its heading.
    """
    return Note(f'for example:\n## {section}\n\n{example}')


def outline_divergences(primitives: ItemPrimitives) -> tuple[OutlineDivergenceSpec, ...]:
    """Where the document's sections first stop matching each outline that governs it.

    One entry per structure specification that governs the document and states an outline, in the order the
    specifications apply; none when no outline governs it. A query: it reads what `outline_alignment` does and, only
    when an outline is stated, the line count. Raises nothing.

    Args:
        primitives: The model state of the document.
    """
    alignments = primitives.query(outline_alignment)
    if any(alignment.outline for alignment in alignments):
        return match_outlines(alignments, primitives.query(item_line_count))
    return ()
