"""`FM011`, `malformed-allowed-tools`, over a skill's `allowed-tools` frontmatter field."""

import pytest

from lorecraft.project.syntax import LineNumber
from lorecraft.rules.location import Help, Note
from lorecraft.rules.tests.fake_context import FakeSkillContext

from ..malformed_allowed_tools import MalformedAllowedTools, MalformedAllowedToolsProblem


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
            MalformedAllowedTools(
                line=LineNumber.from_int(4), entry='Read,', problem=MalformedAllowedToolsProblem.COMMA
            ),
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
            MalformedAllowedTools(
                line=LineNumber.from_int(4), entry='Bash(git diff *', problem=MalformedAllowedToolsProblem.PARENTHESES
            ),
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
            MalformedAllowedTools(
                line=LineNumber.from_int(4), entry='Bash(git *)tail', problem=MalformedAllowedToolsProblem.ENTRY
            ),
        ), 'text after the closing parenthesis is not another tool entry'

    def test_check_with_empty_value_reports_it(self) -> None:
        #: Given
        subject = FakeSkillContext('---\nname: review\ndescription: Review a change.\nallowed-tools: "  "\n---\n')

        #: When
        occurrences = MalformedAllowedTools.check(subject)

        #: Then
        assert occurrences == (
            MalformedAllowedTools(line=LineNumber.from_int(4), entry='', problem=MalformedAllowedToolsProblem.EMPTY),
        ), 'a whitespace-only value has no tool entries'

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

    def test_message_quotes_the_malformed_entry(self) -> None:
        #: Given
        occurrence = MalformedAllowedTools(
            line=LineNumber.from_int(4), entry='Read,', problem=MalformedAllowedToolsProblem.COMMA
        )

        #: When
        message = occurrence.message()

        #: Then
        assert message == "malformed `allowed-tools` entry 'Read,'", 'the whole bad entry is quoted'

    def test_labels_are_empty_and_children_name_the_specification_and_fix(self) -> None:
        #: Given
        occurrence = MalformedAllowedTools(
            line=LineNumber.from_int(4), entry='Read,', problem=MalformedAllowedToolsProblem.COMMA
        )

        #: When
        labels = occurrence.labels()
        children = occurrence.children()

        #: Then
        assert labels == (), 'the field line is the primary location and needs no duplicate label'
        assert children == (
            Note(
                "the Agent Skills specification's experimental `allowed-tools` field: "
                'https://agentskills.io/specification#allowed-tools-field'
            ),
            Help('separate tools with spaces, not commas'),
        ), 'the note points to the specification and the help fixes this entry'
