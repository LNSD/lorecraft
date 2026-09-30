"""Lorecraft agents: the model of the coding agents Lorecraft knows.

Everything Lorecraft states about an agent lives in this layer. ``base`` declares the aspects an agent has, one
module each, and every agent has a package of its own stating its values for them: ``claude`` and ``codex``.
``registry`` gathers them into the set of agents Lorecraft knows. It is data: nothing here reads the
environment, the home directory or the disk, and it imports no other Lorecraft layer. Its paths are pure paths
relative to the repository root for the project scope, or to the home directory for the user scope, which
whoever holds one resolves.

The surface is the registry and what holds for every agent: another layer iterates the agents and reads each
one's aspects from its ``Agent`` record, and names no agent and no agent's constant itself. The set of agents
and each agent's constants stay inside this layer. ``SKILL_ENTRY_FILENAME`` is the exception that is not one:
the specification fixes it, so no agent states it and there is no record to read it from.
"""

from .base import SKILL_ENTRY_FILENAME, Agent, AgentName
from .registry import iter_agents

__all__: list[str] = [
    'Agent',
    'AgentName',
    'iter_agents',
    'SKILL_ENTRY_FILENAME',
]
