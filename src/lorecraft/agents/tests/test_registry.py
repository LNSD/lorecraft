"""What every registered agent declares: each path is a validated root-relative path."""

import pytest

from lorecraft.core.path import RootRelativePath

from ..registry import iter_agents


@pytest.mark.unit
class TestIterAgents:
    def test_iter_agents_with_the_registered_agents_yields_only_root_relative_paths(self) -> None:
        #: Given
        validated = RootRelativePath

        #: When
        agents = tuple(iter_agents())
        declared = [
            path
            for agent in agents
            for path in (
                *agent.project_skills_dirs,
                *agent.user_skills_dirs,
                *agent.project_agents_md_files,
                *agent.user_agents_md_files,
            )
        ]

        #: Then
        unvalidated = [path for path in declared if not isinstance(path, validated)]
        assert declared, 'the registered agents declare at least one path'
        assert not unvalidated, f'every declared path is validated, got {unvalidated}'
