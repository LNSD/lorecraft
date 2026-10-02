"""The `check skills` command: validate agent skills against the Agent Skills specification.

This is the composition root of the skill check: it selects the skills of one snapshot, hands them to
``run_skills``, and prints the run. Every ``Error`` escaping that flow is reported here and exits 2; a
``SKILL.md`` that cannot be decoded is a finding, not an error. The module also registers the check, so a bare
``lorecraft check`` runs it too.
"""

from pathlib import Path
from typing import Annotated, Final, Literal

import typer

from lorecraft.checks import run_skills
from lorecraft.cli.check_run import SkillCheck, print_skill_run, register_skill_check, select_skills
from lorecraft.cli.failure import report_failure
from lorecraft.core.error import Error

from . import app

SKILLS_CHECK: Final[SkillCheck] = register_skill_check(SkillCheck(name='skills', run=run_skills))


@app.command(name=SKILLS_CHECK.name)
def skills(
    paths: Annotated[
        list[Path] | None,
        typer.Argument(
            help=(
                'Skills to check, each by a skill directory, a directory of skills, or a SKILL.md, relative to the '
                'current directory; a SKILL.md checks that file alone. '
                "Defaults to every skill in the agents' skills directories under ROOT."
            )
        ),
    ] = None,
    root: Annotated[
        Path | None,
        typer.Option('--root', help='Repository root. Defaults to the nearest parent containing docs/__meta__.'),
    ] = None,
    output_format: Annotated[
        Literal['text', 'json'],
        typer.Option('--format', help='Output format: text or json.'),
    ] = 'text',
) -> None:
    """Check each skill against the Agent Skills specification: its SKILL.md and its other Markdown files.

    A skill named by its SKILL.md has that file checked alone.

    Exit 0 when clean, 1 when findings exist, and 2 for invalid input.

    Raises:
        typer.Exit: With the documented status code for findings or invalid input.
    """
    try:
        database, selections = select_skills(root, paths)
        run = SKILLS_CHECK.run(database, selections)
    except Error as exc:
        report_failure(exc)
        raise typer.Exit(code=2) from exc

    print_skill_run(run, output_format)
    if run.findings():
        raise typer.Exit(code=1)
