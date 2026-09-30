"""Skill ref identity and ordering; nothing here touches the disk."""

import pytest

from lorecraft.vfs import RootRelativePath

from ..ref import SkillRef


@pytest.mark.unit
class TestSkillRef:
    def test_path_with_a_skill_directory_returns_the_skill_file_inside_it(self) -> None:
        #: Given
        ref = SkillRef(RootRelativePath.parse('.agents/skills/review'))

        #: When
        path = ref.path

        #: Then
        assert path == RootRelativePath.parse('.agents/skills/review/SKILL.md'), (
            'the skill file is always SKILL.md, directly inside the skill directory'
        )

    def test_sorted_with_refs_in_two_skills_directories_returns_them_in_directory_order(self) -> None:
        #: Given
        review = SkillRef(RootRelativePath.parse('skills/review'))
        commit = SkillRef(RootRelativePath.parse('.agents/skills/commit'))

        #: When
        ordered = sorted([review, commit])

        #: Then
        assert ordered == [commit, review], 'refs order by their directory'
