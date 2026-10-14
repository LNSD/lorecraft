"""`FM012`, `allowed-tools-too-long`, over a skill's whole allowed-tools value."""

from textwrap import dedent
from typing import Final

import pytest

from lib.overruns import overrun
from lorecraft.core.num import NonZeroUnsignedInt
from lorecraft.project.syntax import LineNumber
from lorecraft.rules.location import Help, Here, Label, Note
from lorecraft.rules.tests.fake_context import FakeSkillContext

from ..allowed_tools_too_long import AllowedToolsTooLong
from .test_malformed_allowed_tools import SPECIFICATION_NOTE

UNCLOSED_SEQUENCE: Final[str] = dedent("""\
    ---
    [
    ---
    """)
"""A frontmatter block that is not valid YAML."""

SEQUENCE: Final[str] = dedent("""\
    ---
    - review
    ---
    """)
"""A frontmatter block that is a sequence, not a mapping."""

NO_ALLOWED_TOOLS: Final[str] = dedent("""\
    ---
    name: review
    description: Review a change.
    ---
    """)
"""A skill whose frontmatter has no `allowed-tools`."""

NULL_ALLOWED_TOOLS: Final[str] = dedent("""\
    ---
    allowed-tools: null
    ---
    """)
"""A skill whose `allowed-tools` is null."""

NUMBER_ALLOWED_TOOLS: Final[str] = dedent("""\
    ---
    allowed-tools: 501
    ---
    """)
"""A skill whose `allowed-tools` is a number."""

LIST_ALLOWED_TOOLS: Final[str] = dedent("""\
    ---
    allowed-tools: [Read, Grep]
    ---
    """)
"""A skill whose `allowed-tools` is a list."""


@pytest.mark.unit
class TestAllowedToolsTooLong:
    def test_check_with_a_value_of_zero_characters_reports_nothing(self) -> None:
        #: Given
        value = ''
        text = dedent(f"""\
            ---
            name: review
            description: Review a change.
            allowed-tools: "{value}"
            ---
            """)
        subject = FakeSkillContext(text)

        #: When
        occurrences = AllowedToolsTooLong.check(subject)

        #: Then
        assert occurrences == (), 'an empty value is within the recommendation'

    def test_check_with_a_value_of_499_characters_reports_nothing(self) -> None:
        #: Given
        value = 'A' * 499
        text = dedent(f"""\
            ---
            name: review
            description: Review a change.
            allowed-tools: "{value}"
            ---
            """)
        subject = FakeSkillContext(text)

        #: When
        occurrences = AllowedToolsTooLong.check(subject)

        #: Then
        assert occurrences == (), 'a value one under the recommendation is within it'

    def test_check_with_a_value_of_500_characters_reports_nothing(self) -> None:
        #: Given
        value = 'A' * 500
        text = dedent(f"""\
            ---
            name: review
            description: Review a change.
            allowed-tools: "{value}"
            ---
            """)
        subject = FakeSkillContext(text)

        #: When
        occurrences = AllowedToolsTooLong.check(subject)

        #: Then
        assert occurrences == (), 'the recommendation includes exactly 500 characters'

    def test_check_with_501_letters_reports_the_whole_value_length(self) -> None:
        #: Given
        value = 'A' * 501
        text = dedent(f"""\
            ---
            name: review
            description: Review a change.
            allowed-tools: "{value}"
            ---
            """)
        subject = FakeSkillContext(text)

        #: When
        occurrences = AllowedToolsTooLong.check(subject)

        #: Then
        assert occurrences == (
            AllowedToolsTooLong(line=LineNumber(NonZeroUnsignedInt(4)), overrun=overrun(501, 500)),
        ), 'every character counts toward the length'

    def test_check_with_501_spaces_reports_the_whole_value_length(self) -> None:
        #: Given
        value = ' ' * 501
        text = dedent(f"""\
            ---
            name: review
            description: Review a change.
            allowed-tools: "{value}"
            ---
            """)
        subject = FakeSkillContext(text)

        #: When
        occurrences = AllowedToolsTooLong.check(subject)

        #: Then
        assert occurrences == (
            AllowedToolsTooLong(line=LineNumber(NonZeroUnsignedInt(4)), overrun=overrun(501, 500)),
        ), 'whitespace counts toward the length'

    def test_check_with_501_accented_letters_reports_the_whole_value_length(self) -> None:
        #: Given
        value = 'é' * 501
        text = dedent(f"""\
            ---
            name: review
            description: Review a change.
            allowed-tools: "{value}"
            ---
            """)
        subject = FakeSkillContext(text)

        #: When
        occurrences = AllowedToolsTooLong.check(subject)

        #: Then
        assert occurrences == (
            AllowedToolsTooLong(line=LineNumber(NonZeroUnsignedInt(4)), overrun=overrun(501, 500)),
        ), 'Unicode characters count once rather than by bytes'

    def test_check_with_no_frontmatter_reports_nothing(self) -> None:
        #: Given
        subject = FakeSkillContext('# Review\n')

        #: When
        occurrences = AllowedToolsTooLong.check(subject)

        #: Then
        assert occurrences == (), 'missing, invalid and non-string frontmatter is left to its own rules'

    def test_check_with_invalid_yaml_frontmatter_reports_nothing(self) -> None:
        #: Given
        subject = FakeSkillContext(UNCLOSED_SEQUENCE)

        #: When
        occurrences = AllowedToolsTooLong.check(subject)

        #: Then
        assert occurrences == (), 'missing, invalid and non-string frontmatter is left to its own rules'

    def test_check_with_a_sequence_as_frontmatter_reports_nothing(self) -> None:
        #: Given
        subject = FakeSkillContext(SEQUENCE)

        #: When
        occurrences = AllowedToolsTooLong.check(subject)

        #: Then
        assert occurrences == (), 'missing, invalid and non-string frontmatter is left to its own rules'

    def test_check_with_no_allowed_tools_reports_nothing(self) -> None:
        #: Given
        subject = FakeSkillContext(NO_ALLOWED_TOOLS)

        #: When
        occurrences = AllowedToolsTooLong.check(subject)

        #: Then
        assert occurrences == (), 'missing, invalid and non-string frontmatter is left to its own rules'

    def test_check_with_a_null_allowed_tools_reports_nothing(self) -> None:
        #: Given
        subject = FakeSkillContext(NULL_ALLOWED_TOOLS)

        #: When
        occurrences = AllowedToolsTooLong.check(subject)

        #: Then
        assert occurrences == (), 'missing, invalid and non-string frontmatter is left to its own rules'

    def test_check_with_a_number_as_allowed_tools_reports_nothing(self) -> None:
        #: Given
        subject = FakeSkillContext(NUMBER_ALLOWED_TOOLS)

        #: When
        occurrences = AllowedToolsTooLong.check(subject)

        #: Then
        assert occurrences == (), 'missing, invalid and non-string frontmatter is left to its own rules'

    def test_check_with_a_list_as_allowed_tools_reports_nothing(self) -> None:
        #: Given
        subject = FakeSkillContext(LIST_ALLOWED_TOOLS)

        #: When
        occurrences = AllowedToolsTooLong.check(subject)

        #: Then
        assert occurrences == (), 'missing, invalid and non-string frontmatter is left to its own rules'

    def test_message_with_an_occurrence_names_the_length_and_recommendation(self) -> None:
        #: Given
        occurrence = AllowedToolsTooLong(line=LineNumber(NonZeroUnsignedInt(4)), overrun=overrun(501, 500))

        #: When
        message = occurrence.message()

        #: Then
        assert message == '`allowed-tools` value too long (501 > 500)', 'the value and recommendation are explicit'

    def test_labels_with_an_occurrence_name_what_is_over_the_recommendation_on_the_field_line(self) -> None:
        #: Given
        occurrence = AllowedToolsTooLong(line=LineNumber(NonZeroUnsignedInt(4)), overrun=overrun(520, 500))

        #: When
        labels = occurrence.labels()

        #: Then
        assert labels == (Label(Here(LineNumber(NonZeroUnsignedInt(4))), 'characters over the recommended length'),), (
            'the label names what overruns and carries no number: the message has it'
        )

    def test_children_with_an_occurrence_say_how_to_shorten_the_value_and_where_the_limit_comes_from(
        self,
    ) -> None:
        #: Given
        occurrence = AllowedToolsTooLong(line=LineNumber(NonZeroUnsignedInt(4)), overrun=overrun(501, 500))

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            SPECIFICATION_NOTE,
            Help(
                'keep only the tools the skill needs, and merge patterns such as '
                '`Bash(git diff *) Bash(git log *)` into `Bash(git *)`'
            ),
            Note(
                'Lorecraft recommends at most 500 characters, the `compatibility` limit; '
                'the Agent Skills specification sets none for `allowed-tools`'
            ),
        ), "the specification note, then the help, then the note that the limit is the package's"
