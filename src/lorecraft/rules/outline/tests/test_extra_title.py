"""`OUT002`, `extra-title`, over a document's headings.

The rule is pure, so every case here is a document's headings and what each specification states, written as
literals; no document is read.
"""

from typing import Final

import pytest

from lorecraft.core.path import RootRelativePath
from lorecraft.project.syntax import Heading, LineNumber
from lorecraft.rules.inputs import HeadingsInput, HeadingsSpec
from lorecraft.rules.location import Elsewhere, Here, Label, Note

from ..extra_title import ExtraTitle

CORPUS_SPEC: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/guide.structure.json')
"""A corpus structure specification."""

NAMESPACE_SPEC: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/guide-cli.structure.json')
"""A namespace structure specification under the same corpus."""

TITLE: Final[Heading] = Heading(level=1, text='Setup', line=LineNumber.from_int(1), empty=False, words=0)
"""An H1 title on line 1."""

INSTALL: Final[Heading] = Heading(level=2, text='Install', line=LineNumber.from_int(3), empty=False, words=9)
"""An H2 section on line 3."""

SECOND_TITLE: Final[Heading] = Heading(level=1, text='Usage', line=LineNumber.from_int(7), empty=False, words=6)
"""A second H1 title on line 7."""

THIRD_TITLE: Final[Heading] = Heading(level=1, text='Reference', line=LineNumber.from_int(11), empty=False, words=4)
"""A third H1 title on line 11."""


def _spec(spec: RootRelativePath) -> HeadingsSpec:
    """What a specification states over the headings: nothing a title rule reads.

    Args:
        spec: The structure specification file.
    """
    return HeadingsSpec(spec=spec, title_cap=None, forbid_empty_sections=False, forbidden=(), section_caps=())


@pytest.mark.unit
class TestExtraTitle:
    def test_check_with_a_second_title_reports_it_at_its_heading(self) -> None:
        #: Given
        subject = HeadingsInput(headings=(TITLE, INSTALL, SECOND_TITLE), corpus=_spec(CORPUS_SPEC), namespaces=())

        #: When
        occurrences = ExtraTitle.check(subject)

        #: Then
        assert occurrences == (
            ExtraTitle(spec=CORPUS_SPEC, line=LineNumber.from_int(7), first_line=LineNumber.from_int(1)),
        ), 'the second title is one occurrence, at its own heading, pointing back at the first'

    def test_check_with_two_titles_after_the_first_reports_each(self) -> None:
        #: Given
        subject = HeadingsInput(
            headings=(TITLE, INSTALL, SECOND_TITLE, THIRD_TITLE), corpus=_spec(CORPUS_SPEC), namespaces=()
        )

        #: When
        occurrences = ExtraTitle.check(subject)

        #: Then
        assert occurrences == (
            ExtraTitle(spec=CORPUS_SPEC, line=LineNumber.from_int(7), first_line=LineNumber.from_int(1)),
            ExtraTitle(spec=CORPUS_SPEC, line=LineNumber.from_int(11), first_line=LineNumber.from_int(1)),
        ), 'every title after the first is its own occurrence, in document order, each pointing back at the first'

    def test_check_with_one_title_reports_nothing(self) -> None:
        #: Given
        subject = HeadingsInput(headings=(TITLE, INSTALL), corpus=_spec(CORPUS_SPEC), namespaces=())

        #: When
        occurrences = ExtraTitle.check(subject)

        #: Then
        assert occurrences == (), 'a document carrying its one title has none extra'

    def test_check_with_no_title_reports_nothing(self) -> None:
        #: Given
        subject = HeadingsInput(headings=(INSTALL,), corpus=_spec(CORPUS_SPEC), namespaces=())

        #: When
        occurrences = ExtraTitle.check(subject)

        #: Then
        assert occurrences == (), 'a document short of its titles is missing one, never carrying an extra one'

    def test_check_with_two_specifications_reports_once_under_the_corpus_specification(self) -> None:
        #: Given
        subject = HeadingsInput(
            headings=(TITLE, INSTALL, SECOND_TITLE),
            corpus=_spec(CORPUS_SPEC),
            namespaces=(_spec(NAMESPACE_SPEC),),
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
