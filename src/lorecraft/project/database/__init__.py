"""The database of one revision: the memoized queries over a snapshot, and its typed read records.

`Database` wraps one snapshot and memoizes every value derived from it, each computed by the rest of this package:
the model, the decoded text, the frontmatter, the parse trees, the counts and the shared analyses. Its decode queries
return a witness of a file's text, `ItemText`, or an `Undecodable` marker, and every per-file query takes the witness.
"""

from .database import Database, Read
from .text import ItemText, Undecodable

__all__: list[str] = [
    'Database',
    'Read',
    'ItemText',
    'Undecodable',
]
