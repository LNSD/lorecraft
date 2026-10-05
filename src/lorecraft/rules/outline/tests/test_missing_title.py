"""`OUT001`, `missing-title`, over a document's headings.

The rule is pure, so every case here is a document's headings and what each specification states, written as
literals; no document is read.
"""

from typing import Final

import pytest

from lorecraft.core.num import NonZeroUnsignedInt
from lorecraft.core.path import RootRelativePath
from lorecraft.project.schemas import TitleRule
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


def _spec(spec: RootRelativePath, title: TitleRule | None) -> HeadingsSpec:
    """What a specification states over the headings: its title rule alone.

    Args:
        spec: The structure specification file.
        title: Its title rule, or `None` when it states none.
    """
    return HeadingsSpec(spec=spec, title=title, forbid_empty_sections=False, forbidden=(), section_caps=())


@pytest.mark.unit
class TestMissingTitle:
    def test_check_with_a_document_without_a_title_reports_it_on_line_1(self) -> None:
        #: Given
        title = TitleRule(count=NonZeroUnsignedInt(1), first=True)
        subject = HeadingsInput(headings=(INSTALL,), specs=(_spec(CORPUS_SPEC, title),))

        #: When
        occurrences = MissingTitle.check(subject)

        #: Then
        assert occurrences == (MissingTitle(spec=CORPUS_SPEC, line=LineNumber.from_int(1), found=0, count=1),), (
            'a document with no H1 is one occurrence, on line 1, naming the specification that requires the title'
        )

    def test_check_with_a_document_carrying_its_title_reports_nothing(self) -> None:
        #: Given
        title = TitleRule(count=NonZeroUnsignedInt(1), first=True)
        subject = HeadingsInput(headings=(TITLE, INSTALL), specs=(_spec(CORPUS_SPEC, title),))

        #: When
        occurrences = MissingTitle.check(subject)

        #: Then
        assert occurrences == (), 'a document carrying as many titles as required is not missing one'

    def test_check_with_more_titles_than_required_reports_nothing(self) -> None:
        #: Given
        title = TitleRule(count=NonZeroUnsignedInt(1), first=False)
        second = Heading(level=1, text='Again', line=LineNumber.from_int(5), empty=False, words=0)
        subject = HeadingsInput(headings=(TITLE, INSTALL, second), specs=(_spec(CORPUS_SPEC, title),))

        #: When
        occurrences = MissingTitle.check(subject)

        #: Then
        assert occurrences == (), 'a title past the count is an extra title, never a missing one'

    def test_check_with_no_title_rule_reports_nothing(self) -> None:
        #: Given
        subject = HeadingsInput(headings=(INSTALL,), specs=(_spec(CORPUS_SPEC, None),))

        #: When
        occurrences = MissingTitle.check(subject)

        #: Then
        assert occurrences == (), 'a specification that states no title rule requires no title'

    def test_check_with_a_document_short_of_both_specifications_reports_each_in_order(self) -> None:
        #: Given
        subject = HeadingsInput(
            headings=(TITLE, INSTALL),
            specs=(
                _spec(CORPUS_SPEC, TitleRule(count=NonZeroUnsignedInt(2), first=False)),
                _spec(NAMESPACE_SPEC, TitleRule(count=NonZeroUnsignedInt(3), first=False)),
            ),
        )

        #: When
        occurrences = MissingTitle.check(subject)

        #: Then
        assert occurrences == (
            MissingTitle(spec=CORPUS_SPEC, line=LineNumber.from_int(1), found=1, count=2),
            MissingTitle(spec=NAMESPACE_SPEC, line=LineNumber.from_int(1), found=1, count=3),
        ), 'each specification applies on its own, so the document is reported once for each, in order'

    def test_message_with_an_occurrence_names_the_titles_found_and_required(self) -> None:
        #: Given
        occurrence = MissingTitle(spec=CORPUS_SPEC, line=LineNumber.from_int(1), found=0, count=1)

        #: When
        message = occurrence.message()

        #: Then
        assert message == 'missing H1 title (0 < 1)', 'the message sets the titles found against the titles required'

    def test_children_with_an_occurrence_point_at_the_specification(self) -> None:
        #: Given
        occurrence = MissingTitle(spec=CORPUS_SPEC, line=LineNumber.from_int(1), found=0, count=1)

        #: When
        children = occurrence.children()

        #: Then
        assert children == (Note('the document structure is set here', at=Elsewhere(CORPUS_SPEC)),), (
            'a note points at the structure specification that requires the title'
        )
