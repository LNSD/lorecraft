"""Run the rules over one revision: the runner the command line calls.

`lorecraft check` calls `check_subjects`, which judges each document, skill, resource and layout entry by the rules of
`lorecraft.rules` that a `RuleTable` enables, handing each rule the subject context `lorecraft.project.database`
answers from the queries. The table, the selection that narrows it and the report each subject gets are
`lorecraft.rules.table`, `lorecraft.rules.selection` and `lorecraft.rules.report`.
Nothing here prints: the `check` command owns the output and the exit codes.
"""

from .runner import Subject, check_subjects

__all__: list[str] = [
    'Subject',
    'check_subjects',
]
