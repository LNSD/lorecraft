"""The `check` command: run every enabled rule over the whole workspace, and report what the rules found.

The command declares the options and the help text, and parses `--select` and `--ignore` against the rule index while
the command line is read. The flow is in `check_run`, which this module imports only when the command runs, so that
`--help` and `--version` never import the rules engine.
"""

from pathlib import Path
from typing import Annotated

import typer

from ..app import GlobalOptions
from ..output import ColorChoice, DiagnosticFormat
from ..registry import register
from ..rule_arguments import (
    EmptySelectorError,
    EngineSelectorError,
    MalformedSelectorError,
    RemovedRuleSelectorError,
    RuleNameSelectorError,
    SelectorValue,
    UnknownSelectorError,
)


def _parse_selectors(value: str) -> SelectorValue:
    """Parse one value of `--select` or `--ignore` while the command line is read.

    Args:
        value: The value as typed: one or more selectors separated by commas.

    Raises:
        typer.BadParameter: If the value is empty, malformed or names nothing a run could select or ignore, which
            Typer prints as a usage error naming the option.
    """
    try:
        return SelectorValue.parse(value)
    except (
        EmptySelectorError,
        MalformedSelectorError,
        UnknownSelectorError,
        RuleNameSelectorError,
        EngineSelectorError,
        RemovedRuleSelectorError,
    ) as exc:
        raise typer.BadParameter(str(exc)) from exc


@register('check')
def check(
    ctx: typer.Context,
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
        list[SelectorValue] | None,
        typer.Option(
            '--select',
            metavar='<selectors>',
            parser=_parse_selectors,
            help='Run only these rules: codes, code or group prefixes, or ALL, comma-separated or repeated. Defaults '
            'to ALL.',
        ),
    ] = None,
    ignore: Annotated[
        list[SelectorValue] | None,
        typer.Option(
            '--ignore',
            metavar='<selectors>',
            parser=_parse_selectors,
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

    Exit 0 when no diagnostic is an error, 1 when any is, such as a spec that failed to load, and 2 for invalid
    input or selectors, or when the root or `docs/__meta__/` cannot be listed.

    \f
    Raises:
        typer.Exit: With the documented status code for an error diagnostic or invalid input.
    """
    # Imported here, not at the top: `check_run` imports the rules engine, which `--help` and `--version` never use.
    from ..check_run import run_check

    options = ctx.find_root().obj
    assert isinstance(options, GlobalOptions), 'the root callback stores global options'
    status = run_check(
        root,
        output_format=output_format,
        color=color,
        select=select,
        ignore=ignore,
        builtin_skills_schema=options.builtin_skills_schema,
    )
    if status is not None:
        raise typer.Exit(code=status)
