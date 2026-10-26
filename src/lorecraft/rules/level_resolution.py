"""Resolve a rule's level; an exact code from any source beats every prefix setting.

Each source is a mapping from a rule-group prefix or exact rule code to a level. Within one specificity, later
sources override earlier ones. Resolution is independent of detection: the result is a mapping the rule table can
use when it builds its enabled rules.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from .identity import Level, RuleCode, RuleGroupPrefix

type LevelSelector = RuleGroupPrefix | RuleCode
type LevelSource = Mapping[LevelSelector, Level]


@dataclass(frozen=True, slots=True)
class ResolvedLevels:
    """An ordered stack of configured level sources, from broad settings to local overrides.

    Attributes:
        sources: Configuration, command-line flags and inline directives in that order. A caller may omit
            unavailable sources, but must preserve this order. The rule's default is supplied separately to
            `level_for`.
    """

    sources: tuple[LevelSource, ...]

    @classmethod
    def from_sources(cls, sources: Sequence[LevelSource]) -> ResolvedLevels:
        """Hold a stable, immutable stack of level sources.

        Args:
            sources: Sources from lowest to highest precedence.
        """
        return cls(tuple(sources))

    def level_for(self, code: RuleCode, default: Level) -> Level:
        """Resolve a rule's level; an exact code from any source beats every prefix setting.

        Exact-code settings are considered from latest to earliest before any prefix setting. Prefix settings are
        then considered from latest to earliest.

        Args:
            code: The rule whose level is being resolved.
            default: The level declared by the rule.
        """
        for source in reversed(self.sources):
            if code in source:
                return source[code]
        for source in reversed(self.sources):
            if code.group.prefix in source:
                return source[code.group.prefix]
        return default
