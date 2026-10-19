"""The outline alignment as a query: where a document's sections fall in each outline.

It is shared by the rules over a document's outline and by the divergences the outline rules read, so it lives with the
model rather than with one rule.
"""

from typing import TYPE_CHECKING

from lorecraft.project.query import item_parse, item_structure_specs

from .outline_alignment import OutlineAlignmentSpec, align_outlines

if TYPE_CHECKING:
    # Type-only: `lorecraft.project.query` imports this package, so a runtime import here would be a cycle.
    from lorecraft.project.query import Primitives


def outline_alignment(primitives: Primitives) -> tuple[OutlineAlignmentSpec, ...]:
    """Which outline entry each of the document's H2 sections falls in, for each specification that governs it.

    One entry per structure specification that governs the document, in the order the specifications apply, one that
    states no outline included: it aligns each section to nothing. A query: it reads the structure specifications and,
    when one governs the document, the headings. Raises nothing.

    Args:
        primitives: The model state of the document.
    """
    specs = primitives.query(item_structure_specs)
    return align_outlines(specs, primitives.query(item_parse).headings) if specs else ()
