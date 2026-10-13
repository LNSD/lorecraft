"""Run the rules over one revision: the engine the command line calls.

`lorecraft check` calls `check_subjects`, which judges each document, skill, resource and layout entry by the rules of
`lorecraft.rules` that a `RuleTable` enables, handing each rule the subject context `lorecraft.project.database`
answers from the queries, and `report_load_failures`, which reports each unit of the declaration that failed to load
at its own path, or returns the `UnlistableRoot` when `docs/` or `docs/__meta__/` cannot be listed, for the command
to stop on. The table, the selection that narrows it and the report each subject gets are
`lorecraft.rules.table`, `lorecraft.rules.selection` and `lorecraft.rules.report`.
What the modes share is `lorecraft.engine.runner` and the load failures' reports; each mode's policy for a document
a failed layer governs is an entry point of its own, `skip` for the check run.
Nothing here prints, and nothing here imports the command line or its toolkit: the `check` command owns the output
and the exit codes.
"""

from .load_failures import LoadFailureReports, UnlistableRoot, report_load_failures
from .runner import Subject
from .skip import check_subjects

__all__: list[str] = [
    'LoadFailureReports',
    'Subject',
    'UnlistableRoot',
    'check_subjects',
    'report_load_failures',
]
