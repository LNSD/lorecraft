"""What a query reads and what it is: a pure function over the primitives of one item.

A query is a plain function from `Primitives` to the fact it derives, such as a document's title facts. A rule declares
the queries it needs and a database memoizes each by the function and the item. The primitives are the only way a query
reaches the model, so what a query read is what its answer depends on: a database can keep the answer for the next
revision whenever every primitive it read is kept, and a query never reads the snapshot.
"""

from .linked_paths import linked_paths
from .primitives import (
    CorpusDirectoryPrimitives,
    CorpusDirectoryQuery,
    CountPrimitives,
    GovernancePrimitives,
    ItemReads,
    LinkResolutionPrimitives,
    Primitives,
    Query,
    QueryPrimitives,
    SchemaPrimitives,
    SchemaQuery,
    SchemaReads,
    SubjectQuery,
    SubjectRef,
    SymlinkPrimitives,
    SymlinkQuery,
    SyntaxPrimitives,
    TitlePrimitives,
)

__all__: list[str] = [
    'CorpusDirectoryPrimitives',
    'CorpusDirectoryQuery',
    'CountPrimitives',
    'GovernancePrimitives',
    'ItemReads',
    'LinkResolutionPrimitives',
    'Primitives',
    'SchemaPrimitives',
    'SchemaReads',
    'SchemaQuery',
    'Query',
    'QueryPrimitives',
    'SubjectQuery',
    'SubjectRef',
    'SymlinkPrimitives',
    'SymlinkQuery',
    'SyntaxPrimitives',
    'TitlePrimitives',
    'linked_paths',
]
