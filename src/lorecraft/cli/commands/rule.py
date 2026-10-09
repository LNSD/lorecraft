"""The `rule` subcommand: print a rule's page from the rulebook, or list every rule.

The rules are package data, so the command reads no workspace and needs no root. The command declares the argument
and the help text; the flow is in `rule_run`, which this module imports only when the command runs, so that
`--help` and `--version` never import the rules.
"""

from typing import Annotated

import typer

from ..registry import register


@register('rule')
def rule(
    key: Annotated[
        str | None,
        typer.Argument(
            metavar='[RULE]',
            help='A rule by its code, its name or an alias code, such as OUT004 or empty-section. Without it, every '
            'rule is listed.',
        ),
    ] = None,
) -> None:
    """Show a rule's page from the rulebook, or list every rule in code order.

    A page says what the rule checks and why, an example and the fix.

    The listing shows the code, name, default level and condition of each rule.

    A removed rule shows `removed` as its level, an engine condition `error`.

    Exit 0 when the page or the listing is printed, and 2 when no rule has the code, name or alias code, or for
    invalid input.

    \f
    Raises:
        typer.Exit: With code 2 when no rule has the code, name or alias code.
    """
    # Imported here, not at the top: `rule_run` imports the rules, which `--help` and `--version` never use.
    from ..rule_run import run_rule

    run_rule(key)
