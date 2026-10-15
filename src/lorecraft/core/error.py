"""Shared base for expected Lorecraft failures."""


class Error(Exception):
    """Base class for input and checking failures callers can report."""


class Unreachable(AssertionError):
    """A path the code claims cannot run did.

    Raised under a `# SAFETY: <invariant>` comment where the type checker cannot prove the path dead; the message
    states the expectation that broke.
    """
