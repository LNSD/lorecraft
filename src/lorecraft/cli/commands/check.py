"""The `check` command: run every enabled rule over the whole workspace, and report what the rules found.

The command declares the options and the help text; the flow is in `check_run`, which this module imports only when
the command runs, so that `--help` and `--version` never import the rules engine.
"""

from pathlib import Path
from typing import Annotated

import typer

from ..output import ColorChoice, DiagnosticFormat
from ..registry import register


@register('check')
def check(
    root: Annotated[
        Path | None,
        typer.Option('--root', help='Repository root. Defaults to the nearest parent containing docs/__meta__.'),
    ] = None,
    output_format: Annotated[
        DiagnosticFormat,
        typer.Option(
            '--format',
            help='Output format: text draws each diagnostic in full, short prints one line each, json prints one '
            'document.',
        ),
    ] = DiagnosticFormat.TEXT,
    color: Annotated[
        ColorChoice,
        typer.Option(
            '--color',
            metavar='<WHEN>',
            help='Control when colored output is used.\n\n'
            'auto: colour when stdout is an interactive terminal, unless NO_COLOR is set; FORCE_COLOR forces it.\n\n'
            'always: colour even when stdout is not a terminal.\n\n'
            'never: no colour.\n\n'
            'Only the text format is coloured.',
        ),
    ] = ColorChoice.AUTO,
    select: Annotated[
        list[str] | None,
        typer.Option(
            '--select',
            metavar='<selectors>',
            help='Run only these rules: codes, code or group prefixes, or ALL, comma-separated or repeated. Defaults '
            'to ALL.',
        ),
    ] = None,
    ignore: Annotated[
        list[str] | None,
        typer.Option(
            '--ignore',
            metavar='<selectors>',
            help='Skip these rules, unless a more specific selector selects them: codes, code or group prefixes, or '
            'ALL, comma-separated or repeated. Defaults to none.',
        ),
    ] = None,
) -> None:
    """Check every document and skill of the workspace: frontmatter, outline, length, links and layout.

    As text, each diagnostic is drawn on stdout with its source lines, labels, help and notes, coloured on a terminal.

    As short, each diagnostic is one uncoloured line on stdout: its path and line, severity, code and message.

    The ungoverned subjects and a summary go to stderr, with the errors and warnings per code prefix as text.

    As JSON, one compact document goes to stdout.

    --select never enables a rule its level leaves off; each such rule, and each alias code, is warned of on stderr.

    Exit 0 when no diagnostic is an error, 1 when any is, and 2 for invalid input, specifications or selectors.

    \f
    Raises:
        typer.Exit: With the documented status code for an error diagnostic or invalid input.
    """
    # Imported here, not at the top: `check_run` imports the rules engine, which `--help` and `--version` never use.
    from ..check_run import run_check

    run_check(root, output_format, color, select, ignore)
