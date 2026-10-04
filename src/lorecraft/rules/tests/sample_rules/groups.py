"""The rule groups the sample rules belong to."""

from typing import Final

from lorecraft.rules.rule import RuleGroup

SAMPLE: Final[RuleGroup] = RuleGroup('SMP', 'Sample rules')
"""The group of most sample rules."""

LAYOUT: Final[RuleGroup] = RuleGroup('LAYS', 'Sample layout rules')
"""The group of the sample rules over a layout entry."""
