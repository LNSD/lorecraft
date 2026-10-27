"""Resolve a rule's level by selector specificity and source precedence.

Each source maps an exact rule code or `ALL` to a level setting. A rule code beats `ALL`; within one specificity,
later sources override earlier ones. Resolution is independent of detection: the result is a mapping the rule table
uses to build its enabled rules.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from .identity import EnabledLevel, Level, RuleCode, Severity, severity_for_enabled_level


@dataclass(frozen=True, slots=True)
class AllRules:
    """The `ALL` selector for a level flag."""

    def __str__(self) -> str:
        """The reserved selector's spelling."""
        return 'ALL'


@dataclass(frozen=True, slots=True)
class WrittenSelector:
    """The spelling of a rule-code selector as the user supplied it.

    Attributes:
        spelling: The selector token, retained for the diagnostic's provenance note.
    """

    spelling: str

    def __str__(self) -> str:
        """The alias exactly as the user typed it."""
        return self.spelling


type LevelSelector = AllRules | RuleCode
type ProvenanceSelector = LevelSelector | WrittenSelector
type SourceOrigin = Literal['config', 'cli']
type LevelOrigin = Literal['default'] | SourceOrigin


@dataclass(frozen=True, slots=True)
class DefaultLevel:
    """A rule's declared default level, without an override source or selector.

    Attributes:
        level: The level declared by the rule.
    """

    level: EnabledLevel

    @property
    def severity(self) -> Severity:
        """The severity corresponding to this enabled level."""
        return severity_for_enabled_level(self.level)


@dataclass(frozen=True, slots=True)
class OverriddenLevel:
    """A configured or command-line level override.

    Attributes:
        level: The level assigned by the setting.
        origin: Where the setting came from.
        selector: The matching resolution selector or the code spelling the user supplied.
    """

    level: EnabledLevel
    origin: SourceOrigin
    selector: ProvenanceSelector

    @property
    def severity(self) -> Severity:
        """The severity corresponding to this enabled level."""
        return severity_for_enabled_level(self.level)


@dataclass(frozen=True, slots=True)
class ElevatedWarning:
    """A resolved warning elevated to error by `-D warnings`."""

    @property
    def severity(self) -> Severity:
        """The severity of an elevated warning."""
        return Severity.ERROR


@dataclass(frozen=True, slots=True)
class AllowedLevel:
    """A rule resolved to allow and therefore excluded from reporting."""


# The complete resolution from settings; allowed rules have no reporting severity.
type LevelResolution = DefaultLevel | OverriddenLevel | AllowedLevel
# The resolution retained for an enabled rule and its diagnostics.
type ReportingResolution = DefaultLevel | OverriddenLevel | ElevatedWarning


@dataclass(frozen=True, slots=True)
class LevelSetting:
    """A level assigned by a resolution selector, with its provenance spelling.

    Attributes:
        level: The level the matching selector assigns.
        selector: The alias spelling to report, or None to report the matching resolution key.
    """

    level: Level
    selector: WrittenSelector | None = None


type LevelSource = Mapping[LevelSelector, LevelSetting]


@dataclass(frozen=True, slots=True)
class ResolvedLevels:
    """An ordered stack of level sources, from broad settings to local overrides.

    Resolving a rule produces a `LevelResolution`, which may be allowed; tables and reports hold a
    `ReportingResolution`, which excludes allowed rules.

    Attributes:
        sources: The level mappings and their origin, ordered from lowest to highest precedence. A caller may omit
            unavailable sources, but must preserve this order. The rule's default is supplied separately to
            `level_for`.
    """

    sources: tuple[tuple[SourceOrigin, LevelSource], ...]

    @classmethod
    def from_sources(cls, sources: Sequence[LevelSource]) -> ResolvedLevels:
        """Hold a stable, immutable stack of level sources.

        Args:
            sources: Sources from lowest to highest precedence.
        """
        return cls(tuple(('config', source) for source in sources))

    @classmethod
    def from_named_sources(cls, sources: Sequence[tuple[SourceOrigin, LevelSource]]) -> ResolvedLevels:
        """Hold level sources with their origin, lowest to highest precedence.

        Args:
            sources: Named sources in increasing precedence order.
        """
        return cls(tuple(sources))

    def level_for(self, code: RuleCode, default: Level) -> Level:
        """Resolve a rule's level by specificity, then source precedence.

        A rule code beats `ALL` from any source; within a specificity, later sources win.

        Args:
            code: The rule whose level is being resolved.
            default: The level declared by the rule.
        """
        resolution: LevelResolution = self.resolution_for(code, default)
        match resolution:
            case AllowedLevel():
                return Level.ALLOW
            case DefaultLevel(level=level) | OverriddenLevel(level=level):
                return level

    def resolution_for(self, code: RuleCode, default: Level) -> LevelResolution:
        """Resolve the level and identify the highest-precedence source that set it.

        Args:
            code: The rule whose level is being resolved.
            default: The level declared by the rule.
        """
        for selector in (code, AllRules()):
            for source, settings in reversed(self.sources):
                if selector in settings:
                    setting = settings[selector]
                    selector_spelling = selector if setting.selector is None else setting.selector
                    if setting.level is Level.ALLOW:
                        return AllowedLevel()
                    return OverriddenLevel(setting.level, source, selector_spelling)
        match default:
            case Level.ALLOW:
                return AllowedLevel()
            case Level.WARN | Level.DENY:
                return DefaultLevel(default)
