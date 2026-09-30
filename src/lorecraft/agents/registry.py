"""The agents Lorecraft knows, as one closed set, and the way another layer reads it.

The set itself stays private: a caller iterates the agents and reads each one's aspects from its record, so
what it learns, such as a project skills directory, stays tied to the agent that states it. Adding an agent is
adding its package beside ``claude`` and ``codex``, and its record to ``_AGENTS``.
"""

from collections.abc import Iterator
from typing import Final

from .base import Agent
from .claude import CLAUDE
from .codex import CODEX

_AGENTS: Final[tuple[Agent, ...]] = (CLAUDE, CODEX)
"""Every agent Lorecraft knows. The order carries no meaning."""


def iter_agents() -> Iterator[Agent]:
    """Every agent Lorecraft knows, one record each. The order carries no meaning."""
    return iter(_AGENTS)
