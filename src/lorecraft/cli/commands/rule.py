"""The `rule` subcommand: print a rule's page from the rulebook, or list every rule.

The rules are package data, so the command reads no workspace and needs no root. The command declares the argument
and the help text, and parses the argument against the rule index while the command line is read; the flow is in
`rule_run`, which this module imports only when the command runs, so that `--help` and `--version` never import the
rules.
"""

from typing import Annotated

import typer

from ..registry import register
from ..rule_arguments import MalformedRuleKeyError, RuleKey, UnknownRuleKeyError


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
        except (MalformedRuleKeyError, UnknownRuleKeyError) as exc:
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
    # Imported here, not at the top: `rule_run` imports the rules, which `--help` and `--version` never use.
    from ..rule_run import run_rule

    run_rule(key)
