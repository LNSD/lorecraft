"""The top-level headings of a document's parse tree, and finding its title among them."""

from typing import cast

import pytest

from ..heading import Heading, HeadingLevel, find_title
from ..position import LineNumber


@pytest.mark.unit
class TestHeading:
    def test_heading_level_zero_raises_assertion_error(self) -> None:
        #: Given
        # The type rules 0 out; the cast stands in for a value that reached the field through `Any`.
        rejected = cast(HeadingLevel, 0)

        #: When
        with pytest.raises(AssertionError) as exc_info:
            Heading(level=rejected, text='Intro', line=LineNumber.from_int(1), empty=False, words=0)

        #: Then
        assert str(rejected) in str(exc_info.value), 'the error names the rejected level'

    def test_heading_level_seven_raises_assertion_error(self) -> None:
        #: Given
        # The type rules 7 out; the cast stands in for a value that reached the field through `Any`.
        rejected = cast(HeadingLevel, 7)

        #: When
        with pytest.raises(AssertionError) as exc_info:
            Heading(level=rejected, text='Deep', line=LineNumber.from_int(1), empty=False, words=0)

        #: Then
        assert str(rejected) in str(exc_info.value), 'the error names the rejected level'

    def test_heading_level_one_constructs(self) -> None:
        #: Given
        accepted = 1

        #: When
        heading = Heading(level=accepted, text='Title', line=LineNumber.from_int(1), empty=False, words=5)

        #: Then
        assert heading.level == accepted, 'a title heading keeps level 1'

    def test_heading_level_six_constructs(self) -> None:
        #: Given
        accepted = 6

        #: When
        heading = Heading(level=accepted, text='Section', line=LineNumber.from_int(10), empty=True, words=0)

        #: Then
        assert heading.level == accepted, 'the deepest heading keeps level 6'


def _heading(level: HeadingLevel, text: str, line: int) -> Heading:
    """A heading with content and no prose words, at a line.

    Args:
        level: The heading depth.
        text: The heading's text.
        line: The line it starts on.
    """
    return Heading(level=level, text=text, line=LineNumber.from_int(line), empty=False, words=0)


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
