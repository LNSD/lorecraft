"""`OUT003`, `title-not-first`, over a document's headings.

The rule is pure, so every case here is a document's headings and what each specification states, written as
literals; no document is read.
"""

from typing import Final

import pytest

from lorecraft.core.path import RootRelativePath
from lorecraft.project.syntax import Heading, LineNumber
from lorecraft.rules.inputs import HeadingsInput, HeadingsSpec
from lorecraft.rules.location import Elsewhere, Note

from ..title_not_first import TitleNotFirst

CORPUS_SPEC: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/guide.structure.json')
"""A corpus structure specification."""

NAMESPACE_SPEC: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/guide-cli.structure.json')
"""A namespace structure specification under the same corpus."""

INSTALL: Final[Heading] = Heading(level=2, text='Install', line=LineNumber.from_int(1), empty=False, words=9)
"""An H2 section opening the document, on line 1."""

TITLE: Final[Heading] = Heading(level=1, text='Setup', line=LineNumber.from_int(5), empty=True, words=0)
"""An H1 title on line 5, after the section."""

USAGE: Final[Heading] = Heading(level=2, text='Usage', line=LineNumber.from_int(7), empty=False, words=6)
"""An H2 section on line 7."""

DETAILS: Final[Heading] = Heading(level=3, text='Details', line=LineNumber.from_int(1), empty=False, words=4)
"""An H3 subsection opening the document, on line 1."""


def _spec(spec: RootRelativePath) -> HeadingsSpec:
    """What a specification states over the headings: nothing a title rule reads.

    Args:
        spec: The structure specification file.
    """
    return HeadingsSpec(
        spec=spec,
        title_cap=None,
        title_char_cap=None,
        title_mismatch=None,
        forbid_empty_sections=False,
        forbidden=(),
        section_caps=(),
    )


@pytest.mark.unit
class TestTitleNotFirst:
    def test_check_with_a_section_before_the_title_reports_it_at_the_section(self) -> None:
        #: Given
        subject = HeadingsInput(headings=(INSTALL, TITLE), corpus=_spec(CORPUS_SPEC), namespaces=())

        #: When
        occurrences = TitleNotFirst.check(subject)

        #: Then
        assert occurrences == (TitleNotFirst(spec=CORPUS_SPEC, line=LineNumber.from_int(1), level=2),), (
            'the heading opening the document in place of the title is one occurrence, at that heading'
        )

    def test_check_with_sections_and_no_title_reports_the_first_section(self) -> None:
        #: Given
        subject = HeadingsInput(headings=(INSTALL, USAGE), corpus=_spec(CORPUS_SPEC), namespaces=())

        #: When
        occurrences = TitleNotFirst.check(subject)

        #: Then
        assert occurrences == (TitleNotFirst(spec=CORPUS_SPEC, line=LineNumber.from_int(1), level=2),), (
            'a document opening with a section is reported even when it carries no title at all'
        )

    def test_check_with_a_subsection_opening_the_document_reports_its_level(self) -> None:
        #: Given
        subject = HeadingsInput(headings=(DETAILS, TITLE), corpus=_spec(CORPUS_SPEC), namespaces=())

        #: When
        occurrences = TitleNotFirst.check(subject)

        #: Then
        assert occurrences == (TitleNotFirst(spec=CORPUS_SPEC, line=LineNumber.from_int(1), level=3),), (
            'the occurrence carries the level of the heading the document opens with, not a fixed one'
        )

    def test_check_with_the_title_first_reports_nothing(self) -> None:
        #: Given
        subject = HeadingsInput(headings=(TITLE, USAGE), corpus=_spec(CORPUS_SPEC), namespaces=())

        #: When
        occurrences = TitleNotFirst.check(subject)

        #: Then
        assert occurrences == (), 'a document opening with its H1 title has it first'

    def test_check_with_no_heading_reports_nothing(self) -> None:
        #: Given
        subject = HeadingsInput(headings=(), corpus=_spec(CORPUS_SPEC), namespaces=())

        #: When
        occurrences = TitleNotFirst.check(subject)

        #: Then
        assert occurrences == (), 'a document with no heading is missing its title, which is not this rule'

    def test_check_with_two_specifications_reports_once_under_the_corpus_specification(self) -> None:
        #: Given
        subject = HeadingsInput(
            headings=(INSTALL, TITLE),
            corpus=_spec(CORPUS_SPEC),
            namespaces=(_spec(NAMESPACE_SPEC),),
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
