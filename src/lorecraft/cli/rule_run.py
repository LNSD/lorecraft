"""The flow behind `lorecraft rule`: load the rules and print a rule's page from the rulebook, or list every rule.

It lives apart from `commands/rule.py` so that importing the command, which `--help` and `--version` do, does not
import the rules: the command imports this module only when it runs.
"""

import typer

from lorecraft import rules
from lorecraft.core.error import Error
from lorecraft.rules.registry import Registry

from .failure import report_failure
from .output import ExitStatus
from .rulebook import render_listing, render_page


class UnknownRuleError(Error):
    """No rule, removed rule or engine condition has the code, name or alias code typed.

    Attributes:
        key: What the user typed.
    """

    key: str

    def __init__(self, key: str) -> None:
        self.key = key
        super().__init__(f'no rule has the code, name or alias code {key!r}')


def run_rule(key: str | None) -> None:
    """Print the page of the rule `key` names, or the listing of every rule when `key` is `None`.

    Args:
        key: A rule's code, name or alias code, as typed.

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
    typer.echo(render_page(declaration), nl=False)
