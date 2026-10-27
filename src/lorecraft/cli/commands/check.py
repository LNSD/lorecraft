"""The `check` command: run every enabled rule over the whole workspace, and report what the rules found.

The command declares the options and the help text. The flow is in `check_run`, which this module imports only when
the command runs, so that `--help` and `--version` never import the rules engine.
"""

from pathlib import Path
from typing import Annotated

import typer

from lorecraft.core.error import Error
from lorecraft.rules.identity import Level

from ..app import global_options
from ..level_arguments import InvalidLevelArgumentError, LevelArgument, ParsedLevelArgument, validate_level_arguments
from ..output import ColorChoice, DiagnosticFormat
from ..registry import register


def _parse_level(value: str, level: Level) -> ParsedLevelArgument:
    """Parse one level value while the command line is read.

    Args:
        value: The selector supplied to the flag.
        level: The level the flag assigns.

    Raises:
        typer.BadParameter: If the selector is invalid for the flag.
    """
    try:
        return LevelArgument.parse(value, level)
    except InvalidLevelArgumentError as exc:
        raise typer.BadParameter(str(exc)) from exc


def _parse_allow(value: str) -> ParsedLevelArgument:
    """Parse one allow value.

    Args:
        value: The selector supplied to `-A`.
    """
    return _parse_level(value, Level.ALLOW)


def _parse_warn(value: str) -> ParsedLevelArgument:
    """Parse one warn value.

    Args:
        value: The selector supplied to `-W`.
    """
    return _parse_level(value, Level.WARN)


def _parse_deny(value: str) -> ParsedLevelArgument:
    """Parse one deny value.

    Args:
        value: The selector supplied to `-D`.
    """
    return _parse_level(value, Level.DENY)


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
    allow: Annotated[
        list[ParsedLevelArgument] | None,
        typer.Option(
            '-A',
            '--allow',
            metavar='<selector>',
            parser=_parse_allow,
            help='Allow this rule or ALL; repeatable, defaults to none.',
        ),
    ] = None,
    warn: Annotated[
        list[ParsedLevelArgument] | None,
        typer.Option(
            '-W',
            '--warn',
            metavar='<selector>',
            parser=_parse_warn,
            help='Warn on this rule or ALL; repeatable, defaults to none.',
        ),
    ] = None,
    deny: Annotated[
        list[ParsedLevelArgument] | None,
        typer.Option(
            '-D',
            '--deny',
            metavar='<selector>',
            parser=_parse_deny,
            help='Deny this rule, ALL, or warnings; repeatable, defaults to none.',
        ),
    ] = None,
) -> None:
    """Check every document and skill of the workspace: frontmatter, outline, length, links and layout.

    As text, each diagnostic is drawn on stdout with its source lines, labels, help and notes, coloured on a terminal.

    As short, each diagnostic is one uncoloured line on stdout: its path and line, severity, code and message.

    The ungoverned subjects and a summary go to stderr, with the errors and warnings per code prefix as text.

    As JSON, one compact document goes to stdout.

    Level flags accept active rule codes, alias codes or ALL; -D also accepts warnings. They apply levels to the
    rule table, where a specific code overrides ALL. They reject conflicting assignments and are validated before
    the workspace is checked. -D warnings elevates resolved warnings to errors.

    Exit 0 when no diagnostic is an error, 1 when any is, such as a spec that failed to load, and 2 for invalid
    input, or when the root or `docs/__meta__/` cannot be listed.

    \f
    Raises:
        typer.BadParameter: If the level selectors conflict.
        typer.Exit: With the documented status code for an error diagnostic or invalid input.
        RuntimeError: If rule registration fails or the generated index does not match the registry.
    """
    level_arguments = (*(allow or ()), *(warn or ()), *(deny or ()))
    try:
        validate_level_arguments(level_arguments)
    except Error as exc:
        raise typer.BadParameter(str(exc), param_hint="'-A' / '-W' / '-D'") from exc

    # Imported here, not at the top: `check_run` imports the rules engine, which `--help` and `--version` never use.
    from ..check_run import run_check

    options = global_options(ctx)
    status = run_check(
        root,
        output_format=output_format,
        color=color,
        builtin_layers=options.builtin_layers,
        level_arguments=level_arguments,
    )
    if status is not None:
        raise typer.Exit(code=status)
