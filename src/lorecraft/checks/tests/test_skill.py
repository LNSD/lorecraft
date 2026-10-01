"""Skill validation over a ``SKILL.md``'s frontmatter node.

``validate_skill`` is pure, so every case here is a text literal parsed in memory and a directory name, held to
the one Agent Skills specification; no ``SKILL.md`` is read.
"""

import pytest

from lorecraft.project.schemas import SKILL_FRONTMATTER_SCHEMA
from lorecraft.project.syntax import LineNumber, parse_frontmatter

from ..reporting import Violation
from ..skill import validate_skill


@pytest.mark.unit
class TestValidateSkill:
    def test_validate_skill_with_conforming_frontmatter_returns_no_violations(self) -> None:
        #: Given
        frontmatter = parse_frontmatter('---\nname: review\ndescription: Review a change. Use before a PR\n---\n')

        #: When
        result = validate_skill(SKILL_FRONTMATTER_SCHEMA, frontmatter=frontmatter, directory_name='review')

        #: Then
        assert result.violations == (), 'a skill with the two required fields, named for its directory, is clean'

    def test_validate_skill_with_every_specification_field_returns_no_violations(self) -> None:
        #: Given
        frontmatter = parse_frontmatter(
            '---\n'
            'name: review\n'
            'description: Review a change. Use before a PR\n'
            'license: Apache-2.0\n'
            'compatibility: Requires git\n'
            'metadata:\n'
            '  author: example-org\n'
            'allowed-tools: Read Grep\n'
            '---\n'
        )

        #: When
        result = validate_skill(SKILL_FRONTMATTER_SCHEMA, frontmatter=frontmatter, directory_name='review')

        #: Then
        assert result.violations == (), 'all six fields of the specification are accepted'

    def test_validate_skill_without_a_frontmatter_block_reports_it_missing_on_line_one(self) -> None:
        #: Given
        frontmatter = parse_frontmatter('# Review\n')

        #: When
        result = validate_skill(SKILL_FRONTMATTER_SCHEMA, frontmatter=frontmatter, directory_name='review')

        #: Then
        assert result.violations == (
            Violation(
                line=LineNumber(1), rule='skill.frontmatter-missing', message='no `---` delimited frontmatter block'
            ),
        ), 'a SKILL.md with no frontmatter block carries that one violation'

    def test_validate_skill_with_invalid_yaml_reports_it_unparseable(self) -> None:
        #: Given
        frontmatter = parse_frontmatter('---\nname: [review\n---\n')

        #: When
        result = validate_skill(SKILL_FRONTMATTER_SCHEMA, frontmatter=frontmatter, directory_name='review')

        #: Then
        assert [violation.rule for violation in result.violations] == ['skill.frontmatter-unparseable'], (
            'frontmatter that is not YAML is one violation, and no field is judged'
        )

    def test_validate_skill_with_a_non_mapping_block_reports_it_unparseable(self) -> None:
        #: Given
        frontmatter = parse_frontmatter('---\n- review\n---\n')

        #: When
        result = validate_skill(SKILL_FRONTMATTER_SCHEMA, frontmatter=frontmatter, directory_name='review')

        #: Then
        assert result.violations == (
            Violation(
                line=LineNumber(1), rule='skill.frontmatter-unparseable', message='frontmatter is not a YAML mapping'
            ),
        ), 'a YAML list is not the mapping a skill opens with'

    def test_validate_skill_without_the_required_fields_reports_each_on_line_one(self) -> None:
        #: Given
        frontmatter = parse_frontmatter('---\nlicense: MIT\n---\n')

        #: When
        result = validate_skill(SKILL_FRONTMATTER_SCHEMA, frontmatter=frontmatter, directory_name='review')

        #: Then
        assert result.violations == (
            Violation(line=LineNumber(1), rule='skill.name', message='`name` is required'),
            Violation(line=LineNumber(1), rule='skill.description', message='`description` is required'),
        ), 'each missing required field is its own violation, at line 1 since it has no line of its own'

    def test_validate_skill_with_a_malformed_name_reports_the_name_rule_on_the_name_line(self) -> None:
        #: Given
        frontmatter = parse_frontmatter('---\ndescription: Review a change\nname: Code--Review\n---\n')

        #: When
        result = validate_skill(SKILL_FRONTMATTER_SCHEMA, frontmatter=frontmatter, directory_name='Code--Review')

        #: Then
        assert [(violation.line, violation.rule) for violation in result.violations] == [
            (LineNumber(3), 'skill.name')
        ], 'a name the specification rejects is reported where it is written'

    def test_validate_skill_with_a_name_unlike_the_directory_reports_the_directory_rule(self) -> None:
        #: Given
        frontmatter = parse_frontmatter('---\nname: review\ndescription: Review a change\n---\n')

        #: When
        result = validate_skill(SKILL_FRONTMATTER_SCHEMA, frontmatter=frontmatter, directory_name='audit')

        #: Then
        assert result.violations == (
            Violation(
                line=LineNumber(2),
                rule='skill.name-matches-directory',
                message="`name` is 'review'; expected 'audit', the name of the skill directory",
            ),
        ), 'a valid name that differs from the directory is the one violation'

    def test_validate_skill_with_a_field_outside_the_specification_reports_it_unknown(self) -> None:
        #: Given
        frontmatter = parse_frontmatter('---\nname: review\ndescription: Review a change\nmodel: opus\n---\n')

        #: When
        result = validate_skill(SKILL_FRONTMATTER_SCHEMA, frontmatter=frontmatter, directory_name='review')

        #: Then
        assert result.violations == (
            Violation(
                line=LineNumber(4),
                rule='skill.unknown-field',
                message='`model` is not a field of the Agent Skills specification',
            ),
        ), 'a field an agent adds beyond the specification is refused, on its own line'

    def test_validate_skill_with_a_key_that_is_not_a_string_reports_it_unknown_on_line_one(self) -> None:
        #: Given
        frontmatter = parse_frontmatter('---\nname: review\ndescription: Review a change\n123: opus\n---\n')

        #: When
        result = validate_skill(SKILL_FRONTMATTER_SCHEMA, frontmatter=frontmatter, directory_name='review')

        #: Then
        assert result.violations == (
            Violation(
                line=LineNumber(1),
                rule='skill.unknown-field',
                message='a key that is not a string is not a field of the Agent Skills specification',
            ),
        ), 'a key YAML decodes to a number is no field, and has no recorded line, so it is reported on line 1'

    def test_validate_skill_with_a_non_string_metadata_value_reports_the_metadata_rule(self) -> None:
        #: Given
        frontmatter = parse_frontmatter(
            '---\nname: review\ndescription: Review a change\nmetadata:\n  version: 1.0\n---\n'
        )

        #: When
        result = validate_skill(SKILL_FRONTMATTER_SCHEMA, frontmatter=frontmatter, directory_name='review')

        #: Then
        assert result.violations == (
            Violation(
                line=LineNumber(4),
                rule='skill.metadata',
                message='`metadata.version` must be a string',
            ),
        ), 'the violation names the nested key and sits on the line of the field that holds it'

    def test_validate_skill_with_a_name_that_is_not_a_string_reports_no_directory_rule(self) -> None:
        #: Given
        frontmatter = parse_frontmatter('---\nname: 3\ndescription: Review a change\n---\n')

        #: When
        result = validate_skill(SKILL_FRONTMATTER_SCHEMA, frontmatter=frontmatter, directory_name='review')

        #: Then
        assert [violation.rule for violation in result.violations] == ['skill.name'], (
            'a name of the wrong type is the specification violation alone: there is no name to compare'
        )

    def test_validate_skill_with_a_name_unlike_the_directory_and_an_unknown_field_reports_the_name_first(self) -> None:
        #: Given
        frontmatter = parse_frontmatter('---\nmodel: opus\nname: review\ndescription: Review a change\n---\n')

        #: When
        result = validate_skill(SKILL_FRONTMATTER_SCHEMA, frontmatter=frontmatter, directory_name='audit')

        #: Then
        assert [violation.rule for violation in result.violations] == [
            'skill.name-matches-directory',
            'skill.unknown-field',
        ], 'the name is compared before the specification is applied, as in the frontmatter check'

    def test_validate_skill_with_a_key_repeated_with_the_same_value_reports_the_repetition(self) -> None:
        #: Given
        frontmatter = parse_frontmatter('---\nname: review\ndescription: Review a change\nname: review\n---\n')

        #: When
        result = validate_skill(SKILL_FRONTMATTER_SCHEMA, frontmatter=frontmatter, directory_name='review')

        #: Then
        assert result.violations == (
            Violation(
                line=LineNumber(4),
                rule='skill.duplicate-key',
                message="'name' is already written on line 2",
            ),
        ), 'a key written twice is a finding on the repeated line, even when both values agree'

    def test_validate_skill_with_a_key_repeated_with_another_value_reports_the_repetition(self) -> None:
        #: Given
        frontmatter = parse_frontmatter(
            '---\nname: review\ndescription: Review a change\ndescription: Audit a change\n---\n'
        )

        #: When
        result = validate_skill(SKILL_FRONTMATTER_SCHEMA, frontmatter=frontmatter, directory_name='review')

        #: Then
        assert result.violations == (
            Violation(
                line=LineNumber(4),
                rule='skill.duplicate-key',
                message="'description' is already written on line 3",
            ),
        ), 'a key written twice with another value is a finding on the line whose value is kept'

    def test_validate_skill_with_a_key_written_three_times_points_each_repetition_at_the_first(self) -> None:
        #: Given
        frontmatter = parse_frontmatter(
            '---\nname: review\nname: review\nname: review\ndescription: Review a change\n---\n'
        )

        #: When
        result = validate_skill(SKILL_FRONTMATTER_SCHEMA, frontmatter=frontmatter, directory_name='review')

        #: Then
        assert result.violations == (
            Violation(
                line=LineNumber(3),
                rule='skill.duplicate-key',
                message="'name' is already written on line 2",
            ),
            Violation(
                line=LineNumber(4),
                rule='skill.duplicate-key',
                message="'name' is already written on line 2",
            ),
        ), 'each later occurrence is its own finding, and each names the line of the first'

    def test_validate_skill_with_the_wrong_name_written_last_reports_it_on_the_last_line(self) -> None:
        #: Given
        frontmatter = parse_frontmatter('---\nname: review\ndescription: Review a change\nname: audit\n---\n')

        #: When
        result = validate_skill(SKILL_FRONTMATTER_SCHEMA, frontmatter=frontmatter, directory_name='review')

        #: Then
        assert result.violations == (
            Violation(
                line=LineNumber(4),
                rule='skill.name-matches-directory',
                message="`name` is 'audit'; expected 'review', the name of the skill directory",
            ),
            Violation(
                line=LineNumber(4),
                rule='skill.duplicate-key',
                message="'name' is already written on line 2",
            ),
        ), 'the name the decoder kept is judged on the line it is written on, and the repetition is reported last'

    def test_validate_skill_with_the_right_name_written_last_reports_only_the_repetition(self) -> None:
        #: Given
        frontmatter = parse_frontmatter('---\nname: audit\ndescription: Review a change\nname: review\n---\n')

        #: When
        result = validate_skill(SKILL_FRONTMATTER_SCHEMA, frontmatter=frontmatter, directory_name='review')

        #: Then
        assert result.violations == (
            Violation(
                line=LineNumber(4),
                rule='skill.duplicate-key',
                message="'name' is already written on line 2",
            ),
        ), 'the decoder kept the right name, so the overwritten wrong one is reported only as a repetition'

    def test_validate_skill_with_a_bad_value_written_last_reports_it_on_the_last_line(self) -> None:
        #: Given
        frontmatter = parse_frontmatter('---\nname: review\ndescription: fine\ndescription: ""\n---\n')

        #: When
        result = validate_skill(SKILL_FRONTMATTER_SCHEMA, frontmatter=frontmatter, directory_name='review')

        #: Then
        assert result.violations == (
            Violation(line=LineNumber(4), rule='skill.description', message='skill description cannot be empty'),
            Violation(
                line=LineNumber(4),
                rule='skill.duplicate-key',
                message="'description' is already written on line 3",
            ),
        ), 'the specification judges the value the decoder kept, on the line it is written on, before the repetition'

    def test_validate_skill_with_a_good_value_written_last_reports_only_the_repetition(self) -> None:
        #: Given
        frontmatter = parse_frontmatter('---\nname: review\ndescription: ""\ndescription: fine\n---\n')

        #: When
        result = validate_skill(SKILL_FRONTMATTER_SCHEMA, frontmatter=frontmatter, directory_name='review')

        #: Then
        assert result.violations == (
            Violation(
                line=LineNumber(4),
                rule='skill.duplicate-key',
                message="'description' is already written on line 3",
            ),
        ), 'the decoder kept the good value, so the overwritten bad one is reported only as a repetition'

    def test_validate_skill_with_an_unknown_key_repeated_reports_it_on_the_last_line(self) -> None:
        #: Given
        frontmatter = parse_frontmatter('---\nname: review\ndescription: Review a change\nmodel: a\nmodel: b\n---\n')

        #: When
        result = validate_skill(SKILL_FRONTMATTER_SCHEMA, frontmatter=frontmatter, directory_name='review')

        #: Then
        assert result.violations == (
            Violation(
                line=LineNumber(5),
                rule='skill.unknown-field',
                message='`model` is not a field of the Agent Skills specification',
            ),
            Violation(
                line=LineNumber(5),
                rule='skill.duplicate-key',
                message="'model' is already written on line 4",
            ),
        ), 'an unknown key written twice is reported once, on its last line, before the repetition'

    def test_validate_skill_with_a_merge_overriding_a_written_key_reports_no_repetition(self) -> None:
        #: Given
        frontmatter = parse_frontmatter(
            '---\nname: review\ndescription: Review a change\n<<: {name: other, license: MIT}\n---\n'
        )

        #: When
        result = validate_skill(SKILL_FRONTMATTER_SCHEMA, frontmatter=frontmatter, directory_name='review')

        #: Then
        assert result.violations == (), 'a key a merge supplies is not written twice, and the written name wins'

    def test_validate_skill_with_a_repeated_lone_surrogate_key_reports_it_escaped(self) -> None:
        #: Given
        frontmatter = parse_frontmatter(
            '---\nname: review\ndescription: Review a change\n"\\ud83d": a\n"\\ud83d": b\n---\n'
        )

        #: When
        result = validate_skill(SKILL_FRONTMATTER_SCHEMA, frontmatter=frontmatter, directory_name='review')

        #: Then
        assert result.violations == (
            Violation(
                line=LineNumber(1),
                rule='skill.frontmatter',
                message='the frontmatter does not satisfy the Agent Skills specification',
            ),
            Violation(
                line=LineNumber(5),
                rule='skill.duplicate-key',
                message="'\\ud83d' is already written on line 4",
            ),
        ), 'a key no terminal can print is named by its escape, so the repetition can be written out'

    def test_validate_skill_with_a_repeated_key_holding_a_newline_reports_it_on_one_line(self) -> None:
        #: Given
        frontmatter = parse_frontmatter(
            '---\nname: review\ndescription: Review a change\n"a\\nb": 1\n"a\\nb": 2\n---\n'
        )

        #: When
        result = validate_skill(SKILL_FRONTMATTER_SCHEMA, frontmatter=frontmatter, directory_name='review')

        #: Then
        assert result.violations == (
            Violation(
                line=LineNumber(5),
                rule='skill.unknown-field',
                message='`a\nb` is not a field of the Agent Skills specification',
            ),
            Violation(
                line=LineNumber(5),
                rule='skill.duplicate-key',
                message="'a\\nb' is already written on line 4",
            ),
        ), 'a newline in the key is printed as its escape, so the repetition stays on one line'

    def test_validate_skill_with_a_field_only_a_merge_supplies_reports_it_on_line_1(self) -> None:
        #: Given
        frontmatter = parse_frontmatter('---\nname: review\n<<: {description: ""}\n---\n')

        #: When
        result = validate_skill(SKILL_FRONTMATTER_SCHEMA, frontmatter=frontmatter, directory_name='review')

        #: Then
        assert result.violations == (
            Violation(line=LineNumber(1), rule='skill.description', message='skill description cannot be empty'),
        ), 'a field written only inside a merged mapping has no top-level line, so it is reported on line 1'
