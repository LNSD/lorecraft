"""What a query reads and what it is: a pure function over the primitives of one item.

A query is a plain function from `Primitives` to the fact it derives, such as `title_constraints`. A rule declares the
queries it needs and a database memoizes each by the function and the item. The primitives are the only way a query
reaches the model, so what a query read is what its answer depends on: a database can keep the answer for the next
revision whenever every primitive it read is kept, and a query never reads the snapshot.
"""

from .primitives import (
    CorpusDirectoryPrimitives,
    CorpusDirectoryQuery,
    CountPrimitives,
    GovernancePrimitives,
    LinkResolutionPrimitives,
    Primitives,
    Query,
    SymlinkPrimitives,
    SymlinkQuery,
    SyntaxPrimitives,
)
from .structure_primitives import StructurePrimitives

__all__: list[str] = [
    'CorpusDirectoryPrimitives',
    'CorpusDirectoryQuery',
    'CountPrimitives',
    'GovernancePrimitives',
    'LinkResolutionPrimitives',
    'Primitives',
    'Query',
    'StructurePrimitives',
    'SymlinkPrimitives',
    'SymlinkQuery',
    'SyntaxPrimitives',
]
