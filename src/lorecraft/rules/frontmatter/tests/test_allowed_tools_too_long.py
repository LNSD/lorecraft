"""`FM012`, `allowed-tools-too-long`, over a skill's whole allowed-tools value."""

import pytest

from lorecraft.project.syntax import LineNumber
from lorecraft.rules.tests.fake_context import FakeSkillContext

from ..allowed_tools_too_long import AllowedToolsTooLong


@pytest.mark.unit
class TestAllowedToolsTooLong:
    @pytest.mark.parametrize('length', (0, 499, 500))
    def test_check_with_a_value_within_the_recommendation_reports_nothing(self, length: int) -> None:
        #: Given
        value = 'A' * length
        subject = FakeSkillContext(f'---\nname: review\ndescription: Review a change.\nallowed-tools: "{value}"\n---\n')

        #: When
        occurrences = AllowedToolsTooLong.check(subject)

        #: Then
        assert occurrences == (), 'the recommendation includes exactly 500 characters'

    @pytest.mark.parametrize('character', ('A', ' ', 'é'))
    def test_check_with_501_characters_reports_the_whole_value_length(self, character: str) -> None:
        #: Given
        value = character * 501
        subject = FakeSkillContext(f'---\nname: review\ndescription: Review a change.\nallowed-tools: "{value}"\n---\n')

        #: When
        occurrences = AllowedToolsTooLong.check(subject)

        #: Then
        assert occurrences == (AllowedToolsTooLong(line=LineNumber.from_int(4), character_count=501),), (
            'all characters count, including whitespace, and Unicode characters count once rather than by bytes'
        )

    @pytest.mark.parametrize(
        'text',
        (
            '# Review\n',
            '---\n[\n---\n',
            '---\n- review\n---\n',
            '---\nname: review\ndescription: Review a change.\n---\n',
            '---\nallowed-tools: null\n---\n',
            '---\nallowed-tools: 501\n---\n',
            '---\nallowed-tools: [Read, Grep]\n---\n',
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
        occurrence = AllowedToolsTooLong(line=LineNumber.from_int(4), character_count=501)

        #: When
        message = occurrence.message()

        #: Then
        assert message == '`allowed-tools` value too long (501 > 500)', 'the value and recommendation are explicit'

    def test_labels_and_children_are_empty(self) -> None:
        #: Given
        occurrence = AllowedToolsTooLong(line=LineNumber.from_int(4), character_count=501)

        #: When
        labels = occurrence.labels()
        children = occurrence.children()

        #: Then
        assert (labels, children) == ((), ()), 'the recommendation has no external specification or extra location'
