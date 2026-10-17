"""The database of one revision: the memoized queries over a snapshot, and what they hand out.

`Database` wraps one snapshot and memoizes every value derived from it, each computed by the rest of this package:
the model, the decoded text, the frontmatter, the parse trees, the counts and the shared analyses. Its decode queries
return a witness of a file's text, `ItemText`, or an `Undecodable` marker, and every per-file query takes the witness.
`DatabaseItemContext` answers the contexts of `lorecraft.project.context` from those queries, for one decoded
document, skill entry or skill resource, and `DatabaseSymlinkContext` from the record of one symlink of the skill layout
whose chain leaves the repository.
"""

from .context import (
    DatabaseItemContext,
    DatabaseSymlinkContext,
)
from .database import Database
from .text import ItemText, Undecodable

__all__: list[str] = [
    'Database',
    'ItemText',
    'Undecodable',
    'DatabaseItemContext',
    'DatabaseSymlinkContext',
]
