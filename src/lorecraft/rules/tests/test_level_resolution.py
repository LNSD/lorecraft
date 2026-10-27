"""Level resolution by source precedence and selector specificity."""

import pytest

from ..identity import Level, RuleCode, RuleGroupPrefix
from ..level_resolution import LevelSource, ResolvedLevels
from .sample_rules.groups import SAMPLE
from .sample_rules.token_count.any_tokens import AnyTokens
from .sample_rules.token_count.over_half_budget import OverHalfBudget


@pytest.mark.unit
class TestResolvedLevels:
    def test_level_for_with_later_prefix_and_earlier_code_uses_code(self) -> None:
        #: Given
        code_level: LevelSource = {AnyTokens.CODE: Level.DENY}
        later_prefix_level: LevelSource = {SAMPLE.prefix: Level.ALLOW}
        levels = ResolvedLevels.from_sources((code_level, later_prefix_level))

        #: When
        level = levels.level_for(AnyTokens.CODE, AnyTokens.LEVEL)

        #: Then
        assert level is Level.DENY, 'an exact-code setting beats a prefix from any source'

    def test_resolution_for_with_an_exact_code_returns_its_source_and_selector(self) -> None:
        #: Given
        configured: LevelSource = {AnyTokens.CODE: Level.DENY}
        levels = ResolvedLevels.from_sources((configured,))

        #: When
        resolution = levels.resolution_for(AnyTokens.CODE, AnyTokens.LEVEL)

        #: Then
        assert resolution.source == 'config', 'the winning exact-code setting keeps its source'
        assert resolution.selector == AnyTokens.CODE, 'the winning exact-code setting keeps its selector'

    def test_level_for_with_prefix_and_code_in_same_source_uses_code(self) -> None:
        #: Given
        settings: LevelSource = {SAMPLE.prefix: Level.ALLOW, AnyTokens.CODE: Level.DENY}
        levels = ResolvedLevels.from_sources((settings,))

        #: When
        level = levels.level_for(AnyTokens.CODE, Level.WARN)

        #: Then
        assert level is Level.DENY, 'an exact rule code beats its prefix within a source'

    def test_level_for_without_matching_setting_uses_the_rule_default(self) -> None:
        #: Given
        unrelated: LevelSource = {RuleCode(SAMPLE, 99): Level.ALLOW}
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
        assert resolution.source == 'default', 'an unmatched rule uses the default origin'
        assert resolution.selector is None, 'a default level has no setting selector'

    def test_resolution_for_preserves_the_selected_source(self) -> None:
        #: Given
        cli: LevelSource = {AnyTokens.CODE: Level.DENY}
        levels = ResolvedLevels.from_named_sources((('config', {}), ('cli', cli)))

        #: When
        resolution = levels.resolution_for(AnyTokens.CODE, AnyTokens.LEVEL)

        #: Then
        assert resolution.level is Level.DENY, 'the cli source supplies its configured level'
        assert resolution.source == 'cli', 'the chosen level retains its cli origin'
        assert resolution.selector == AnyTokens.CODE, 'the chosen level retains its exact selector'

    def test_resolution_for_uses_the_winning_prefix_selector(self) -> None:
        #: Given
        cli: LevelSource = {SAMPLE.prefix: Level.DENY}
        levels = ResolvedLevels.from_named_sources((('cli', cli),))

        #: When
        resolution = levels.resolution_for(AnyTokens.CODE, AnyTokens.LEVEL)

        #: Then
        assert resolution.selector == SAMPLE.prefix, 'a prefix override retains the prefix the user set'

    def test_level_for_accepts_prefix_key_for_rule_group(self) -> None:
        #: Given
        prefix = RuleGroupPrefix('SMP')
        settings: LevelSource = {prefix: Level.WARN}
        levels = ResolvedLevels.from_sources((settings,))

        #: When
        level = levels.level_for(AnyTokens.CODE, Level.ALLOW)

        #: Then
        assert level is Level.WARN, 'a group prefix applies to every code in that group'
