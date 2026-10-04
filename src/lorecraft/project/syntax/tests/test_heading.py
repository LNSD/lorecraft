"""The top-level headings of a document's parse tree."""

from typing import cast

import pytest

from ..heading import Heading, HeadingLevel
from ..position import LineNumber


@pytest.mark.unit
class TestHeading:
    def test_heading_level_zero_raises_assertion_error(self) -> None:
        #: Given
        # The type rules 0 out; the cast stands in for a value that reached the field through `Any`.
        rejected = cast(HeadingLevel, 0)

        #: When
        with pytest.raises(AssertionError) as exc_info:
            Heading(level=rejected, text='Intro', line=LineNumber.parse(1), empty=False, words=0)

        #: Then
        assert str(rejected) in str(exc_info.value), 'the error names the rejected level'

    def test_heading_level_seven_raises_assertion_error(self) -> None:
        #: Given
        # The type rules 7 out; the cast stands in for a value that reached the field through `Any`.
        rejected = cast(HeadingLevel, 7)

        #: When
        with pytest.raises(AssertionError) as exc_info:
            Heading(level=rejected, text='Deep', line=LineNumber.parse(1), empty=False, words=0)

        #: Then
        assert str(rejected) in str(exc_info.value), 'the error names the rejected level'

    def test_heading_level_one_constructs(self) -> None:
        #: Given
        accepted = 1

        #: When
        heading = Heading(level=accepted, text='Title', line=LineNumber.parse(1), empty=False, words=5)

        #: Then
        assert heading.level == accepted, 'a title heading keeps level 1'

    def test_heading_level_six_constructs(self) -> None:
        #: Given
        accepted = 6

        #: When
        heading = Heading(level=accepted, text='Section', line=LineNumber.parse(10), empty=True, words=0)

        #: Then
        assert heading.level == accepted, 'the deepest heading keeps level 6'
