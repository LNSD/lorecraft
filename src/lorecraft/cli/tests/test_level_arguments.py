"""Parsing and conflict validation for `-A`, `-W` and `-D`."""

import pytest

from lorecraft.cli.rule_key import RuleKey
from lorecraft.rules.frontmatter.duplicate_key import DuplicateKey
from lorecraft.rules.identity import Level
from lorecraft.rules.index import RuleRow
from lorecraft.rules.level_resolution import WrittenSelector
from lorecraft.rules.registry import Registry

from ..level_arguments import (
    AllRulesTarget,
    ConflictingLevelArgumentError,
    DenyWarnings,
    IndexRuleNotInRegistryError,
    InvalidLevelArgumentError,
    LevelArgument,
    RuleCodeTarget,
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
        assert isinstance(argument, LevelArgument), 'a rule code is an ordinary level argument'
        assert argument.level is Level.DENY, 'the selected level uses the shared enum'
        assert isinstance(argument.target, RuleCodeTarget), 'an active code retains its canonical text'
        assert str(argument.target) == 'LC101', 'a full rule code retains its canonical identity'

    def test_parse_with_alias_returns_the_rule_code(self) -> None:
        #: Given
        raw = 'MD040'

        #: When
        argument = LevelArgument.parse(raw, Level.ALLOW, AliasIndex())

        #: Then
        assert isinstance(argument, LevelArgument), 'a code alias is an ordinary level argument'
        assert argument.level is Level.ALLOW, 'the selected level uses the shared enum'
        assert isinstance(argument.target, RuleCodeTarget), 'an alias resolves to its canonical code text'
        assert str(argument.target) == 'LC304', 'an alias resolves to the canonical rule code'
        assert argument.target.alias == WrittenSelector(raw), 'the target preserves the alias the user typed'

    def test_target_to_rule_code_builds_the_identity_from_the_runtime_registry(self) -> None:
        #: Given
        registry = Registry((DuplicateKey,))
        target = RuleCodeTarget(RuleKey(str(DuplicateKey.CODE)))

        #: When
        code = target.to_rule_code(registry)

        #: Then
        assert code is DuplicateKey.CODE, 'the active rule code is built only after the runtime registry is loaded'

    def test_target_to_rule_code_with_a_missing_declaration_raises_runtime_error(self) -> None:
        #: Given
        target = RuleCodeTarget(RuleKey(str(DuplicateKey.CODE)))

        #: When
        with pytest.raises(IndexRuleNotInRegistryError) as exc_info:
            target.to_rule_code(Registry(()))

        #: Then
        assert isinstance(exc_info.value, RuntimeError), 'a stale generated index is a package defect'

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
        assert argument == DenyWarnings(), 'warnings has its own argument variant'

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
        assert exc_info.value.reason == 'warnings is reserved for --deny', 'the error explains the reserved selector'

    def test_parse_with_warnings_under_warn_refuses_value(self) -> None:
        #: Given
        raw = 'warnings'

        #: When
        with pytest.raises(InvalidLevelArgumentError) as exc_info:
            LevelArgument.parse(raw, Level.WARN)

        #: Then
        assert exc_info.value.reason == 'warnings is reserved for --deny', 'the error names its reserved flag'


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
        assert str(exc_info.value.target) == 'LC304', 'the conflict names the canonical rule code'

    def test_validate_with_same_level_repeated_allows_it(self) -> None:
        #: Given
        arguments = (LevelArgument.parse('LC101', Level.WARN), LevelArgument.parse('LC101', Level.WARN))

        #: When
        validate_level_arguments(arguments)

        #: Then
        assert arguments == (LevelArgument.parse('LC101', Level.WARN), LevelArgument.parse('LC101', Level.WARN)), (
            'repeating one level assignment is harmless'
        )
