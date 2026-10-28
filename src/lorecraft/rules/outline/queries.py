"""Queries and notes used by rules over document outlines: spec notes, examples and outline divergences."""

from lorecraft.core.path import RootRelativePath
from lorecraft.project.query import ItemPrimitives, item_line_count
from lorecraft.project.schemas import OutlineDivergenceSpec, SectionName, match_outlines, outline_alignment
from lorecraft.rules.location import Elsewhere, Note


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
