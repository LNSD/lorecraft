"""The top-level headings of a document's parse tree, and finding its title and its sections among them."""

import pytest

from lorecraft.core.num import NonZeroUnsignedInt, UnsignedInt

from ..heading import Heading, HeadingLevel, SectionHeading, find_title, section_headings
from ..position import LineNumber
from ..words import WordCount


@pytest.mark.unit
class TestHeading:
    def test_heading_level_one_constructs(self) -> None:
        #: Given
        accepted = 1
        line = LineNumber(NonZeroUnsignedInt(1))
        words = WordCount(UnsignedInt(5))

        #: When
        heading = Heading(
            level=accepted,
            text='Title',
            line=line,
            empty=False,
            words=words,
        )

        #: Then
        assert heading.level == accepted, 'a title heading keeps level 1'

    def test_heading_level_six_constructs(self) -> None:
        #: Given
        accepted = 6
        line = LineNumber(NonZeroUnsignedInt(10))
        words = WordCount(UnsignedInt(0))

        #: When
        heading = Heading(
            level=accepted,
            text='Section',
            line=line,
            empty=True,
            words=words,
        )

        #: Then
        assert heading.level == accepted, 'the deepest heading keeps level 6'


def _heading(level: HeadingLevel, text: str, line: int) -> Heading:
    """A heading with content and no prose words, at a line.

    Args:
        level: The heading depth.
        text: The heading's text.
        line: The line it starts on.
    """
    return Heading(
        level=level, text=text, line=LineNumber(NonZeroUnsignedInt(line)), empty=False, words=WordCount(UnsignedInt(0))
    )


@pytest.mark.unit
class TestFindTitle:
    def test_find_title_with_two_h1_headings_returns_the_first(self) -> None:
        #: Given
        first = _heading(1, 'Setup', 3)
        headings = (_heading(2, 'Before', 1), first, _heading(1, 'Setup again', 5))

        #: When
        title = find_title(headings)

        #: Then
        assert title == first, 'the title is the first H1, wherever it falls, and a later H1 is not'

    def test_find_title_with_no_h1_heading_returns_none(self) -> None:
        #: Given
        headings = (_heading(2, 'Run', 1), _heading(3, 'Options', 3))

        #: When
        title = find_title(headings)

        #: Then
        assert title is None, 'a document with no H1 has no title'


@pytest.mark.unit
class TestFindSections:
    def test_section_headings_with_headings_of_every_level_returns_only_the_h2_headings_in_order(self) -> None:
        #: Given
        first = _heading(2, 'Rule', 3)
        second = _heading(2, 'Checklist', 9)
        headings = (_heading(1, 'Title', 1), first, _heading(3, 'Detail', 5), second, _heading(1, 'Again', 12))

        #: When
        sections = section_headings(headings)

        #: Then
        assert sections == (
            SectionHeading(level=2, text='Rule', line=first.line, empty=first.empty, words=first.words),
            SectionHeading(level=2, text='Checklist', line=second.line, empty=second.empty, words=second.words),
        ), 'only an H2 opens a section, and they keep document order'
