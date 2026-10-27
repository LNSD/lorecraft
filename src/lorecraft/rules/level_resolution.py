"""Resolve a rule's level; an exact code from any source beats every prefix setting.

Each source is a mapping from a rule-group prefix or exact rule code to a level. Within one specificity, later
sources override earlier ones. Resolution is independent of detection: the result is a mapping the rule table can
use when it builds its enabled rules.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from .identity import Level, RuleCode, RuleGroupPrefix

type LevelSelector = RuleGroupPrefix | RuleCode
type LevelSource = Mapping[LevelSelector, Level]
type LevelOrigin = Literal['default', 'config', 'cli']


@dataclass(frozen=True, slots=True)
class LevelResolution:
    """The chosen level, its origin and the selector that set it.

    Attributes:
        level: The level that applies to the rule.
        source: Where the setting came from, or `default` when nothing set it.
        selector: The exact code or group prefix that matched, or None for a default.
    """

    level: Level
    source: LevelOrigin
    selector: LevelSelector | None


@dataclass(frozen=True, slots=True)
class ResolvedLevels:
    """An ordered stack of configured level sources, from broad settings to local overrides.

    Attributes:
        sources: The level mappings and their origin, ordered from lowest to highest precedence. A caller may omit
            unavailable sources, but must preserve this order. The rule's default is supplied separately to
            `level_for`.
    """

    sources: tuple[tuple[LevelOrigin, LevelSource], ...]

    @classmethod
    def from_sources(cls, sources: Sequence[LevelSource]) -> ResolvedLevels:
        """Hold a stable, immutable stack of level sources.

        Args:
            sources: Sources from lowest to highest precedence.
        """
        return cls(tuple(('config', source) for source in sources))

    @classmethod
    def from_named_sources(cls, sources: Sequence[tuple[LevelOrigin, LevelSource]]) -> ResolvedLevels:
        """Hold level sources with their origin, lowest to highest precedence."""
        return cls(tuple(sources))

    def level_for(self, code: RuleCode, default: Level) -> Level:
        """Resolve a rule's level; an exact code from any source beats every prefix setting.

        Exact-code settings are considered from latest to earliest before any prefix setting. Prefix settings are
        then considered from latest to earliest.

        Args:
            code: The rule whose level is being resolved.
            default: The level declared by the rule.
        """
        return self.resolution_for(code, default).level

    def resolution_for(self, code: RuleCode, default: Level) -> LevelResolution:
        """Resolve the level and identify the highest-precedence source that set it."""
        for selector in (code, code.group.prefix):
            for source, settings in reversed(self.sources):
                if selector in settings:
                    return LevelResolution(settings[selector], source, selector)
        return LevelResolution(default, 'default', None)
