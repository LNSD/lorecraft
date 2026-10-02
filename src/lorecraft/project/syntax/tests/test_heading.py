"""The heading nodes of a document's parse tree."""

import pytest

from ..heading import Heading
from ..position import LineNumber


@pytest.mark.unit
class TestHeading:
    def test_heading_with_level_zero_raises_value_error(self) -> None:
        #: Given
        rejected = 0

        #: When
        with pytest.raises(ValueError) as exc_info:
            Heading(level=rejected, text='Intro', line=LineNumber(1), empty=False, words=0)

        #: Then
        assert str(rejected) in str(exc_info.value), 'the error names the rejected level'

    def test_heading_with_level_seven_raises_value_error(self) -> None:
        #: Given
        rejected = 7

        #: When
        with pytest.raises(ValueError) as exc_info:
            Heading(level=rejected, text='Deep', line=LineNumber(1), empty=False, words=0)

        #: Then
        assert str(rejected) in str(exc_info.value), 'the error names the rejected level'

    def test_heading_with_level_one_constructs(self) -> None:
        #: Given
        level = 1

        #: When
        heading = Heading(level=level, text='Title', line=LineNumber(1), empty=False, words=5)

        #: Then
        assert heading.level == level, 'a title heading keeps level 1'

    def test_heading_with_level_six_constructs(self) -> None:
        #: Given
        level = 6

        #: When
        heading = Heading(level=level, text='Section', line=LineNumber(10), empty=True, words=0)

        #: Then
        assert heading.level == level, 'the deepest heading keeps level 6'
