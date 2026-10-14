"""Where a node of a parse tree sits in its document: a one-based line number."""

from typing import NewType

from lorecraft.core.num import NonZeroUnsignedInt

LineNumber = NewType('LineNumber', NonZeroUnsignedInt)
"""A one-based line number in a document: 1 is the first line, never taken for another count."""
