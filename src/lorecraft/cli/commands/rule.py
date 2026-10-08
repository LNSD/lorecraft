"""The `rule` subcommand: print a rule's page from the rulebook, or list every rule.

The rules are package data, so the command reads no workspace and needs no root: it loads the registry and prints
what `cli.rulebook` renders from it, the same page `docs/rulebook/` holds.
"""

from typing import Annotated

import typer

from lorecraft import rules
from lorecraft.core.error import Error
from lorecraft.rules.registry import Registry

from ..failure import report_failure
from ..output import ExitStatus
from ..registry import register
from ..rulebook import render_listing, render_page


class UnknownRuleError(Error):
    """No rule, removed rule or engine condition has the code, name or alias code typed.

    Attributes:
        key: What the user typed.
    """

    key: str

    def __init__(self, key: str) -> None:
        self.key = key
        super().__init__(f'no rule has the code, name or alias code {key!r}')


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
    registry = Registry.load(rules)
    if key is None:
        typer.echo(render_listing(registry))
        return

    declaration = registry.find(key)
    if declaration is None:
        report_failure(UnknownRuleError(key))
        raise typer.Exit(code=ExitStatus.FAILURE)
    typer.echo(render_page(declaration, registry), nl=False)
