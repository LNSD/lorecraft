"""`LEN005`, `title-too-long`, over the character cap of a document's title.

Every case is a document written as text, read through a fake context that parses it as the real parser does, under
structure specifications decoded from JSON; no document is read from disk.
"""

from typing import Final

import pytest

from lorecraft.core.path import RootRelativePath
from lorecraft.project.syntax import LineNumber
from lorecraft.rules.location import Elsewhere, Help, Here, Label, Note
from lorecraft.rules.tests.fake_context import FakeDocumentContext, namespace_spec, structure_spec_path

from ..title_too_long import TitleTooLong

CORPUS_SPEC: Final[RootRelativePath] = structure_spec_path('guide')
"""The corpus structure specification."""

NAMESPACE_SPEC: Final[RootRelativePath] = structure_spec_path('guide-cli')
"""A namespace structure specification under the same corpus, which sets a title cap of its own."""

TEXT: Final[str] = '# Setting up the toolkit on a new machine\n\n## Run\n\nRun the toolkit over the repository.\n'
"""A document whose H1 title, on line 1, is of 39 characters, followed by one section."""

NO_CAP: Final[str] = '{"empty_sections": "forbidden"}'
"""A structure specification that sets no cap on the title."""


def _title_cap(chars: int) -> str:
    """A structure specification that caps the title's characters and states nothing else.

    Args:
        chars: The most characters the title may hold; at least 1.
    """
    return f'{{"title": {{"chars": {chars}}}}}'


@pytest.mark.unit
class TestTitleTooLong:
    def test_check_with_a_title_over_its_cap_reports_it_at_its_heading(self) -> None:
        #: Given
        subject = FakeDocumentContext(TEXT, corpus='guide', structure=_title_cap(30))

        #: When
        occurrences = TitleTooLong.check(subject)

        #: Then
        assert occurrences == (TitleTooLong(spec=CORPUS_SPEC, line=LineNumber.from_int(1), char_count=39, cap=30),), (
            'a title over its cap is one occurrence, at its heading, naming the specification that sets the cap'
        )

    def test_check_with_a_title_at_its_cap_reports_nothing(self) -> None:
        #: Given
        subject = FakeDocumentContext(TEXT, corpus='guide', structure=_title_cap(39))

        #: When
        occurrences = TitleTooLong.check(subject)

        #: Then
        assert occurrences == (), 'the cap is the most characters allowed, so a title at its cap fits it'

    def test_check_with_a_specification_setting_no_cap_reports_nothing(self) -> None:
        #: Given
        subject = FakeDocumentContext(TEXT, corpus='guide', structure=NO_CAP)

        #: When
        occurrences = TitleTooLong.check(subject)

        #: Then
        assert occurrences == (), 'a title no cap applies to may hold any number of characters'

    def test_check_with_a_document_without_a_title_reports_nothing(self) -> None:
        #: Given
        subject = FakeDocumentContext(
            '## Run\n\nRun the toolkit over the repository.\n', corpus='guide', structure=_title_cap(1)
        )

        #: When
        occurrences = TitleTooLong.check(subject)

        #: Then
        assert occurrences == (), 'a missing title is reported as missing alone, not as a title over its cap'

    def test_check_with_a_later_h1_over_the_cap_reports_nothing(self) -> None:
        #: Given
        text = '# Setup\n\nRun the toolkit over the repository.\n\n' + TEXT
        subject = FakeDocumentContext(text, corpus='guide', structure=_title_cap(30))

        #: When
        occurrences = TitleTooLong.check(subject)

        #: Then
        assert occurrences == (), 'only the first H1 is the title, so a later one over the cap is not held to it'

    def test_check_with_a_cap_set_by_the_namespace_alone_reports_it_under_the_namespace(self) -> None:
        #: Given
        subject = FakeDocumentContext(
            TEXT, corpus='guide', structure=NO_CAP, namespaces=(namespace_spec('guide', 'cli', _title_cap(35)),)
        )

        #: When
        occurrences = TitleTooLong.check(subject)

        #: Then
        assert occurrences == (
            TitleTooLong(spec=NAMESPACE_SPEC, line=LineNumber.from_int(1), char_count=39, cap=35),
        ), 'a cap is the specification that sets it, so it is reported under the namespace, not the corpus'

    def test_check_with_a_title_over_only_the_namespace_cap_reports_that_cap(self) -> None:
        #: Given
        subject = FakeDocumentContext(
            TEXT,
            corpus='guide',
            structure=_title_cap(60),
            namespaces=(namespace_spec('guide', 'cli', _title_cap(35)),),
        )

        #: When
        occurrences = TitleTooLong.check(subject)

        #: Then
        assert occurrences == (
            TitleTooLong(spec=NAMESPACE_SPEC, line=LineNumber.from_int(1), char_count=39, cap=35),
        ), 'a namespace cap does not replace the corpus one, so the title is held to it on its own'

    def test_check_with_a_title_over_both_caps_reports_each_in_order(self) -> None:
        #: Given
        subject = FakeDocumentContext(
            TEXT,
            corpus='guide',
            structure=_title_cap(38),
            namespaces=(namespace_spec('guide', 'cli', _title_cap(30)),),
        )

        #: When
        occurrences = TitleTooLong.check(subject)

        #: Then
        assert occurrences == (
            TitleTooLong(spec=CORPUS_SPEC, line=LineNumber.from_int(1), char_count=39, cap=38),
            TitleTooLong(spec=NAMESPACE_SPEC, line=LineNumber.from_int(1), char_count=39, cap=30),
        ), 'each specification applies on its own, so the title is reported once for each cap, in order'

    def test_check_with_markup_and_a_multibyte_character_counts_the_code_points_of_the_text(self) -> None:
        #: Given
        # `Typing in Python é` is 18 code points, though its `é` is two bytes and its backticks are left out
        subject = FakeDocumentContext('# Typing in `Python` é\n\nAnnotate.\n', corpus='guide', structure=_title_cap(17))

        #: When
        occurrences = TitleTooLong.check(subject)

        #: Then
        assert occurrences == (TitleTooLong(spec=CORPUS_SPEC, line=LineNumber.from_int(1), char_count=18, cap=17),), (
            "the title's characters are the code points of its text, its inline markup stripped"
        )

    def test_message_with_an_occurrence_names_the_characters_and_the_cap(self) -> None:
        #: Given
        occurrence = TitleTooLong(spec=CORPUS_SPEC, line=LineNumber.from_int(1), char_count=39, cap=30)

        #: When
        message = occurrence.message()

        #: Then
        assert message == 'too many characters in the title (39 > 30)', (
            'the message sets the character count against the cap'
        )

    def test_labels_with_an_occurrence_say_how_many_characters_it_runs_over_the_cap(self) -> None:
        #: Given
        occurrence = TitleTooLong(spec=CORPUS_SPEC, line=LineNumber.from_int(1), char_count=39, cap=30)

        #: When
        labels = occurrence.labels()

        #: Then
        assert labels == (Label(Here(LineNumber.from_int(1)), 'characters over the cap: 9'),), (
            'the label sits on the title and gives the overrun'
        )

    def test_children_with_an_occurrence_point_at_the_spec_then_help_then_say_how_characters_are_counted(self) -> None:
        #: Given
        occurrence = TitleTooLong(spec=CORPUS_SPEC, line=LineNumber.from_int(1), char_count=39, cap=30)

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Note('the limit is set here', at=Elsewhere(CORPUS_SPEC)),
            Help('name what the document is about, and leave the rest to its first paragraph'),
            Note(
                "characters are counted as the code points of the title's text, without its # marker or inline markup"
            ),
        ), 'the specification note comes first, then the help, then how the characters are counted'
