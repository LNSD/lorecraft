"""Document checks: each validates one aspect of the documents a workspace model lists.

A check is pure over the one part of a document it reads: the header check over the frontmatter node. The
``Database`` caches the model, the frontmatter and the parse trees of one snapshot, and every check reads
through it, so each part is computed once whichever checks read it; ``run`` asks the database for the part the
check reads and hands only that to the check. Nothing here prints: the ``check`` commands own the output and
the exit codes.
"""

from .database import Database
from .header import HeaderCheckResult, validate_header
from .reporting import Finding, format_finding
from .run import CheckRun, DocumentReport, run_header

__all__ = [
    'Database',
    'Finding',
    'format_finding',
    'HeaderCheckResult',
    'validate_header',
    'DocumentReport',
    'CheckRun',
    'run_header',
]
