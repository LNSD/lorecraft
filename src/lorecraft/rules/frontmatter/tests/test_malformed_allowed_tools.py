"""`FM011`, `malformed-allowed-tools`, over a skill's `allowed-tools` frontmatter field."""

from typing import Final

import pytest

from lorecraft.project.syntax import LineNumber
from lorecraft.rules.location import Help, Here, Label, Note
from lorecraft.rules.tests.fake_context import FakeSkillContext

from ..malformed_allowed_tools import (
    CommaSeparated,
    EmptyValue,
    MalformedAllowedTools,
    NotATool,
    UnbalancedParentheses,
)

SPECIFICATION_NOTE: Final[Note] = Note(
    "the Agent Skills specification's experimental `allowed-tools` field: "
    'https://agentskills.io/specification#allowed-tools-field'
)
"""The note naming where the specification states the field, which both skill rules of the group carry."""


def _skill_allowing(value: str) -> FakeSkillContext:
    """A skill whose `allowed-tools`, on line 4, holds the value."""
    return FakeSkillContext(f'---\nname: review\ndescription: Review a change.\nallowed-tools: "{value}"\n---\n')


@pytest.mark.unit
class TestMalformedAllowedTools:
    def test_check_with_comma_separator_reports_the_bad_entry_and_accepts_pattern_comma(self) -> None:
        #: Given
        subject = FakeSkillContext(
            '---\nname: review\ndescription: Review a change.\nallowed-tools: Read, Bash(git log --format=%h,%s)\n---\n'
        )

        #: When
        occurrences = MalformedAllowedTools.check(subject)

        #: Then
        assert occurrences == (
            MalformedAllowedTools(line=LineNumber.from_int(4), problem=CommaSeparated(entry='Read,', suggested='Read')),
        ), 'a comma between tools is invalid, while commas inside the pattern stay inside the entry'

    def test_check_with_an_unbalanced_pattern_reports_the_whole_entry(self) -> None:
        #: Given
        subject = FakeSkillContext(
            '---\nname: review\ndescription: Review a change.\nallowed-tools: Bash(git diff *\n---\n'
        )

        #: When
        occurrences = MalformedAllowedTools.check(subject)

        #: Then
        assert occurrences == (
            MalformedAllowedTools(line=LineNumber.from_int(4), problem=UnbalancedParentheses('Bash(git diff *')),
        ), 'an unclosed pattern consumes the rest of the value as one malformed entry'

    def test_check_with_text_after_a_pattern_reports_the_entry(self) -> None:
        #: Given
        subject = FakeSkillContext(
            '---\nname: review\ndescription: Review a change.\nallowed-tools: Bash(git *)tail\n---\n'
        )

        #: When
        occurrences = MalformedAllowedTools.check(subject)

        #: Then
        assert occurrences == (
            MalformedAllowedTools(line=LineNumber.from_int(4), problem=NotATool('Bash(git *)tail')),
        ), 'text after the closing parenthesis is not another tool entry'

    def test_check_with_empty_value_reports_it(self) -> None:
        #: Given
        subject = FakeSkillContext('---\nname: review\ndescription: Review a change.\nallowed-tools: "  "\n---\n')

        #: When
        occurrences = MalformedAllowedTools.check(subject)

        #: Then
        assert occurrences == (MalformedAllowedTools(line=LineNumber.from_int(4), problem=EmptyValue()),), (
            'a whitespace-only value has no tool entries'
        )

    @pytest.mark.parametrize(
        'value',
        (
            'Read Bash(git log --format=%h,%s)',
            'Bash(git *) Read',
            'Bash() Read',
            'Read Grep',
        ),
    )
    def test_check_with_a_well_formed_list_reports_nothing(self, value: str) -> None:
        #: Given
        subject = FakeSkillContext(f'---\nname: review\ndescription: Review a change.\nallowed-tools: "{value}"\n---\n')

        #: When
        occurrences = MalformedAllowedTools.check(subject)

        #: Then
        assert occurrences == (), 'tool names and one balanced parenthesised pattern form a list'

    def test_check_with_no_field_reports_nothing(self) -> None:
        #: Given
        subject = FakeSkillContext('---\nname: review\ndescription: Review a change.\n---\n')

        #: When
        occurrences = MalformedAllowedTools.check(subject)

        #: Then
        assert occurrences == (), 'the optional field may be absent'

    def test_check_with_commas_between_tools_suggests_spaces(self) -> None:
        #: Given
        subject = _skill_allowing('Read,Grep')

        #: When
        occurrences = MalformedAllowedTools.check(subject)

        #: Then
        assert occurrences == (
            MalformedAllowedTools(
                line=LineNumber.from_int(4), problem=CommaSeparated(entry='Read,Grep', suggested='Read Grep')
            ),
        ), 'a comma between tools becomes a space in the suggestion'

    def test_check_with_a_comma_inside_a_pattern_keeps_it_in_the_suggestion(self) -> None:
        #: Given
        subject = _skill_allowing('Read,Bash(a,b)')

        #: When
        occurrences = MalformedAllowedTools.check(subject)

        #: Then
        assert occurrences == (
            MalformedAllowedTools(
                line=LineNumber.from_int(4),
                problem=CommaSeparated(entry='Read,Bash(a,b)', suggested='Read Bash(a,b)'),
            ),
        ), 'a comma inside parentheses belongs to the pattern, so only the one between the tools is replaced'

    def test_check_with_a_comma_after_a_pattern_suggests_a_space(self) -> None:
        #: Given
        subject = _skill_allowing('Bash(git diff),Read')

        #: When
        occurrences = MalformedAllowedTools.check(subject)

        #: Then
        assert occurrences == (
            MalformedAllowedTools(
                line=LineNumber.from_int(4),
                problem=CommaSeparated(entry='Bash(git diff),Read', suggested='Bash(git diff) Read'),
            ),
        ), 'a comma after the closing parenthesis separates tools, so the suggestion differs from the entry'

    def test_check_with_a_lone_comma_reports_it_as_not_a_tool(self) -> None:
        #: Given
        subject = _skill_allowing(',')

        #: When
        occurrences = MalformedAllowedTools.check(subject)

        #: Then
        assert occurrences == (MalformedAllowedTools(line=LineNumber.from_int(4), problem=NotATool(entry=',')),), (
            'a comma alone leaves nothing to suggest'
        )

    def test_check_with_only_a_comma_inside_parentheses_reports_it_as_not_a_tool(self) -> None:
        #: Given
        subject = _skill_allowing('(a,b)')

        #: When
        occurrences = MalformedAllowedTools.check(subject)

        #: Then
        assert occurrences == (MalformedAllowedTools(line=LineNumber.from_int(4), problem=NotATool(entry='(a,b)')),), (
            'the comma belongs to the pattern, so spacing the commas would suggest the entry unchanged'
        )

    def test_check_with_a_tool_glued_to_a_pattern_reports_it_as_not_a_tool(self) -> None:
        #: Given
        subject = _skill_allowing('Bash(a)Read')

        #: When
        occurrences = MalformedAllowedTools.check(subject)

        #: Then
        assert occurrences == (
            MalformedAllowedTools(line=LineNumber.from_int(4), problem=NotATool(entry='Bash(a)Read')),
        ), 'a balanced suffix with no comma between tools has no correction to suggest'

    def test_check_with_an_unclosed_parenthesis_reports_it_as_unbalanced(self) -> None:
        #: Given
        subject = _skill_allowing('(a')

        #: When
        occurrences = MalformedAllowedTools.check(subject)

        #: Then
        assert occurrences == (
            MalformedAllowedTools(line=LineNumber.from_int(4), problem=UnbalancedParentheses(entry='(a')),
        ), 'an entry that opens a pattern without closing it is unbalanced'

    def test_message_says_the_field_is_not_a_list_of_tool_entries(self) -> None:
        #: Given
        occurrence = MalformedAllowedTools(
            line=LineNumber.from_int(4), problem=CommaSeparated(entry='Read,', suggested='Read')
        )

        #: When
        message = occurrence.message()

        #: Then
        assert message == '`allowed-tools` is not a list of tool entries', (
            'the message is one template, for an empty value too; the label names the entry'
        )

    def test_labels_with_a_comma_separated_entry_name_it_on_the_field_line(self) -> None:
        #: Given
        occurrence = MalformedAllowedTools(
            line=LineNumber.from_int(4), problem=CommaSeparated(entry='Read,', suggested='Read')
        )

        #: When
        labels = occurrence.labels()

        #: Then
        assert labels == (Label(Here(LineNumber.from_int(4)), '`Read,` is not `Tool` or `Tool(pattern)`'),), (
            'the label names the entry as read from the field'
        )

    def test_labels_with_an_unbalanced_entry_name_it_on_the_field_line(self) -> None:
        #: Given
        occurrence = MalformedAllowedTools(line=LineNumber.from_int(4), problem=UnbalancedParentheses(entry='Bash(a'))

        #: When
        labels = occurrence.labels()

        #: Then
        assert labels == (Label(Here(LineNumber.from_int(4)), '`Bash(a` is not `Tool` or `Tool(pattern)`'),), (
            'the label names the entry as read from the field'
        )

    def test_labels_with_a_non_tool_entry_name_it_on_the_field_line(self) -> None:
        #: Given
        occurrence = MalformedAllowedTools(line=LineNumber.from_int(4), problem=NotATool(entry='Bash(a)b'))

        #: When
        labels = occurrence.labels()

        #: Then
        assert labels == (Label(Here(LineNumber.from_int(4)), '`Bash(a)b` is not `Tool` or `Tool(pattern)`'),), (
            'the label names the entry as read from the field'
        )

    def test_labels_with_an_empty_value_say_no_tool_is_written(self) -> None:
        #: Given
        occurrence = MalformedAllowedTools(line=LineNumber.from_int(4), problem=EmptyValue())

        #: When
        labels = occurrence.labels()

        #: Then
        assert labels == (Label(Here(LineNumber.from_int(4)), 'no tool is written here'),), (
            'an empty value has no entry to name'
        )

    def test_children_with_an_empty_value_say_to_write_tools_or_remove_the_field(self) -> None:
        #: Given
        occurrence = MalformedAllowedTools(line=LineNumber.from_int(4), problem=EmptyValue())

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            SPECIFICATION_NOTE,
            Help('write one or more tool names separated by spaces, or remove `allowed-tools`'),
        ), 'the note points to the specification and the help says how to fill or drop the field'

    def test_children_with_a_comma_separated_entry_give_the_corrected_value(self) -> None:
        #: Given
        problem = CommaSeparated(entry='Read,Grep', suggested='Read Grep')
        occurrence = MalformedAllowedTools(line=LineNumber.from_int(4), problem=problem)

        #: When
        children = occurrence.children()

        #: Then
        assert children == (SPECIFICATION_NOTE, Help('write `Read Grep`')), (
            'the note points to the specification and the help gives the corrected value'
        )

    def test_children_with_an_unbalanced_entry_say_to_balance_the_parentheses(self) -> None:
        #: Given
        occurrence = MalformedAllowedTools(line=LineNumber.from_int(4), problem=UnbalancedParentheses(entry='Bash(a'))

        #: When
        children = occurrence.children()

        #: Then
        assert children == (SPECIFICATION_NOTE, Help('balance the parentheses around the pattern')), (
            'the note points to the specification and the help fixes the parentheses'
        )

    def test_children_with_a_non_tool_entry_say_to_write_a_tool_or_a_tool_with_a_pattern(self) -> None:
        #: Given
        occurrence = MalformedAllowedTools(line=LineNumber.from_int(4), problem=NotATool(entry='Bash(a)b'))

        #: When
        children = occurrence.children()

        #: Then
        assert children == (SPECIFICATION_NOTE, Help('write the entry as `Tool` or `Tool(pattern)`')), (
            'the note points to the specification and the help names the two shapes an entry may have'
        )
