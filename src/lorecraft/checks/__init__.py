"""Judge one revision: the rules engine the command line runs.

`lorecraft check` runs the engine: `runner` judges each document, skill, resource and layout entry by the rules of
`lorecraft.rules` a `RuleTable` from `table` enables, handing each rule the subject context `lorecraft.project.database`
answers from the queries, and reports each subject as `report` states, its diagnostics sorted by `diagnostic_order`.
Nothing here prints: the `check` command owns the output and the exit codes.
"""

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
from .runner import Subject, check_subjects
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
]
