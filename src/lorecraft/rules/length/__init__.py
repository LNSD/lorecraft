"""The `LEN` group: every length limit a subject must fit, one module per rule."""

from typing import Final

from lorecraft.rules.rule import RuleGroup

LENGTH: Final[RuleGroup] = RuleGroup('LEN', 'Length limits')
"""The group of the rules that hold a subject to a length limit: a document's token budget among them."""
