"""The rule groups the sample rules belong to."""

from typing import Final

from lorecraft.rules.declaration import RuleGroup, RuleGroupPrefix

SAMPLE: Final[RuleGroup] = RuleGroup(RuleGroupPrefix('SMP'), 'Sample rules')
"""The group of most sample rules."""

LAYOUT: Final[RuleGroup] = RuleGroup(RuleGroupPrefix('LAYS'), 'Sample layout rules')
"""The group of the sample rules over a layout entry."""
