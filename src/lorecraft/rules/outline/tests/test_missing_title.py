"""`OUT001`, `missing-title`, over a document's headings.

Every case is a document written as text, read through a fake context that parses it as the real parser does, under
structure specifications decoded from JSON; no document is read from disk.
"""

from typing import Final

import pytest

from lorecraft.core.path import RootRelativePath
from lorecraft.project.syntax import LineNumber
from lorecraft.rules.location import Elsewhere, Note
from lorecraft.rules.tests.fake_context import FakeDocumentContext, namespace_spec, structure_spec_path

from ..missing_title import MissingTitle

CORPUS_SPEC: Final[RootRelativePath] = structure_spec_path('guide')
"""The corpus structure specification."""

STRUCTURE: Final[str] = '{"forbidden": ["Changelog"]}'
"""A structure specification that states a rule other than the title, which no key states."""

UNTITLED: Final[str] = '## Install\n\nInstall the toolkit, then run it once over the repository.\n'
"""A document with one section and no H1 title."""


@pytest.mark.unit
class TestMissingTitle:
    def test_check_with_a_document_without_a_title_reports_it_on_line_1(self) -> None:
        #: Given
        subject = FakeDocumentContext(UNTITLED, corpus='guide', structure=STRUCTURE)

        #: When
        occurrences = MissingTitle.check(subject)

        #: Then
        assert occurrences == (MissingTitle(spec=CORPUS_SPEC, line=LineNumber.from_int(1)),), (
            'a document with no H1 is one occurrence, on line 1, naming the corpus structure specification'
        )

    def test_check_with_a_document_carrying_its_title_reports_nothing(self) -> None:
        #: Given
        subject = FakeDocumentContext('# Setup\n\n' + UNTITLED, corpus='guide', structure=STRUCTURE)

        #: When
        occurrences = MissingTitle.check(subject)

        #: Then
        assert occurrences == (), 'a document carrying its title is not missing one'

    def test_check_with_more_than_one_title_reports_nothing(self) -> None:
        #: Given
        subject = FakeDocumentContext('# Setup\n\n' + UNTITLED + '\n# Again\n', corpus='guide', structure=STRUCTURE)

        #: When
        occurrences = MissingTitle.check(subject)

        #: Then
        assert occurrences == (), 'a title after the first is an extra title, never a missing one'

    def test_check_with_an_h1_inside_a_blockquote_reports_the_title_missing(self) -> None:
        #: Given
        subject = FakeDocumentContext('> # Setup\n\n' + UNTITLED, corpus='guide', structure=STRUCTURE)

        #: When
        occurrences = MissingTitle.check(subject)

        #: Then
        assert occurrences == (MissingTitle(spec=CORPUS_SPEC, line=LineNumber.from_int(1)),), (
            'only a heading at the top level of the document counts, so an H1 in a blockquote is no title'
        )

    def test_check_with_two_specifications_reports_once_under_the_corpus_specification(self) -> None:
        #: Given
        subject = FakeDocumentContext(
            UNTITLED, corpus='guide', structure=STRUCTURE, namespaces=(namespace_spec('guide', 'cli', STRUCTURE),)
        )

        #: When
        occurrences = MissingTitle.check(subject)

        #: Then
        assert occurrences == (MissingTitle(spec=CORPUS_SPEC, line=LineNumber.from_int(1)),), (
            'every specification agrees on one title, so the document is reported once, under its corpus'
        )

    def test_message_with_an_occurrence_states_the_missing_title(self) -> None:
        #: Given
        occurrence = MissingTitle(spec=CORPUS_SPEC, line=LineNumber.from_int(1))

        #: When
        message = occurrence.message()

        #: Then
        assert message == 'missing H1 title', 'the message states that the title is missing'

    def test_children_with_an_occurrence_point_at_the_specification(self) -> None:
        #: Given
        occurrence = MissingTitle(spec=CORPUS_SPEC, line=LineNumber.from_int(1))

        #: When
        children = occurrence.children()

        #: Then
        assert children == (Note('the document structure is set here', at=Elsewhere(CORPUS_SPEC)),), (
            'a note points at the corpus structure specification that governs the document'
        )
