"""Document checks: each validates one aspect of the documents a workspace model lists.

A check is pure over the parse tree it is handed. The ``Database`` caches the model and the parse trees of one
snapshot, and every check reads through it, so a document is parsed once whichever checks read it; ``run``
hands each governed document's parse tree to the check. Nothing here prints: the ``check`` commands own the
output and the exit codes.
"""

from .database import Database
from .header import HeaderCheckResult, validate_header
from .reporting import Finding, format_finding
from .run import HeaderReport, HeaderRun, run_header

__all__ = [
    'Database',
    'Finding',
    'format_finding',
    'HeaderCheckResult',
    'validate_header',
    'HeaderReport',
    'HeaderRun',
    'run_header',
]
