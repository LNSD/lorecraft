"""A count past its cap, spelled in plain integers for the cases that expect one."""

from lorecraft.core.num import NonZeroUnsignedInt, Overrun, UnsignedInt


def overrun(count: int, cap: int) -> Overrun:
    """The overrun of `count` against `cap`.

    Args:
        count: The measured count; greater than `cap`.
        cap: The most the count may reach; at least 1.
    """
    return Overrun(UnsignedInt(count), NonZeroUnsignedInt(cap))
