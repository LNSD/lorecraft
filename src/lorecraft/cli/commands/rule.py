"""The `rule` subcommand: print a rule's page from the rulebook, or list every rule.

The rules are package data, so the command reads no workspace and needs no root: it loads the registry and prints
what `cli.rulebook` renders from it, the same page `docs/rulebook/` holds.
"""

from typing import Annotated

import typer

from lorecraft import rules
from lorecraft.core.error import Error
from lorecraft.rules.registry import Registry

from ..registry import register
from ..rule_arguments import RuleKey
from ..rulebook import render_listing, render_page


class _RuleKeyParser:
    """Parse the argument of `rule` while the command line is read.

    Typer prints the parser's `__name__` as the argument's type in `--help`, where a plain function would print its
    own name. The argument was a `str` before it was parsed, and its help is unchanged, so this is named `str`.
    """

    __name__ = 'str'

    def __call__(self, text: str) -> RuleKey:
        """Parse the argument into a rule key.

        Args:
            text: The argument as typed.

        Raises:
            typer.BadParameter: If the argument is malformed or names no rule, which Typer prints as a usage error.
        """
        try:
            return RuleKey.parse(text)
        except Error as exc:
            raise typer.BadParameter(str(exc)) from exc


@register('rule')
def rule(
    key: Annotated[
        RuleKey | None,
        typer.Argument(
            metavar='[RULE]',
            parser=_RuleKeyParser(),
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
    """
    registry = Registry.load(rules)
    if key is None:
        typer.echo(render_listing(registry))
        return

    typer.echo(render_page(key.to_declaration(registry)), nl=False)
