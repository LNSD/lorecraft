"""What the `LC` group's conditions share: the group they are declared under."""

from typing import Final

from lorecraft.rules.declaration import RuleGroup

GROUP_ID: Final[RuleGroup] = RuleGroup('LC', 'Engine conditions')
"""The group reserved for engine conditions: the registry rejects, as the package loads, a condition outside it and a
rule or a removed rule inside it."""
