"""The flow behind `lorecraft rule`: load the rules and print a rule's page from the rulebook, or list every rule.

It lives apart from `commands/rule.py` so that importing the command, which `--help` and `--version` do, does not
import the rules: the command imports this module only when it runs.
"""

import typer

from lorecraft import rules
from lorecraft.rules.registry import Registry

from .rule_key import RuleKey
from .rulebook import render_listing, render_page


def run_rule(key: RuleKey | None) -> None:
    """Print the page of the rule `key` names, or the listing of every rule when `key` is `None`.

    Args:
        key: The argument, already parsed and confirmed against the rule index.

    Raises:
        RuntimeError: If the rules cannot be registered, or the index names a rule the registry does not hold, which
            means the generated index is stale.
    """
    registry = Registry.load(rules)
    if key is None:
        typer.echo(render_listing(registry))
        return

    typer.echo(render_page(key.to_declaration(registry)), nl=False)
