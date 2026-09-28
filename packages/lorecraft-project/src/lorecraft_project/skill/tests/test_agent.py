"""The agent registry: its four records and which of them read the canonical directory."""

from typing import Final

import pytest

from lorecraft_vfs import RootRelativePath

from ..agent import AGENTS, Agent, AgentName

DECLARED_NAMES: Final[tuple[AgentName, ...]] = (
    AgentName('codex'),
    AgentName('antigravity'),
    AgentName('opencode'),
    AgentName('claude-code'),
)


def _agent(name: str) -> Agent:
    """The registered agent with this name; fails the test when there is none."""
    for agent in AGENTS:
        if agent.name == name:
            return agent
    raise AssertionError(f'no agent named {name} is registered')


@pytest.mark.unit
class TestAgents:
    def test_agents_declares_the_four_names_in_registry_order(self) -> None:
        #: Given
        agents = AGENTS

        #: When
        names = tuple(agent.name for agent in agents)

        #: Then
        assert names == DECLARED_NAMES, f'the registry lists vercel ids in vercel order, once each, got {names}'

    def test_agents_with_claude_code_reads_the_claude_skills_directory(self) -> None:
        #: Given
        agent = _agent('claude-code')

        #: When
        skills_dir = agent.skills_dir

        #: Then
        assert skills_dir == RootRelativePath.parse('.claude/skills'), 'claude-code reads its own directory'

    def test_is_universal_with_codex_returns_true(self) -> None:
        #: Given
        agent = _agent('codex')

        #: When
        is_universal = agent.is_universal

        #: Then
        assert is_universal is True, 'codex reads .agents/skills directly, so it is universal'

    def test_is_universal_with_antigravity_returns_true(self) -> None:
        #: Given
        agent = _agent('antigravity')

        #: When
        is_universal = agent.is_universal

        #: Then
        assert is_universal is True, 'antigravity reads .agents/skills directly, so it is universal'

    def test_is_universal_with_opencode_returns_true(self) -> None:
        #: Given
        agent = _agent('opencode')

        #: When
        is_universal = agent.is_universal

        #: Then
        assert is_universal is True, 'opencode reads .agents/skills directly, so it is universal'

    def test_is_universal_with_claude_code_returns_false(self) -> None:
        #: Given
        agent = _agent('claude-code')

        #: When
        is_universal = agent.is_universal

        #: Then
        assert is_universal is False, 'claude-code reads its own .claude/skills, so it is not universal'
