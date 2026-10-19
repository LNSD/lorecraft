"""What a query reads and what it is: a pure function over the primitives of one subject.

A query is a plain function from `ItemPrimitives` to the value it derives, such as a document's title. A rule declares
the queries it needs and a database memoizes each by the function and the item. The primitives are the only way a query
reaches the model, so what a query read is what its answer depends on: a database can keep the answer for the next
revision whenever every primitive it read is kept, and a query never reads the snapshot.
"""

from .item_facts import (
    item_base,
    item_corpus,
    item_frontmatter,
    item_line_count,
    item_name,
    item_parse,
    item_structure_specs,
    item_token_count,
)
from .linked_paths import linked_paths
from .primitives import (
    CorpusDirectoryPrimitives,
    CorpusDirectoryQuery,
    CountPrimitives,
    DecodedText,
    GovernancePrimitives,
    ItemPrimitives,
    ItemQuery,
    LinkResolutionPrimitives,
    NameHierarchyPrimitives,
    Query,
    QueryPrimitives,
    QueryTargetRef,
    SchemaPrimitives,
    SchemaQuery,
    SubjectQuery,
    SymlinkPrimitives,
    SymlinkQuery,
    SyntaxPrimitives,
    TitlePrimitives,
)

__all__: list[str] = [
    'CorpusDirectoryPrimitives',
    'CorpusDirectoryQuery',
    'CountPrimitives',
    'DecodedText',
    'GovernancePrimitives',
    'ItemQuery',
    'LinkResolutionPrimitives',
    'NameHierarchyPrimitives',
    'ItemPrimitives',
    'Query',
    'QueryPrimitives',
    'SchemaPrimitives',
    'SchemaQuery',
    'SubjectQuery',
    'QueryTargetRef',
    'SymlinkQuery',
    'SymlinkPrimitives',
    'SyntaxPrimitives',
    'TitlePrimitives',
    'linked_paths',
    'item_corpus',
    'item_base',
    'item_frontmatter',
    'item_line_count',
    'item_name',
    'item_parse',
    'item_structure_specs',
    'item_token_count',
]
