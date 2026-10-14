"""What the `LC` group's conditions share: the group they are declared under, and what a refusal was of."""

from enum import StrEnum
from typing import Final

from lorecraft.rules.identity import ENGINE_GROUP, RuleGroup

GROUP_ID: Final[RuleGroup] = ENGINE_GROUP
"""The group reserved for engine conditions: a condition's `EngineCode` is always in it, and the registry rejects, as
the package loads, a rule or a removed rule inside it."""


class RefusedOperation(StrEnum):
    """What the operating system refused while a structure file, a directory or a `SKILL.md` was reached.

    Each value is the verb a message states it with.
    """

    READ = 'read'
    RESOLVE = 'resolve'
    INSPECT = 'inspect'
    LIST = 'list'
