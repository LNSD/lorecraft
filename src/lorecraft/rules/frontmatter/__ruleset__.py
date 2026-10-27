"""The frontmatter rule group and its identity."""

from typing import Final

from lorecraft.rules.identity import RuleGroup, RuleGroupPrefix

GROUP_ID: Final[RuleGroup] = RuleGroup(RuleGroupPrefix('LC'), 'Frontmatter checks', range(200, 300))
"""The group of the rules over a subject's frontmatter: the block itself, and the schema that governs it."""
