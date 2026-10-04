"""A rule's declaration: its identity values, its rule bases, and the `@rule` decorator."""

import pytest

from lorecraft.core.error import Error
from lorecraft.project.syntax import LineNumber

from ..location import Here, WholeSubject
from ..rule import (
    AliasCode,
    DoubledHyphenRuleNameError,
    EmptyAliasLinterError,
    EmptyRuleGroupTitleError,
    EmptyRuleNameError,
    InvalidAliasCodeError,
    InvalidRuleGroupPrefixError,
    InvalidRuleNameCharacterError,
    LeadingHyphenRuleNameError,
    LeadingZeroReleaseError,
    Level,
    MalformedReleaseError,
    Release,
    Rule,
    RuleCode,
    RuleGroup,
    RuleName,
    RuleNumberOutOfRangeError,
    TrailingHyphenRuleNameError,
    declared_rules,
)
from .sample_input import SampleEntry, SampleLines
from .sample_rules.groups import SAMPLE
from .sample_rules.valid.retired import TabIndent
from .sample_rules.valid.trailing_space import TrailingSpace
from .sample_rules.valid.uppercase_entry import UppercaseEntry


@pytest.mark.unit
class TestRelease:
    def test_parse_with_three_components_returns_the_release(self) -> None:
        #: Given
        raw = '0.3.0'

        #: When
        release = Release.parse(raw)

        #: Then
        assert str(release) == raw, 'a release is kept exactly as spelled'

    def test_parse_with_a_multi_digit_component_returns_the_release(self) -> None:
        #: Given
        raw = '1.10.200'

        #: When
        release = Release.parse(raw)

        #: Then
        assert str(release) == raw, 'a component may have several digits'

    def test_parse_with_a_v_prefix_raises_malformed_release_error(self) -> None:
        #: Given
        raw = 'v0.3.0'

        #: When
        with pytest.raises(MalformedReleaseError) as exc_info:
            Release.parse(raw)

        #: Then
        assert exc_info.value.value == raw, 'the error keeps the release with a prefix'

    def test_parse_with_two_components_raises_malformed_release_error(self) -> None:
        #: Given
        raw = '0.3'

        #: When
        with pytest.raises(MalformedReleaseError) as exc_info:
            Release.parse(raw)

        #: Then
        assert exc_info.value.value == raw, 'the error keeps the release missing its patch'

    def test_parse_with_four_components_raises_malformed_release_error(self) -> None:
        #: Given
        raw = '0.3.0.1'

        #: When
        with pytest.raises(MalformedReleaseError) as exc_info:
            Release.parse(raw)

        #: Then
        assert exc_info.value.value == raw, 'the error keeps the release with a fourth component'

    def test_parse_with_a_pre_release_suffix_raises_malformed_release_error(self) -> None:
        #: Given
        raw = '0.3.0-rc1'

        #: When
        with pytest.raises(MalformedReleaseError) as exc_info:
            Release.parse(raw)

        #: Then
        assert exc_info.value.value == raw, 'the error keeps the release with a suffix'

    def test_parse_with_an_empty_component_raises_malformed_release_error(self) -> None:
        #: Given
        raw = '0..3'

        #: When
        with pytest.raises(MalformedReleaseError) as exc_info:
            Release.parse(raw)

        #: Then
        assert exc_info.value.value == raw, 'the error keeps the release with an empty component'

    def test_parse_with_a_non_ascii_digit_raises_malformed_release_error(self) -> None:
        #: Given
        raw = '0.\N{ARABIC-INDIC DIGIT THREE}.0'

        #: When
        with pytest.raises(MalformedReleaseError) as exc_info:
            Release.parse(raw)

        #: Then
        assert exc_info.value.value == raw, 'the error keeps the release with a digit outside ASCII'

    def test_parse_with_a_leading_zero_raises_leading_zero_release_error(self) -> None:
        #: Given
        raw = '0.03.0'

        #: When
        with pytest.raises(LeadingZeroReleaseError) as exc_info:
            Release.parse(raw)

        #: Then
        assert exc_info.value.value == raw, 'the error keeps the release'
        assert exc_info.value.component == '03', 'the error names the component with the leading zero'


@pytest.mark.unit
class TestRuleName:
    def test_parse_with_words_joined_by_hyphens_returns_the_name(self) -> None:
        #: Given
        raw = 'empty-section'

        #: When
        name = RuleName.parse(raw)

        #: Then
        assert str(name) == raw, 'a name is kept exactly as spelled'

    def test_parse_with_a_single_letter_returns_the_name(self) -> None:
        #: Given
        raw = 'a'

        #: When
        name = RuleName.parse(raw)

        #: Then
        assert str(name) == raw, 'one character is the shortest name that is not empty'

    def test_parse_with_digits_returns_the_name(self) -> None:
        #: Given
        raw = 'md040-fence2'

        #: When
        name = RuleName.parse(raw)

        #: Then
        assert str(name) == raw, 'a word may hold ASCII digits beside its lowercase letters'

    def test_parse_with_several_single_hyphens_returns_the_name(self) -> None:
        #: Given
        raw = 'section-out-of-order'

        #: When
        name = RuleName.parse(raw)

        #: Then
        assert str(name) == raw, 'any number of words may be joined, each by one hyphen'

    def test_parse_with_an_empty_name_raises_empty_rule_name_error(self) -> None:
        #: Given
        raw = ''

        #: When
        with pytest.raises(EmptyRuleNameError) as exc_info:
            RuleName.parse(raw)

        #: Then
        assert type(exc_info.value).__bases__ == (Error,), 'the variant derives from Error directly, not a family'
        assert str(exc_info.value) == 'rule name cannot be empty', 'the error explains the empty-name case'

    def test_rule_name_constructed_directly_with_an_empty_name_raises_empty_rule_name_error(self) -> None:
        #: Given
        raw = ''

        #: When
        with pytest.raises(EmptyRuleNameError) as exc_info:
            RuleName(raw)

        #: Then
        assert str(exc_info.value) == 'rule name cannot be empty', 'direct construction checks the same invariant'

    def test_parse_with_an_uppercase_letter_raises_invalid_rule_name_character_error(self) -> None:
        #: Given
        raw = 'empty-Section'

        #: When
        with pytest.raises(InvalidRuleNameCharacterError) as exc_info:
            RuleName.parse(raw)

        #: Then
        assert exc_info.value.value == raw, 'the error keeps the name with an uppercase letter'
        assert exc_info.value.position == 6, 'the error locates the uppercase letter'
        assert exc_info.value.character == 'S', 'the error names the uppercase letter'

    def test_parse_with_a_space_raises_invalid_rule_name_character_error(self) -> None:
        #: Given
        raw = 'empty section'

        #: When
        with pytest.raises(InvalidRuleNameCharacterError) as exc_info:
            RuleName.parse(raw)

        #: Then
        assert exc_info.value.character == ' ', 'a space does not join two words'

    def test_parse_with_an_underscore_raises_invalid_rule_name_character_error(self) -> None:
        #: Given
        raw = 'empty_section'

        #: When
        with pytest.raises(InvalidRuleNameCharacterError) as exc_info:
            RuleName.parse(raw)

        #: Then
        assert exc_info.value.character == '_', 'an underscore does not join two words'

    def test_parse_with_a_non_ascii_letter_raises_invalid_rule_name_character_error(self) -> None:
        #: Given
        raw = '\N{LATIN SMALL LETTER E WITH ACUTE}mpty-section'

        #: When
        with pytest.raises(InvalidRuleNameCharacterError) as exc_info:
            RuleName.parse(raw)

        #: Then
        assert exc_info.value.position == 0, 'a lowercase letter outside ASCII is rejected'

    def test_parse_with_a_leading_hyphen_raises_leading_hyphen_rule_name_error(self) -> None:
        #: Given
        raw = '-empty-section'

        #: When
        with pytest.raises(LeadingHyphenRuleNameError) as exc_info:
            RuleName.parse(raw)

        #: Then
        assert exc_info.value.value == raw, 'the error keeps the name starting with a hyphen'

    def test_parse_with_a_trailing_hyphen_raises_trailing_hyphen_rule_name_error(self) -> None:
        #: Given
        raw = 'empty-section-'

        #: When
        with pytest.raises(TrailingHyphenRuleNameError) as exc_info:
            RuleName.parse(raw)

        #: Then
        assert exc_info.value.value == raw, 'the error keeps the name ending with a hyphen'

    def test_parse_with_two_hyphens_in_a_row_raises_doubled_hyphen_rule_name_error(self) -> None:
        #: Given
        raw = 'empty--section'

        #: When
        with pytest.raises(DoubledHyphenRuleNameError) as exc_info:
            RuleName.parse(raw)

        #: Then
        assert exc_info.value.value == raw, 'the error keeps the name with two hyphens in a row'
        assert exc_info.value.position == 5, 'the error locates the first of the two hyphens'


@pytest.mark.unit
class TestRuleGroup:
    def test_rule_group_with_an_empty_prefix_raises_invalid_rule_group_prefix_error(self) -> None:
        #: Given
        prefix = ''

        #: When
        with pytest.raises(InvalidRuleGroupPrefixError) as exc_info:
            RuleGroup(prefix, 'Outline')

        #: Then
        assert exc_info.value.prefix == prefix, 'the error keeps the empty prefix'

    def test_rule_group_with_a_lowercase_prefix_raises_invalid_rule_group_prefix_error(self) -> None:
        #: Given
        prefix = 'Out'

        #: When
        with pytest.raises(InvalidRuleGroupPrefixError) as exc_info:
            RuleGroup(prefix, 'Outline')

        #: Then
        assert exc_info.value.prefix == prefix, 'the error keeps the prefix with a lowercase letter'

    def test_rule_group_with_a_digit_in_the_prefix_raises_invalid_rule_group_prefix_error(self) -> None:
        #: Given
        prefix = 'OUT2'

        #: When
        with pytest.raises(InvalidRuleGroupPrefixError) as exc_info:
            RuleGroup(prefix, 'Outline')

        #: Then
        assert exc_info.value.prefix == prefix, 'the error keeps the prefix with a digit'

    def test_rule_group_with_an_empty_title_raises_empty_rule_group_title_error(self) -> None:
        #: Given
        title = ''

        #: When
        with pytest.raises(EmptyRuleGroupTitleError) as exc_info:
            RuleGroup('OUT', title)

        #: Then
        assert exc_info.value.prefix == 'OUT', 'the error names the group with no title'


@pytest.mark.unit
class TestRuleCode:
    def test_str_with_a_one_digit_number_pads_it_to_three_digits(self) -> None:
        #: Given
        code = RuleCode(RuleGroup('OUT', 'Outline'), 2)

        #: When
        printed = str(code)

        #: Then
        assert printed == 'OUT002', "a code prints as its group's prefix and three digits"

    def test_str_with_the_largest_number_prints_it_unpadded(self) -> None:
        #: Given
        code = RuleCode(RuleGroup('OUT', 'Outline'), 999)

        #: When
        printed = str(code)

        #: Then
        assert printed == 'OUT999', 'a three-digit number needs no padding'

    def test_rule_code_with_number_zero_raises_rule_number_out_of_range_error(self) -> None:
        #: Given
        number = 0

        #: When
        with pytest.raises(RuleNumberOutOfRangeError) as exc_info:
            RuleCode(SAMPLE, number)

        #: Then
        assert exc_info.value.group is SAMPLE, 'the error names the group of the code'
        assert exc_info.value.number == number, 'the error keeps the number below the range'

    def test_rule_code_with_a_four_digit_number_raises_rule_number_out_of_range_error(self) -> None:
        #: Given
        number = 1000

        #: When
        with pytest.raises(RuleNumberOutOfRangeError) as exc_info:
            RuleCode(SAMPLE, number)

        #: Then
        assert exc_info.value.number == number, 'the error keeps the number that would print four digits'


@pytest.mark.unit
class TestAliasCode:
    def test_str_with_a_linter_and_a_code_prints_the_code_alone(self) -> None:
        #: Given
        alias = AliasCode('markdownlint', 'MD040')

        #: When
        printed = str(alias)

        #: Then
        assert printed == 'MD040', 'an alias code prints as the upstream code a user types'

    def test_alias_code_with_an_empty_linter_raises_empty_alias_linter_error(self) -> None:
        #: Given
        linter = ''

        #: When
        with pytest.raises(EmptyAliasLinterError) as exc_info:
            AliasCode(linter, 'MD040')

        #: Then
        assert exc_info.value.code == 'MD040', 'the error names the code with no linter'

    def test_alias_code_with_an_empty_code_raises_invalid_alias_code_error(self) -> None:
        #: Given
        code = ''

        #: When
        with pytest.raises(InvalidAliasCodeError) as exc_info:
            AliasCode('markdownlint', code)

        #: Then
        assert exc_info.value.linter == 'markdownlint', 'the error names the linter'
        assert exc_info.value.code == code, 'the error keeps the empty code'

    def test_alias_code_with_whitespace_in_the_code_raises_invalid_alias_code_error(self) -> None:
        #: Given
        code = 'MD 040'

        #: When
        with pytest.raises(InvalidAliasCodeError) as exc_info:
            AliasCode('markdownlint', code)

        #: Then
        assert exc_info.value.code == code, 'the error keeps the code holding a space'


@pytest.mark.unit
class TestLevel:
    def test_level_values_in_declaration_order_spell_allow_warn_deny(self) -> None:
        #: Given
        expected = ('allow', 'warn', 'deny')

        #: When
        spelled = tuple(level.value for level in Level)

        #: Then
        assert spelled == expected, 'the three levels, in order, are spelled allow, warn and deny'


@pytest.mark.unit
class TestContentRule:
    def test_primary_of_a_content_rule_occurrence_is_its_line(self) -> None:
        #: Given
        occurrence = TrailingSpace(spec=None, line=LineNumber(4))

        #: When
        primary = occurrence.primary()

        #: Then
        assert primary == Here(LineNumber(4)), 'an occurrence in a subject with lines points at its line'

    def test_labels_of_a_content_rule_occurrence_by_default_are_empty(self) -> None:
        #: Given
        occurrence = TrailingSpace(spec=None, line=LineNumber(4))

        #: When
        labels = occurrence.labels()

        #: Then
        assert labels == (), 'a rule that writes no label leaves its line unlabelled'

    def test_children_of_a_content_rule_occurrence_by_default_are_empty(self) -> None:
        #: Given
        occurrence = TrailingSpace(spec=None, line=LineNumber(4))

        #: When
        children = occurrence.children()

        #: Then
        assert children == (), 'a rule that writes no help or note prints its message alone'

    def test_check_of_a_sample_rule_reports_its_own_occurrences(self) -> None:
        #: Given
        subject = SampleLines(('clean', 'trailing ', 'clean'))

        #: When
        occurrences = TrailingSpace.check(subject)

        #: Then
        assert occurrences == (TrailingSpace(spec=None, line=LineNumber(2)),), (
            'a rule reports one instance of its own class per occurrence'
        )


@pytest.mark.unit
class TestLayoutRule:
    def test_primary_of_a_layout_rule_occurrence_is_the_whole_subject(self) -> None:
        #: Given
        occurrence = UppercaseEntry(spec=None)

        #: When
        primary = occurrence.primary()

        #: Then
        assert primary == WholeSubject(), 'a layout entry has no lines, so its occurrence points at the entry'

    def test_labels_of_a_layout_rule_occurrence_by_default_are_empty(self) -> None:
        #: Given
        occurrence = UppercaseEntry(spec=None)

        #: When
        labels = occurrence.labels()

        #: Then
        assert labels == (), 'a rule that writes no label leaves the entry unlabelled'

    def test_children_of_a_layout_rule_occurrence_by_default_are_empty(self) -> None:
        #: Given
        occurrence = UppercaseEntry(spec=None)

        #: When
        children = occurrence.children()

        #: Then
        assert children == (), 'a rule that writes no help or note prints its message alone'

    def test_check_of_a_sample_layout_rule_reports_one_occurrence_for_the_entry(self) -> None:
        #: Given
        subject = SampleEntry('README')

        #: When
        occurrences = UppercaseEntry.check(subject)

        #: Then
        assert occurrences == (UppercaseEntry(spec=None),), 'a layout rule reports the entry once, with no line'


@pytest.mark.unit
class TestRemovedRule:
    def test_removed_rule_as_a_class_is_not_a_rule_subclass(self) -> None:
        #: Given
        removed = TabIndent

        #: When
        is_rule = issubclass(removed, Rule)

        #: Then
        assert is_rule is False, 'a removed rule can never be built as an occurrence or reported'


@pytest.mark.unit
class TestRuleDecorator:
    def test_rule_on_a_rule_class_at_import_leaves_its_declaration_unchanged(self) -> None:
        #: Given
        # TrailingSpace was decorated with @rule as its module was imported with this one
        declared = TrailingSpace

        #: When
        code = str(declared.CODE)

        #: Then
        assert declared.__name__ == 'TrailingSpace', 'the decorated name is bound to the class itself'
        assert code == 'SMP002', 'the class keeps the code it declares'

    def test_rule_on_a_removed_rule_at_import_records_it(self) -> None:
        #: Given
        # TabIndent was decorated with @rule as its module was imported with this one
        removed = TabIndent

        #: When
        declared = declared_rules()

        #: Then
        assert removed in declared, 'a removed rule is recorded for the registry to collect'
