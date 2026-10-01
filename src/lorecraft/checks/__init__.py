"""Document and skill checks: each validates one aspect of the documents, or the skills, a workspace model lists.

A check is pure over the one part of a document it reads: the frontmatter check over the frontmatter node, the
structure check over the headings, the budget check over the token count. The `Database` caches the model, the
frontmatter, the parse trees and the token counts of one snapshot, and every check reads through it, so each part is
computed once whichever checks read it; `run` asks the database for the part the check reads and hands only that to
the check. The skill check reads the frontmatter of each `SKILL.md` the same way, and holds it to the Agent Skills
specification rather than to a corpus specification; the skill length check reads its line count; the skill link
check reads the links of its parse tree, and of the parse tree of each of the skill's resources, with what the
snapshot holds at each path inside the skill they name, and the skill metadata check the paths a skill that links
files in through `metadata` lists there, with what the snapshot holds at each. A check returns violations, which
name no document; `run` files them under the document's report, or the skill's, or the resource's, which locates
them as findings. Nothing here prints: the `check` commands own the output and the exit codes.
"""

from .budget import BudgetCheckResult, validate_budget
from .database import Database
from .frontmatter import FrontmatterCheckResult, validate_frontmatter
from .reporting import Finding, Note, NoteKind, Violation, format_finding
from .run import (
    CheckRun,
    DocumentReport,
    SkillCheckRun,
    SkillReport,
    SkillResourceReport,
    run_budget,
    run_frontmatter,
    run_skills,
    run_structure,
)
from .skill import SkillCheckResult, validate_skill
from .structure import StructureCheckResult, validate_structure

__all__ = [
    'Database',
    'Finding',
    'Violation',
    'Note',
    'NoteKind',
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
    'SkillCheckResult',
    'validate_skill',
    'SkillReport',
    'SkillResourceReport',
    'SkillCheckRun',
    'run_skills',
]
