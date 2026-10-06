"""`OUT002`, `extra-title`, over a document's headings.

Every case is a document written as text, read through a fake context that parses it as the real parser does, under
structure specifications decoded from JSON; no document is read from disk.
"""

from typing import Final

import pytest

from lorecraft.core.path import RootRelativePath
from lorecraft.project.syntax import LineNumber
from lorecraft.rules.location import Elsewhere, Here, Label, Note
from lorecraft.rules.tests.fake_context import FakeDocumentContext, namespace_spec, structure_spec_path

from ..extra_title import ExtraTitle

CORPUS_SPEC: Final[RootRelativePath] = structure_spec_path('guide')
"""The corpus structure specification."""

STRUCTURE: Final[str] = '{"forbidden": ["Changelog"]}'
"""A structure specification that states a rule other than the title, which no key states."""

ONE_TITLE: Final[str] = '# Setup\n\n## Install\n\nInstall the toolkit, then run it once over the repository.\n'
"""A document of five lines: its H1 title on line 1, then one section."""

SECOND_TITLE: Final[str] = ONE_TITLE + '\n# Usage\n\nRun it over the repository.\n'
"""`ONE_TITLE`, followed by a second H1 title on line 7."""


@pytest.mark.unit
class TestExtraTitle:
    def test_check_with_a_second_title_reports_it_at_its_heading(self) -> None:
        #: Given
        subject = FakeDocumentContext(SECOND_TITLE, corpus='guide', structure=STRUCTURE)

        #: When
        occurrences = ExtraTitle.check(subject)

        #: Then
        assert occurrences == (
            ExtraTitle(spec=CORPUS_SPEC, line=LineNumber.from_int(7), first_line=LineNumber.from_int(1)),
        ), 'the second title is one occurrence, at its own heading, pointing back at the first'

    def test_check_with_two_titles_after_the_first_reports_each(self) -> None:
        #: Given
        subject = FakeDocumentContext(SECOND_TITLE + '\n# Reference\n', corpus='guide', structure=STRUCTURE)

        #: When
        occurrences = ExtraTitle.check(subject)

        #: Then
        assert occurrences == (
            ExtraTitle(spec=CORPUS_SPEC, line=LineNumber.from_int(7), first_line=LineNumber.from_int(1)),
            ExtraTitle(spec=CORPUS_SPEC, line=LineNumber.from_int(11), first_line=LineNumber.from_int(1)),
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
        assert occurrences == (
            ExtraTitle(spec=CORPUS_SPEC, line=LineNumber.from_int(7), first_line=LineNumber.from_int(1)),
        ), 'every specification agrees on one title, so the extra title is reported once, under the corpus'

    def test_message_with_an_occurrence_names_the_line_of_the_first_title(self) -> None:
        #: Given
        occurrence = ExtraTitle(spec=CORPUS_SPEC, line=LineNumber.from_int(7), first_line=LineNumber.from_int(1))

        #: When
        message = occurrence.message()

        #: Then
        assert message == 'extra H1 title, the document is titled on line 1', (
            'the message names the line of the title the document already carries'
        )

    def test_labels_with_an_occurrence_point_at_the_first_title(self) -> None:
        #: Given
        occurrence = ExtraTitle(spec=CORPUS_SPEC, line=LineNumber.from_int(7), first_line=LineNumber.from_int(1))

        #: When
        labels = occurrence.labels()

        #: Then
        assert labels == (Label(Here(LineNumber.from_int(1)), 'title written here'),), (
            "a label points at the document's own title, on its line"
        )

    def test_children_with_an_occurrence_point_at_the_specification(self) -> None:
        #: Given
        occurrence = ExtraTitle(spec=CORPUS_SPEC, line=LineNumber.from_int(7), first_line=LineNumber.from_int(1))

        #: When
        children = occurrence.children()

        #: Then
        assert children == (Note('the document structure is set here', at=Elsewhere(CORPUS_SPEC)),), (
            'a note points at the corpus structure specification that governs the document'
        )
