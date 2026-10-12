"""What the `LC` group's conditions share: the group they are declared under, and what a refusal was of."""

from enum import Enum
from typing import Final

from lorecraft.rules.declaration import RuleGroup, RuleGroupPrefix

GROUP_ID: Final[RuleGroup] = RuleGroup(RuleGroupPrefix('LC'), 'Engine conditions')
"""The group reserved for engine conditions: the registry rejects, as the package loads, a condition outside it and a
rule or a removed rule inside it."""


class RefusedOperation(Enum):
    """What the operating system refused while a skills directory, a skill entry or a `SKILL.md` was reached.

    Each value is the verb a message states it with.
    """

    RESOLVE = 'resolve'
    INSPECT = 'inspect'
    LIST = 'list'
