"""The `check` command group: one subcommand per check, over documents or over skills, each in its own module here.

Importing this package registers the group and imports every module beside this one, so each check joins
the group the same way a top-level command joins the root: by being a file in the package. Each check module
also registers its check, and a bare ``lorecraft check`` runs every registered one over one snapshot, so a new
check joins that run without this module naming it.
"""

import importlib
import pkgutil
from pathlib import Path
from typing import Annotated, Literal

import typer

from lorecraft.checks import CheckRun, SkillCheckRun
from lorecraft.cli.check_run import (
    DocumentCheck,
    SkillCheck,
    print_runs,
    registered_checks,
    registered_skill_checks,
    select_documents,
)
from lorecraft.cli.failure import report_failure
from lorecraft.cli.registry import register_group
from lorecraft.cli.select import select_whole
from lorecraft.core.error import Error

app: typer.Typer = typer.Typer(
    help='Run the documentation and skill checks: every check when no check is named, or the one named.',
    invoke_without_command=True,
)
register_group('check', app)

__all__ = ['app']


@app.callback()
def check_all(
    context: typer.Context,
    root: Annotated[
        Path | None,
        typer.Option('--root', help='Repository root. Defaults to the nearest parent containing docs/__meta__.'),
    ] = None,
    output_format: Annotated[
        Literal['text', 'json'] | None,
        typer.Option('--format', help='Output format: text or json. Defaults to text.'),
    ] = None,
) -> None:
    """Run every check, over every document and every skill, when no check is named.

    Each check reads the same snapshot, through one database, so a document is read and parsed once however
    many checks read it. Exit 0 when clean, 1 when any check finds something, and 2 for invalid input or
    specifications; after an error nothing is printed but the error.

    Raises:
        typer.BadParameter: If ``--root`` or ``--format`` is given before a named check, which takes its own.
        typer.Exit: With the documented status code for findings or invalid input.
    """
    if context.invoked_subcommand is not None:
        # The options belong to the bare run. Before a check's name they would be read and then ignored, so
        # they are refused rather than dropped: the check takes its own `--root` and `--format`. Both default to
        # `None` for this reason alone, so that a given option can be told from an absent one.
        if root is not None or output_format is not None:
            raise typer.BadParameter(
                f'give it after the check name, as `lorecraft check {context.invoked_subcommand} --root ...`',
                param_hint="'--root' / '--format'",
            )
        return

    try:
        database, refs = select_documents(root, None)
        runs: list[tuple[DocumentCheck, CheckRun]] = []
        for check in registered_checks():
            runs.append((check, check.run(database, refs)))
        skill_selections = select_whole(database.model().skills())
        skill_runs: list[tuple[SkillCheck, SkillCheckRun]] = []
        for skill_check in registered_skill_checks():
            skill_runs.append((skill_check, skill_check.run(database, skill_selections)))
    except Error as exc:
        report_failure(exc)
        raise typer.Exit(code=2) from exc

    print_runs(tuple(runs), tuple(skill_runs), output_format or 'text')
    for _check, run in runs:
        if run.findings():
            raise typer.Exit(code=1)
    for _skill_check, skill_run in skill_runs:
        if skill_run.findings():
            raise typer.Exit(code=1)


# Each check lives in its own module and joins this group when imported. The group must exist before the
# imports, because every check module attaches its command to `app`.
for module_info in pkgutil.iter_modules(__path__):
    importlib.import_module(f'{__name__}.{module_info.name}')
