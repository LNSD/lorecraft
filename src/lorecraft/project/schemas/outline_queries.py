"""The outline alignment as a query: where a document's sections fall in each outline.

It is shared by the rules over a document's outline, so it lives with the model rather than with one rule.
"""

from .outline_alignment import OutlineAlignmentSpec, align_outlines
from .query import Primitives


def outline_alignment(primitives: Primitives) -> tuple[OutlineAlignmentSpec, ...]:
    """Which outline entry each of the document's H2 sections falls in, for each specification that governs it.

    One entry per structure specification that governs the document, in the order the specifications apply, one that
    states no outline included: it aligns each section to nothing. A query: it reads the structure specifications and,
    when one governs the document, the headings. Raises nothing.

    Args:
        primitives: The model state of the document.
    """
    specs = primitives.structure_specs()
    return align_outlines(specs, primitives.headings()) if specs else ()
