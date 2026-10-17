"""`FM012`, `allowed-tools-too-long`, over a skill's whole allowed-tools value."""

from textwrap import dedent
from typing import Final

import pytest

from lib.overruns import overrun
from lorecraft.core.num import NonZeroUnsignedInt
from lorecraft.project.syntax import LineNumber
from lorecraft.rules.location import Help, Here, Label, Note
from lorecraft.rules.tests.fake_database import FakeSkillDatabase, judged

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
        subject = FakeSkillDatabase(text)

        #: When
        occurrences = judged(AllowedToolsTooLong, subject)

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
        subject = FakeSkillDatabase(text)

        #: When
        occurrences = judged(AllowedToolsTooLong, subject)

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
        subject = FakeSkillDatabase(text)

        #: When
        occurrences = judged(AllowedToolsTooLong, subject)

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
        subject = FakeSkillDatabase(text)

        #: When
        occurrences = judged(AllowedToolsTooLong, subject)

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
        subject = FakeSkillDatabase(text)

        #: When
        occurrences = judged(AllowedToolsTooLong, subject)

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
        subject = FakeSkillDatabase(text)

        #: When
        occurrences = judged(AllowedToolsTooLong, subject)

        #: Then
        assert occurrences == (
            AllowedToolsTooLong(line=LineNumber(NonZeroUnsignedInt(4)), overrun=overrun(501, 500)),
        ), 'Unicode characters count once rather than by bytes'

    def test_check_with_no_frontmatter_reports_nothing(self) -> None:
        #: Given
        subject = FakeSkillDatabase('# Review\n')

        #: When
        occurrences = judged(AllowedToolsTooLong, subject)

        #: Then
        assert occurrences == (), 'missing, invalid and non-string frontmatter is left to its own rules'

    def test_check_with_invalid_yaml_frontmatter_reports_nothing(self) -> None:
        #: Given
        subject = FakeSkillDatabase(UNCLOSED_SEQUENCE)

        #: When
        occurrences = judged(AllowedToolsTooLong, subject)

        #: Then
        assert occurrences == (), 'missing, invalid and non-string frontmatter is left to its own rules'

    def test_check_with_a_sequence_as_frontmatter_reports_nothing(self) -> None:
        #: Given
        subject = FakeSkillDatabase(SEQUENCE)

        #: When
        occurrences = judged(AllowedToolsTooLong, subject)

        #: Then
        assert occurrences == (), 'missing, invalid and non-string frontmatter is left to its own rules'

    def test_check_with_no_allowed_tools_reports_nothing(self) -> None:
        #: Given
        subject = FakeSkillDatabase(NO_ALLOWED_TOOLS)

        #: When
        occurrences = judged(AllowedToolsTooLong, subject)

        #: Then
        assert occurrences == (), 'missing, invalid and non-string frontmatter is left to its own rules'

    def test_check_with_a_null_allowed_tools_reports_nothing(self) -> None:
        #: Given
        subject = FakeSkillDatabase(NULL_ALLOWED_TOOLS)

        #: When
        occurrences = judged(AllowedToolsTooLong, subject)

        #: Then
        assert occurrences == (), 'missing, invalid and non-string frontmatter is left to its own rules'

    def test_check_with_a_number_as_allowed_tools_reports_nothing(self) -> None:
        #: Given
        subject = FakeSkillDatabase(NUMBER_ALLOWED_TOOLS)

        #: When
        occurrences = judged(AllowedToolsTooLong, subject)

        #: Then
        assert occurrences == (), 'missing, invalid and non-string frontmatter is left to its own rules'

    def test_check_with_a_list_as_allowed_tools_reports_nothing(self) -> None:
        #: Given
        subject = FakeSkillDatabase(LIST_ALLOWED_TOOLS)

        #: When
        occurrences = judged(AllowedToolsTooLong, subject)

        #: Then
        assert occurrences == (), 'missing, invalid and non-string frontmatter is left to its own rules'

    def test_message_names_the_length_and_recommendation(self) -> None:
        #: Given
        occurrence = AllowedToolsTooLong(line=LineNumber(NonZeroUnsignedInt(4)), overrun=overrun(501, 500))

        #: When
        message = occurrence.message()

        #: Then
        assert message == '`allowed-tools` value too long (501 > 500)', 'the value and recommendation are explicit'

    def test_labels_name_the_characters_over_the_recommendation_on_the_field_line(self) -> None:
        #: Given
        occurrence = AllowedToolsTooLong(line=LineNumber(NonZeroUnsignedInt(4)), overrun=overrun(520, 500))

        #: When
        labels = occurrence.labels()

        #: Then
        assert labels == (
            Label(Here(LineNumber(NonZeroUnsignedInt(4))), 'characters over the recommended length: 20'),
        ), 'the label names what overruns and how far: 520 is 20 past 500'

    def test_children_say_how_to_shorten_the_value_and_where_the_limit_comes_from(
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
