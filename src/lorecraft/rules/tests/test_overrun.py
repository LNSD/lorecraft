"""The overrun value: what it keeps, what it refuses, and when a count is within its cap and so none."""

import pytest

from lorecraft.core.num import NonZeroUnsignedInt, UnsignedInt

from ..overrun import NotOverCapError, Overrun, find_overrun


@pytest.mark.unit
class TestOverrun:
    def test_find_overrun_with_a_count_past_the_cap_keeps_both(self) -> None:
        #: Given
        count = UnsignedInt(501)
        cap = NonZeroUnsignedInt(500)

        #: When
        overrun = find_overrun(count, cap)

        #: Then
        assert overrun == Overrun(count, cap), f'a count past its cap is an overrun of both, got {overrun}'

    def test_find_overrun_with_a_count_equal_to_the_cap_returns_none(self) -> None:
        #: Given
        count = UnsignedInt(500)
        cap = NonZeroUnsignedInt(500)

        #: When
        overrun = find_overrun(count, cap)

        #: Then
        assert overrun is None, f'a count equal to its cap is within it, got {overrun}'

    def test_find_overrun_with_a_count_below_the_cap_returns_none(self) -> None:
        #: Given
        count = UnsignedInt(0)
        cap = NonZeroUnsignedInt(500)

        #: When
        overrun = find_overrun(count, cap)

        #: Then
        assert overrun is None, f'a count below its cap is within it, got {overrun}'

    def test_construction_with_a_count_within_the_cap_raises_not_over_cap(self) -> None:
        #: Given
        count = UnsignedInt(500)
        cap = NonZeroUnsignedInt(500)

        #: When
        with pytest.raises(NotOverCapError) as exc_info:
            Overrun(count, cap)

        #: Then
        assert exc_info.value.count == 500, 'the error keeps the rejected count'
        assert exc_info.value.cap == 500, 'the error keeps the cap'

    def test_excess_is_the_count_past_the_cap(self) -> None:
        #: Given
        overrun = Overrun(UnsignedInt(612), NonZeroUnsignedInt(500))

        #: When
        excess = overrun.excess

        #: Then
        assert excess == NonZeroUnsignedInt(112), f'612 is 112 past 500, got {excess}'
