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
    @pytest.mark.parametrize('length', (0, 499, 500))
    def test_check_with_a_value_within_the_recommendation_reports_nothing(self, length: int) -> None:
        #: Given
        value = 'A' * length
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

    @pytest.mark.parametrize('character', ('A', ' ', 'é'))
    def test_check_with_501_characters_reports_the_whole_value_length(self, character: str) -> None:
        #: Given
        value = character * 501
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
        ), 'all characters count, including whitespace, and Unicode characters count once rather than by bytes'

    @pytest.mark.parametrize(
        'text',
        (
            '# Review\n',
            UNCLOSED_SEQUENCE,
            SEQUENCE,
            NO_ALLOWED_TOOLS,
            NULL_ALLOWED_TOOLS,
            NUMBER_ALLOWED_TOOLS,
            LIST_ALLOWED_TOOLS,
        ),
    )
    def test_check_without_a_string_value_reports_nothing(self, text: str) -> None:
        #: Given
        subject = FakeSkillContext(text)

        #: When
        occurrences = AllowedToolsTooLong.check(subject)

        #: Then
        assert occurrences == (), 'missing, invalid and non-string frontmatter is left to its own rules'

    def test_message_names_the_length_and_recommendation(self) -> None:
        #: Given
        occurrence = AllowedToolsTooLong(line=LineNumber(NonZeroUnsignedInt(4)), overrun=overrun(501, 500))

        #: When
        message = occurrence.message()

        #: Then
        assert message == '`allowed-tools` value too long (501 > 500)', 'the value and recommendation are explicit'

    def test_labels_name_what_is_over_the_recommendation_on_the_field_line(self) -> None:
        #: Given
        occurrence = AllowedToolsTooLong(line=LineNumber(NonZeroUnsignedInt(4)), overrun=overrun(520, 500))

        #: When
        labels = occurrence.labels()

        #: Then
        assert labels == (Label(Here(LineNumber(NonZeroUnsignedInt(4))), 'characters over the recommended length'),), (
            'the label names what overruns and carries no number: the message has it'
        )

    def test_children_say_how_to_shorten_the_value_and_where_the_limit_comes_from(self) -> None:
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
