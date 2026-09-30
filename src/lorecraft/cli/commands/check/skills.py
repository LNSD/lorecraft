"""The `check skills` command: validate the frontmatter of agent skills.

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
from lorecraft.core.error import Error

from . import app

SKILLS_CHECK: Final[SkillCheck] = register_skill_check(SkillCheck(name='skills', run=run_skills))


@app.command(name=SKILLS_CHECK.name)
def skills(
    paths: Annotated[
        list[Path] | None,
        typer.Argument(
            help=(
                'Skills to check, each by its directory or its SKILL.md, relative to the current directory. '
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
    """Check the frontmatter of each skill's SKILL.md against the Agent Skills specification.

    Exit 0 when clean, 1 when findings exist, and 2 for invalid input.

    Raises:
        typer.Exit: With the documented status code for findings or invalid input.
    """
    try:
        database, refs = select_skills(root, paths)
        run = SKILLS_CHECK.run(database, refs)
    except Error as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    except OSError as exc:
        # As in each document check command: what is left is Python 3.12's Path.is_dir, which re-raises a
        # PermissionError from find_root and resolve_root where 3.13 and later answer False.
        typer.echo(f'cannot read input: {exc}', err=True)
        raise typer.Exit(code=2) from exc

    print_skill_run(run, output_format)
    if run.findings():
        raise typer.Exit(code=1)
