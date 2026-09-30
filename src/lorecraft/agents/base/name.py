"""The name aspect: the id an agent is known by."""

from typing import NewType

AgentName = NewType('AgentName', str)
"""An agent's id, as vercel-labs/skills spells it (its ``AgentType``), such as ``claude-code``."""
