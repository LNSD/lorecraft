"""`OUT001`, `missing-title`, over a document's headings.

The rule is pure, so every case here is a document's headings and what each specification states, written as
literals; no document is read.
"""

from typing import Final

import pytest

from lorecraft.core.path import RootRelativePath
from lorecraft.project.syntax import Heading, LineNumber
from lorecraft.rules.inputs import HeadingsInput, HeadingsSpec
from lorecraft.rules.location import Elsewhere, Note

from ..missing_title import MissingTitle

CORPUS_SPEC: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/guide.structure.json')
"""A corpus structure specification."""

NAMESPACE_SPEC: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/guide-cli.structure.json')
"""A namespace structure specification under the same corpus."""

TITLE: Final[Heading] = Heading(level=1, text='Setup', line=LineNumber.from_int(1), empty=False, words=0)
"""An H1 title on line 1."""

INSTALL: Final[Heading] = Heading(level=2, text='Install', line=LineNumber.from_int(3), empty=False, words=9)
"""An H2 section on line 3."""


def _spec(spec: RootRelativePath) -> HeadingsSpec:
    """What a specification states over the headings: nothing a title rule reads.

    Args:
        spec: The structure specification file.
    """
    return HeadingsSpec(spec=spec, forbid_empty_sections=False, forbidden=(), section_caps=())


@pytest.mark.unit
class TestMissingTitle:
    def test_check_with_a_document_without_a_title_reports_it_on_line_1(self) -> None:
        #: Given
        subject = HeadingsInput(headings=(INSTALL,), corpus=_spec(CORPUS_SPEC), namespaces=())

        #: When
        occurrences = MissingTitle.check(subject)

        #: Then
        assert occurrences == (MissingTitle(spec=CORPUS_SPEC, line=LineNumber.from_int(1)),), (
            'a document with no H1 is one occurrence, on line 1, naming the corpus structure specification'
        )

    def test_check_with_a_document_carrying_its_title_reports_nothing(self) -> None:
        #: Given
        subject = HeadingsInput(headings=(TITLE, INSTALL), corpus=_spec(CORPUS_SPEC), namespaces=())

        #: When
        occurrences = MissingTitle.check(subject)

        #: Then
        assert occurrences == (), 'a document carrying its title is not missing one'

    def test_check_with_more_than_one_title_reports_nothing(self) -> None:
        #: Given
        second = Heading(level=1, text='Again', line=LineNumber.from_int(5), empty=False, words=0)
        subject = HeadingsInput(headings=(TITLE, INSTALL, second), corpus=_spec(CORPUS_SPEC), namespaces=())

        #: When
        occurrences = MissingTitle.check(subject)

        #: Then
        assert occurrences == (), 'a title after the first is an extra title, never a missing one'

    def test_check_with_two_specifications_reports_once_under_the_corpus_specification(self) -> None:
        #: Given
        subject = HeadingsInput(
            headings=(INSTALL,),
            corpus=_spec(CORPUS_SPEC),
            namespaces=(_spec(NAMESPACE_SPEC),),
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
