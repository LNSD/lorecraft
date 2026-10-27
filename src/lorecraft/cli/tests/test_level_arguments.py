"""Parsing and conflict validation for `-A`, `-W` and `-D`."""

import pytest

from lorecraft.rules.identity import Level, RuleCode
from lorecraft.rules.index import RuleRow

from ..level_arguments import (
    AllRulesTarget,
    ConflictingLevelArgumentError,
    InvalidLevelArgumentError,
    LevelArgument,
    Warnings,
    validate_level_arguments,
)


class AliasIndex:
    """A minimal index with an alias code."""

    def find(self, key: str, /) -> RuleRow | None:
        if key in ('LC304', 'empty-section', 'MD040'):
            return RuleRow('LC304', 'empty-section', 'deny', ('MD040',))
        return None


@pytest.mark.unit
class TestLevelArgumentParse:
    def test_parse_with_full_code_returns_its_level_and_code(self) -> None:
        #: Given
        raw = 'LC101'

        #: When
        argument = LevelArgument.parse(raw, Level.DENY)

        #: Then
        assert argument.level is Level.DENY, 'the selected level uses the shared enum'
        assert isinstance(argument.target, RuleCode), 'an active code is represented by its rule identity'
        assert str(argument.target) == 'LC101', 'a full rule code retains its canonical identity'

    def test_parse_with_alias_returns_the_rule_code(self) -> None:
        #: Given
        raw = 'MD040'

        #: When
        argument = LevelArgument.parse(raw, Level.ALLOW, AliasIndex())

        #: Then
        assert argument.level is Level.ALLOW, 'the selected level uses the shared enum'
        assert isinstance(argument.target, RuleCode), 'an alias resolves to its rule identity'
        assert str(argument.target) == 'LC304', 'an alias resolves to the canonical rule code'

    def test_parse_with_all_returns_the_reserved_selector(self) -> None:
        #: Given
        raw = 'ALL'

        #: When
        argument = LevelArgument.parse(raw, Level.WARN)

        #: Then
        assert argument == LevelArgument(Level.WARN, AllRulesTarget()), 'ALL is represented by its target type'

    def test_parse_with_warnings_under_deny_returns_the_reserved_selector(self) -> None:
        #: Given
        raw = 'warnings'

        #: When
        argument = LevelArgument.parse(raw, Level.DENY)

        #: Then
        assert argument == LevelArgument(Level.DENY, Warnings()), 'warnings has its own target type'

    def test_parse_with_code_prefix_refuses_value(self) -> None:
        #: Given
        raw = 'LC1'

        #: When
        with pytest.raises(InvalidLevelArgumentError) as exc_info:
            LevelArgument.parse(raw, Level.WARN)

        #: Then
        assert exc_info.value.value == raw, 'the usage error retains the rejected argument'

    def test_parse_with_group_refuses_value(self) -> None:
        #: Given
        raw = 'LC'

        #: When
        with pytest.raises(InvalidLevelArgumentError) as exc_info:
            LevelArgument.parse(raw, Level.WARN)

        #: Then
        assert exc_info.value.value == raw, 'a group is not a level selector'

    def test_parse_with_unknown_full_code_refuses_value(self) -> None:
        #: Given
        raw = 'LC999'

        #: When
        with pytest.raises(InvalidLevelArgumentError) as exc_info:
            LevelArgument.parse(raw, Level.WARN)

        #: Then
        assert exc_info.value.value == raw, 'an unknown code is rejected'

    def test_parse_with_rule_name_refuses_value(self) -> None:
        #: Given
        raw = 'empty-section'

        #: When
        with pytest.raises(InvalidLevelArgumentError) as exc_info:
            LevelArgument.parse(raw, Level.WARN)

        #: Then
        assert exc_info.value.value == raw, 'a rule name is not a level selector'

    def test_parse_with_engine_condition_refuses_value(self) -> None:
        #: Given
        raw = 'LC001'

        #: When
        with pytest.raises(InvalidLevelArgumentError) as exc_info:
            LevelArgument.parse(raw, Level.WARN)

        #: Then
        assert exc_info.value.value == raw, 'an engine condition cannot receive a rule level'

    def test_parse_with_empty_value_refuses_value(self) -> None:
        #: Given
        raw = ''

        #: When
        with pytest.raises(InvalidLevelArgumentError) as exc_info:
            LevelArgument.parse(raw, Level.WARN)

        #: Then
        assert exc_info.value.value == raw, 'an empty level value is rejected'

    def test_parse_with_warnings_under_allow_refuses_value(self) -> None:
        #: Given
        raw = 'warnings'

        #: When
        with pytest.raises(InvalidLevelArgumentError) as exc_info:
            LevelArgument.parse(raw, Level.ALLOW)

        #: Then
        assert exc_info.value.flag == '--allow', 'the usage error identifies the incompatible flag'


@pytest.mark.unit
class TestValidateLevelArguments:
    def test_validate_with_alias_and_code_at_different_levels_raises_conflict(self) -> None:
        #: Given
        rule_index = AliasIndex()
        arguments = (
            LevelArgument.parse('MD040', Level.ALLOW, rule_index),
            LevelArgument.parse('LC304', Level.DENY, rule_index),
        )

        #: When
        with pytest.raises(ConflictingLevelArgumentError) as exc_info:
            validate_level_arguments(arguments)

        #: Then
        assert exc_info.value.code == 'LC304', 'the conflict names the canonical rule code'

    def test_validate_with_same_level_repeated_allows_it(self) -> None:
        #: Given
        arguments = (LevelArgument.parse('LC101', Level.WARN), LevelArgument.parse('LC101', Level.WARN))

        #: When
        validate_level_arguments(arguments)

        #: Then
        assert arguments == (LevelArgument.parse('LC101', Level.WARN), LevelArgument.parse('LC101', Level.WARN)), (
            'repeating one level assignment is harmless'
        )
