"""Document checks: each validates one aspect of the documents a workspace model lists.

A check is pure over the one part of a document it reads: the frontmatter check over the frontmatter node, the
structure check over the headings, the budget check over the token count. The ``Database`` caches the model,
the frontmatter, the parse trees and the token counts of one snapshot, and every check reads through it, so each
part is computed once whichever checks read it; ``run`` asks the database for the part the check reads and hands
only that to the check. A check returns violations, which name no document; ``run`` files them under the
document's report, which locates them as findings. Nothing here prints: the ``check`` commands own the output
and the exit codes.
"""

from .budget import BudgetCheckResult, validate_budget
from .database import Database
from .frontmatter import FrontmatterCheckResult, validate_frontmatter
from .reporting import Finding, Violation, format_finding
from .run import CheckRun, DocumentReport, run_budget, run_frontmatter, run_structure
from .structure import StructureCheckResult, validate_structure

__all__ = [
    'Database',
    'Finding',
    'Violation',
    'format_finding',
    'FrontmatterCheckResult',
    'validate_frontmatter',
    'StructureCheckResult',
    'validate_structure',
    'BudgetCheckResult',
    'validate_budget',
    'DocumentReport',
    'CheckRun',
    'run_frontmatter',
    'run_structure',
    'run_budget',
]
