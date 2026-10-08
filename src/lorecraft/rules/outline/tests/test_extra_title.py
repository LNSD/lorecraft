"""`OUT002`, `extra-title`, over a document's headings.

Every case is a document written as text, read through a fake context that parses it as the real parser does, under
structure specifications decoded from JSON; no document is read from disk.
"""

from typing import Final

import pytest

from lorecraft.project.syntax import Heading, LineNumber
from lorecraft.rules.location import Help, Here, Label
from lorecraft.rules.tests.fake_context import FakeDocumentContext, heading_in, namespace_spec

from ..extra_title import ExtraTitle

STRUCTURE: Final[str] = '{"forbidden": ["Changelog"]}'
"""A structure specification that states a rule other than the title, which no key states."""

ONE_TITLE: Final[str] = '# Setup\n\n## Install\n\nInstall the toolkit, then run it once over the repository.\n'
"""A document of five lines: its H1 title on line 1, then one section."""

SECOND_TITLE: Final[str] = ONE_TITLE + '\n# Usage\n\nRun it over the repository.\n'
"""`ONE_TITLE`, followed by a second H1 title on line 7."""

FIRST_TITLE: Final[Heading] = heading_in(ONE_TITLE, 'Setup')
"""The H1 title of `ONE_TITLE`, on line 1."""


@pytest.mark.unit
class TestExtraTitle:
    def test_check_with_a_second_title_reports_it_at_its_heading(self) -> None:
        #: Given
        subject = FakeDocumentContext(SECOND_TITLE, corpus='guide', structure=STRUCTURE)

        #: When
        occurrences = ExtraTitle.check(subject)

        #: Then
        assert occurrences == (ExtraTitle(line=LineNumber.from_int(7), first_title=FIRST_TITLE),), (
            'the second title is one occurrence, at its own heading, pointing back at the first'
        )

    def test_check_with_two_titles_after_the_first_reports_each(self) -> None:
        #: Given
        subject = FakeDocumentContext(SECOND_TITLE + '\n# Reference\n', corpus='guide', structure=STRUCTURE)

        #: When
        occurrences = ExtraTitle.check(subject)

        #: Then
        assert occurrences == (
            ExtraTitle(line=LineNumber.from_int(7), first_title=FIRST_TITLE),
            ExtraTitle(line=LineNumber.from_int(11), first_title=FIRST_TITLE),
        ), 'every title after the first is its own occurrence, in document order, each pointing back at the first'

    def test_check_with_one_title_reports_nothing(self) -> None:
        #: Given
        subject = FakeDocumentContext(ONE_TITLE, corpus='guide', structure=STRUCTURE)

        #: When
        occurrences = ExtraTitle.check(subject)

        #: Then
        assert occurrences == (), 'a document carrying its one title has none extra'

    def test_check_with_no_title_reports_nothing(self) -> None:
        #: Given
        subject = FakeDocumentContext('## Install\n\nInstall the toolkit.\n', corpus='guide', structure=STRUCTURE)

        #: When
        occurrences = ExtraTitle.check(subject)

        #: Then
        assert occurrences == (), 'a document short of its titles is missing one, never carrying an extra one'

    def test_check_with_two_specifications_reports_once_under_the_corpus_specification(self) -> None:
        #: Given
        subject = FakeDocumentContext(
            SECOND_TITLE, corpus='guide', structure=STRUCTURE, namespaces=(namespace_spec('guide', 'cli', STRUCTURE),)
        )

        #: When
        occurrences = ExtraTitle.check(subject)

        #: Then
        assert occurrences == (ExtraTitle(line=LineNumber.from_int(7), first_title=FIRST_TITLE),), (
            'every specification agrees on one title, so the extra title is reported once'
        )

    def test_message_with_an_occurrence_states_the_extra_title(self) -> None:
        #: Given
        occurrence = ExtraTitle(line=LineNumber.from_int(7), first_title=FIRST_TITLE)

        #: When
        message = occurrence.message()

        #: Then
        assert message == 'extra H1 title', 'the message is one template; the label shows the title already written'

    def test_labels_with_an_occurrence_point_at_the_first_title(self) -> None:
        #: Given
        occurrence = ExtraTitle(line=LineNumber.from_int(7), first_title=FIRST_TITLE)

        #: When
        labels = occurrence.labels()

        #: Then
        assert labels == (Label(Here(LineNumber.from_int(1)), 'the document is titled `Setup` here'),), (
            "a label points at the document's own title, on its line, and names it"
        )

    def test_children_with_an_occurrence_say_where_the_extra_title_belongs(self) -> None:
        #: Given
        occurrence = ExtraTitle(line=LineNumber.from_int(7), first_title=FIRST_TITLE)

        #: When
        children = occurrence.children()

        #: Then
        assert children == (Help('make it an H2 section, or move it into a document of its own'),), (
            'help says to make the extra title a section or a document, and no note points at a specification'
        )
