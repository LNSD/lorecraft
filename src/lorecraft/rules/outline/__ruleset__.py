"""The LC3xx group checks document titles and sections against structure specifications."""

from typing import Final

from lorecraft.rules.identity import RuleGroup, RuleGroupPrefix

GROUP_ID: Final[RuleGroup] = RuleGroup(RuleGroupPrefix('LC'), 'Outline checks', range(300, 310))
"""The group of the rules over a document's sections, as a structure file states them, and over its H1
title, which every governed document carries without a key stating it."""
