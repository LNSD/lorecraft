"""The database of one revision: the memoized queries over a snapshot, and what they hand out.

`Database` wraps one snapshot and memoizes every value derived from it, each computed by the rest of this package:
the model, the decoded text, the frontmatter, the parse trees, the counts and the shared analyses. Its decode queries
return a witness of a file's text, `DocumentText`, `SkillText` or `SkillResourceText`, or an `Undecodable` marker,
and every per-file query takes the witness. `DatabaseDocumentContext`, `DatabaseSkillContext` and
`DatabaseSkillResourceContext` answer the contexts of `lorecraft.project.context` from those queries, for one
decoded subject, and `DatabaseLayoutContext` from the record of one symlink of the skill layout whose chain leaves
the repository.
"""

from .context import DatabaseDocumentContext, DatabaseLayoutContext, DatabaseSkillContext, DatabaseSkillResourceContext
from .database import Database
from .text import DocumentText, SkillResourceText, SkillText, Undecodable

__all__: list[str] = [
    'Database',
    'DocumentText',
    'SkillText',
    'SkillResourceText',
    'Undecodable',
    'DatabaseDocumentContext',
    'DatabaseSkillContext',
    'DatabaseSkillResourceContext',
    'DatabaseLayoutContext',
]
