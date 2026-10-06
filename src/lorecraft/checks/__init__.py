"""Judge one revision: the rules engine the command line runs, and the per-check pipelines it replaced.

The rules engine is what `lorecraft check` runs: `runner` judges each document, skill, resource and layout entry by
the rules of `lorecraft.rules` a `RuleTable` enables, handing each rule the subject context
`lorecraft.project.database` answers from the queries, and reports each subject as `report` states, its diagnostics
sorted by `diagnostic_order`. Nothing here prints: the `check` command owns the output and the exit codes.

The per-check pipelines below it are no longer run by the command line, and stay only until they are deleted. A check
there is pure over the one part of a document it reads: the frontmatter check over the frontmatter node, the
structure check over the headings, the budget check over the token count. The `Database` of
`lorecraft.project.database` caches the model, the decoded text, the frontmatter, the parse trees and the token
counts of one snapshot, and every check reads through it, so each part is computed once whichever checks read it;
`run` asks the database to decode each file once, as a witness of its text or an `Undecodable` marker, then for the
part the check reads, and hands only that to the check. The skill check reads the frontmatter of each `SKILL.md` the
same way, and holds it to the Agent Skills specification rather than to a corpus specification; the skill length
check reads its line count; the skill link check reads the links of its parse tree, and, for a skill selected whole,
of the parse tree of each of the skill's resources, with what the snapshot holds at each path inside the skill they
name. A check returns violations, which name no document; `run` files them under the document's report, or the
skill's, or the resource's, which locates them as findings.
"""

from .budget import BudgetCheckResult, validate_budget
from .frontmatter import FrontmatterCheckResult, validate_frontmatter
from .report import (
    CheckedLayoutEntry,
    CheckedSubject,
    Diagnostic,
    DiagnosticOrder,
    EngineDiagnostic,
    RuleDiagnostic,
    SubjectRef,
    SubjectReport,
    UndecodableSubject,
    diagnostic_order,
)
from .reporting import Finding, Note, NoteKind, Violation, format_finding
from .run import (
    CheckRun,
    DocumentReport,
    GovernedDocumentReport,
    SkillCheckRun,
    SkillReport,
    SkillResourceReport,
    SkillScope,
    SkillSelection,
    SymlinkReport,
    UngovernedDocumentReport,
    run_budget,
    run_frontmatter,
    run_skills,
    run_structure,
)
from .runner import Subject, check_subjects
from .skill import SkillCheckResult, validate_skill
from .structure import StructureCheckResult, validate_structure
from .table import EnabledRule, RuleTable, UnknownRuleBaseError

__all__: list[str] = [
    'Subject',
    'check_subjects',
    'RuleTable',
    'EnabledRule',
    'UnknownRuleBaseError',
    'RuleDiagnostic',
    'EngineDiagnostic',
    'Diagnostic',
    'DiagnosticOrder',
    'diagnostic_order',
    'SubjectRef',
    'CheckedSubject',
    'UndecodableSubject',
    'CheckedLayoutEntry',
    'SubjectReport',
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
    'GovernedDocumentReport',
    'UngovernedDocumentReport',
    'CheckRun',
    'run_frontmatter',
    'run_structure',
    'run_budget',
    'SkillCheckResult',
    'validate_skill',
    'SkillReport',
    'SkillResourceReport',
    'SymlinkReport',
    'SkillCheckRun',
    'SkillScope',
    'SkillSelection',
    'run_skills',
]
