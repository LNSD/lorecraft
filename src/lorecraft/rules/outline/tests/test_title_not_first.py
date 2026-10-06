"""`OUT003`, `title-not-first`, over a document's headings.

Every case is a document written as text, read through a fake context that parses it as the real parser does, under
structure specifications decoded from JSON; no document is read from disk.
"""

from typing import Final

import pytest

from lorecraft.core.path import RootRelativePath
from lorecraft.project.syntax import LineNumber
from lorecraft.rules.location import Elsewhere, Note
from lorecraft.rules.tests.fake_context import FakeDocumentContext, namespace_spec, structure_spec_path

from ..title_not_first import TitleNotFirst

CORPUS_SPEC: Final[RootRelativePath] = structure_spec_path('guide')
"""The corpus structure specification."""

STRUCTURE: Final[str] = '{"forbidden": ["Changelog"]}'
"""A structure specification that states a rule other than the title, which no key states."""

SECTION_FIRST: Final[str] = '## Install\n\nInstall the toolkit, then run it once over the repository.\n\n# Setup\n'
"""A document opening with an H2 section on line 1, its H1 title on line 5."""


@pytest.mark.unit
class TestTitleNotFirst:
    def test_check_with_a_section_before_the_title_reports_it_at_the_section(self) -> None:
        #: Given
        subject = FakeDocumentContext(SECTION_FIRST, corpus='guide', structure=STRUCTURE)

        #: When
        occurrences = TitleNotFirst.check(subject)

        #: Then
        assert occurrences == (TitleNotFirst(spec=CORPUS_SPEC, line=LineNumber.from_int(1), level=2),), (
            'the heading opening the document in place of the title is one occurrence, at that heading'
        )

    def test_check_with_sections_and_no_title_reports_the_first_section(self) -> None:
        #: Given
        subject = FakeDocumentContext(
            '## Install\n\nInstall it.\n\n## Usage\n\nRun it.\n', corpus='guide', structure=STRUCTURE
        )

        #: When
        occurrences = TitleNotFirst.check(subject)

        #: Then
        assert occurrences == (TitleNotFirst(spec=CORPUS_SPEC, line=LineNumber.from_int(1), level=2),), (
            'a document opening with a section is reported even when it carries no title at all'
        )

    def test_check_with_a_subsection_opening_the_document_reports_its_level(self) -> None:
        #: Given
        subject = FakeDocumentContext(
            '### Details\n\nRead them once.\n\n# Setup\n', corpus='guide', structure=STRUCTURE
        )

        #: When
        occurrences = TitleNotFirst.check(subject)

        #: Then
        assert occurrences == (TitleNotFirst(spec=CORPUS_SPEC, line=LineNumber.from_int(1), level=3),), (
            'the occurrence carries the level of the heading the document opens with, not a fixed one'
        )

    def test_check_with_the_title_first_reports_nothing(self) -> None:
        #: Given
        subject = FakeDocumentContext('# Setup\n\n## Usage\n\nRun it.\n', corpus='guide', structure=STRUCTURE)

        #: When
        occurrences = TitleNotFirst.check(subject)

        #: Then
        assert occurrences == (), 'a document opening with its H1 title has it first'

    def test_check_with_no_heading_reports_nothing(self) -> None:
        #: Given
        subject = FakeDocumentContext(
            'Run the toolkit once over the repository.\n', corpus='guide', structure=STRUCTURE
        )

        #: When
        occurrences = TitleNotFirst.check(subject)

        #: Then
        assert occurrences == (), 'a document with no heading is missing its title, which is not this rule'

    def test_check_with_two_specifications_reports_once_under_the_corpus_specification(self) -> None:
        #: Given
        subject = FakeDocumentContext(
            SECTION_FIRST, corpus='guide', structure=STRUCTURE, namespaces=(namespace_spec('guide', 'cli', STRUCTURE),)
        )

        #: When
        occurrences = TitleNotFirst.check(subject)

        #: Then
        assert occurrences == (TitleNotFirst(spec=CORPUS_SPEC, line=LineNumber.from_int(1), level=2),), (
            'every specification agrees the title opens the document, so the opening heading is reported once, '
            'under the corpus'
        )

    def test_message_with_an_occurrence_names_the_heading_level_found(self) -> None:
        #: Given
        occurrence = TitleNotFirst(spec=CORPUS_SPEC, line=LineNumber.from_int(1), level=2)

        #: When
        message = occurrence.message()

        #: Then
        assert message == 'first heading is not the H1 title (found H2)', (
            'the message names the level of the heading found where the title belongs'
        )

    def test_message_with_a_subsection_occurrence_names_h3(self) -> None:
        #: Given
        occurrence = TitleNotFirst(spec=CORPUS_SPEC, line=LineNumber.from_int(1), level=3)

        #: When
        message = occurrence.message()

        #: Then
        assert message == 'first heading is not the H1 title (found H3)', (
            'the message is formatted from the level found, so an H3 reads as H3'
        )

    def test_children_with_an_occurrence_point_at_the_specification(self) -> None:
        #: Given
        occurrence = TitleNotFirst(spec=CORPUS_SPEC, line=LineNumber.from_int(1), level=2)

        #: When
        children = occurrence.children()

        #: Then
        assert children == (Note('the document structure is set here', at=Elsewhere(CORPUS_SPEC)),), (
            'a note points at the corpus structure specification that governs the document'
        )
