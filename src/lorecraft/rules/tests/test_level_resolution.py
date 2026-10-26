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

    def test_level_for_accepts_prefix_key_for_rule_group(self) -> None:
        #: Given
        prefix = RuleGroupPrefix('SMP')
        settings: LevelSource = {prefix: Level.WARN}
        levels = ResolvedLevels.from_sources((settings,))

        #: When
        level = levels.level_for(AnyTokens.CODE, Level.ALLOW)

        #: Then
        assert level is Level.WARN, 'a group prefix applies to every code in that group'
