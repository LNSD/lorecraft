"""A count that is past its cap: the value the length rules and `FM012` each hold in place of a count and a cap.

It lives with the rules, not in `lorecraft.core.num`, because "past a cap" is what a check reports, not a number
that is generic over the domain.
"""

from dataclasses import dataclass

from lorecraft.core.error import Error
from lorecraft.core.num import NonZeroUnsignedInt, UnsignedInt


class NotOverCapError(Error):
    """A count is not past its cap, so it is no overrun.

    Attributes:
        count: The rejected count.
        cap: The cap it does not exceed.
    """

    count: int
    cap: int

    def __init__(self, count: int, cap: int) -> None:
        self.count = count
        self.cap = cap
        super().__init__(f'a count must exceed its cap, got {count} <= {cap}')


def _is_past_cap(count: UnsignedInt, cap: NonZeroUnsignedInt) -> bool:
    """Whether a count is past its cap; a count equal to the cap is within it.

    Args:
        count: The measured count.
        cap: The most the count may reach.
    """
    return count.value > cap.value


@dataclass(frozen=True, slots=True)
class Overrun:
    """A count that is past its cap.

    The count and the cap travel together, so a report never holds a pair where the count is within the cap, or one
    that is negative. A count that is within its cap is no overrun: `find_overrun` returns `None` for it.

    Attributes:
        count: The measured count; always greater than `cap`.
        cap: The most the count may reach.
    """

    count: UnsignedInt
    cap: NonZeroUnsignedInt

    def __post_init__(self) -> None:
        """Refuse a count that is not past its cap.

        Raises:
            NotOverCapError: If the count is at most the cap.
        """
        if not _is_past_cap(self.count, self.cap):
            raise NotOverCapError(self.count.value, self.cap.value)

    @property
    def excess(self) -> NonZeroUnsignedInt:
        """How far the count runs past its cap; at least 1."""
        return NonZeroUnsignedInt(self.count.value - self.cap.value)


def find_overrun(count: UnsignedInt, cap: NonZeroUnsignedInt) -> Overrun | None:
    """The overrun of a count against its cap, or `None` when the count is within it.

    Args:
        count: The measured count.
        cap: The most the count may reach; a count equal to it is within it.
    """
    if not _is_past_cap(count, cap):
        return None
    return Overrun(count, cap)
