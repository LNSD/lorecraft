"""Level resolution by source precedence and selector specificity."""

import pytest

from ..identity import Level, RuleCode
from ..level_resolution import (
    AllowedLevel,
    AllRules,
    DefaultLevel,
    LevelSetting,
    LevelSource,
    OverriddenLevel,
    ResolvedLevels,
    WrittenSelector,
)
from .level_helpers import default_level
from .sample_rules.groups import SAMPLE
from .sample_rules.token_count.any_tokens import AnyTokens
from .sample_rules.token_count.over_half_budget import OverHalfBudget


@pytest.mark.unit
class TestResolvedLevels:
    def test_level_for_with_later_all_and_earlier_code_uses_code(self) -> None:
        #: Given
        code_level: LevelSource = {AnyTokens.CODE: LevelSetting(Level.DENY)}
        later_all_level: LevelSource = {AllRules(): LevelSetting(Level.ALLOW)}
        levels = ResolvedLevels.from_sources((code_level, later_all_level))

        #: When
        level = levels.level_for(AnyTokens.CODE, AnyTokens.LEVEL)

        #: Then
        assert level is Level.DENY, 'an exact-code setting beats ALL from any source'

    def test_resolution_for_with_an_exact_code_returns_its_source_and_selector(self) -> None:
        #: Given
        configured: LevelSource = {AnyTokens.CODE: LevelSetting(Level.DENY)}
        levels = ResolvedLevels.from_sources((configured,))

        #: When
        resolution = levels.resolution_for(AnyTokens.CODE, AnyTokens.LEVEL)

        #: Then
        assert resolution == OverriddenLevel(Level.DENY, 'config', AnyTokens.CODE), (
            'the winning exact-code setting keeps its source and selector'
        )

    def test_level_for_with_all_and_code_in_same_source_uses_code(self) -> None:
        #: Given
        settings: LevelSource = {AllRules(): LevelSetting(Level.ALLOW), AnyTokens.CODE: LevelSetting(Level.DENY)}
        levels = ResolvedLevels.from_sources((settings,))

        #: When
        level = levels.level_for(AnyTokens.CODE, Level.WARN)

        #: Then
        assert level is Level.DENY, 'an exact rule code beats ALL within a source'

    def test_resolution_for_an_allow_default_returns_the_disabled_variant(self) -> None:
        #: Given
        levels = ResolvedLevels.from_sources(())

        #: When
        resolution = levels.resolution_for(AnyTokens.CODE, Level.ALLOW)

        #: Then
        assert isinstance(resolution, AllowedLevel), 'an allow default has its own non-reporting variant'

    def test_level_for_without_matching_setting_uses_the_rule_default(self) -> None:
        #: Given
        unrelated: LevelSource = {RuleCode(SAMPLE, 99): LevelSetting(Level.ALLOW)}
        levels = ResolvedLevels.from_sources((unrelated,))

        #: When
        level = levels.level_for(OverHalfBudget.CODE, OverHalfBudget.LEVEL)

        #: Then
        assert level is OverHalfBudget.LEVEL, 'an unmatched setting leaves the rule default intact'

    def test_resolution_for_without_a_setting_returns_default_origin_and_no_selector(self) -> None:
        #: Given
        levels = ResolvedLevels.from_sources(())

        #: When
        resolution = levels.resolution_for(OverHalfBudget.CODE, OverHalfBudget.LEVEL)

        #: Then
        assert resolution == DefaultLevel(default_level(OverHalfBudget)), 'an unmatched rule keeps its declared default'

    def test_resolution_for_preserves_the_selected_source(self) -> None:
        #: Given
        cli: LevelSource = {AnyTokens.CODE: LevelSetting(Level.DENY)}
        levels = ResolvedLevels.from_named_sources((('config', {}), ('cli', cli)))

        #: When
        resolution = levels.resolution_for(AnyTokens.CODE, AnyTokens.LEVEL)

        #: Then
        assert resolution == OverriddenLevel(Level.DENY, 'cli', AnyTokens.CODE), (
            'the chosen level retains its origin and exact selector'
        )

    def test_resolution_for_keeps_written_alias_only_as_provenance(self) -> None:
        #: Given
        settings: LevelSource = {AnyTokens.CODE: LevelSetting(Level.DENY, WrittenSelector('MD040'))}
        levels = ResolvedLevels.from_named_sources((('cli', settings),))

        #: When
        resolution = levels.resolution_for(AnyTokens.CODE, AnyTokens.LEVEL)

        #: Then
        assert resolution == OverriddenLevel(Level.DENY, 'cli', WrittenSelector('MD040')), (
            'the canonical key resolves with written provenance'
        )
