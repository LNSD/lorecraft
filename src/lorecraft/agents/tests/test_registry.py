"""What every registered agent declares: each path is a validated root-relative path."""

import pytest

from lorecraft.agents.base import Agent
from lorecraft.core.path import RootRelativePath

from ..registry import iter_agents


def _declared_paths(agents: tuple[Agent, ...]) -> list[object]:
    """Every skills directory and instruction file the agents declare, project then user, agent by agent.

    Args:
        agents: The registered agents.
    """
    return [
        path
        for agent in agents
        for path in (
            *agent.project_skills_dirs,
            *agent.user_skills_dirs,
            *agent.project_agents_md_files,
            *agent.user_agents_md_files,
        )
    ]


def _unvalidated(paths: list[object], validated: type) -> list[object]:
    """The paths that are not an instance of the validated type, in the order given.

    Args:
        paths: Paths the agents declare.
        validated: The type every declared path must be.
    """
    return [path for path in paths if not isinstance(path, validated)]


@pytest.mark.unit
class TestIterAgents:
    def test_iter_agents_with_the_registered_agents_yields_only_root_relative_paths(self) -> None:
        #: Given
        validated = RootRelativePath
        registered = iter_agents()

        #: When
        agents = tuple(registered)

        #: Then
        declared = _declared_paths(agents)
        unvalidated = _unvalidated(declared, validated)
        assert declared, 'the registered agents declare at least one path'
        assert not unvalidated, f'every declared path is validated, got {unvalidated}'
