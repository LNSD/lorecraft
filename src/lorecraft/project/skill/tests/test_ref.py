"""Skill and resource ref identity and ordering, and which paths name a resource; nothing here touches the disk."""

import pytest

from lorecraft.core.path import PathComponent, RootRelativePath, RootRelativePathError
from lorecraft.vfs import ResolvedPath

from ..ref import NotASkillResourceError, SkillRef, SkillRelativePath, SkillResourceRef


@pytest.mark.unit
class TestSkillRelativePath:
    def test_parse_with_a_path_climbing_out_of_the_skill_raises_root_relative_path_error(self) -> None:
        #: Given
        invalid_path = '../x.md'

        #: When
        with pytest.raises(RootRelativePathError) as exc_info:
            SkillRelativePath.parse(invalid_path)

        #: Then
        assert invalid_path in str(exc_info.value), 'a path climbing out of the skill is refused'

    def test_parse_with_an_absolute_path_raises_root_relative_path_error(self) -> None:
        #: Given
        invalid_path = '/x.md'

        #: When
        with pytest.raises(RootRelativePathError) as exc_info:
            SkillRelativePath.parse(invalid_path)

        #: Then
        assert invalid_path in str(exc_info.value), 'an absolute path is refused'

    def test_parse_with_a_dot_returns_the_skill_directory(self) -> None:
        #: Given
        directory = '.'

        #: When
        path = SkillRelativePath.parse(directory)

        #: Then
        assert path.name is None, 'the skill directory has no name'
        assert str(path) == '.', 'the skill directory prints as `.`'

    def test_truediv_with_a_name_returns_the_joined_path(self) -> None:
        #: Given
        directory = SkillRelativePath.parse('references')

        #: When
        joined = directory / PathComponent.parse('a.md')

        #: Then
        assert joined == SkillRelativePath.parse('references/a.md'), 'a name joins below the path'

    def test_under_with_a_skill_directory_returns_the_root_relative_path(self) -> None:
        #: Given
        path = SkillRelativePath.parse('guides/d.md')
        directory = RootRelativePath.parse('.agents/skills/review')

        #: When
        root_relative = path.under(directory)

        #: Then
        assert root_relative == RootRelativePath.parse('.agents/skills/review/guides/d.md'), (
            'the path is spelled from the root through the skill directory'
        )

    def test_under_with_the_skill_directory_itself_returns_that_directory(self) -> None:
        #: Given
        path = SkillRelativePath.parse('.')
        directory = RootRelativePath.parse('.agents/skills/review')

        #: When
        root_relative = path.under(directory)

        #: Then
        assert root_relative == RootRelativePath.parse('.agents/skills/review'), '`.` is the skill directory'

    def test_sorted_with_paths_out_of_order_returns_them_ordered_by_value(self) -> None:
        #: Given
        scripts = SkillRelativePath.parse('scripts/a.md')
        references = SkillRelativePath.parse('references/a.md')

        #: When
        ordered = sorted([scripts, references])

        #: Then
        assert ordered == [references, scripts], 'paths order as the root-relative paths they wrap do'


@pytest.mark.unit
class TestSkillRef:
    def test_path_with_a_skill_directory_returns_the_skill_file_inside_it(self) -> None:
        #: Given
        ref = SkillRef(ResolvedPath(RootRelativePath.parse('.agents/skills')), PathComponent.parse('review'))

        #: When
        path = ref.path

        #: Then
        assert path == RootRelativePath.parse('.agents/skills/review/SKILL.md'), (
            'the skill file is always SKILL.md, directly inside the skill directory'
        )

    def test_sorted_with_refs_in_two_skills_directories_returns_them_in_directory_order(self) -> None:
        #: Given
        review = SkillRef(ResolvedPath(RootRelativePath.parse('skills')), PathComponent.parse('review'))
        commit = SkillRef(ResolvedPath(RootRelativePath.parse('.agents/skills')), PathComponent.parse('commit'))

        #: When
        ordered = sorted([review, commit])

        #: Then
        assert ordered == [commit, review], 'refs order by their directory'

    def test_find_resource_with_the_top_level_skill_file_returns_none(self) -> None:
        #: Given
        ref = SkillRef(ResolvedPath(RootRelativePath.parse('.agents/skills')), PathComponent.parse('review'))
        path = SkillRelativePath.parse('SKILL.md')

        #: When
        resource = ref.find_resource(path)

        #: Then
        assert resource is None, "the skill's own SKILL.md is the skill, never one of its resources"

    def test_find_resource_with_a_name_not_ending_in_md_returns_none(self) -> None:
        #: Given
        ref = SkillRef(ResolvedPath(RootRelativePath.parse('.agents/skills')), PathComponent.parse('review'))
        path = SkillRelativePath.parse('scripts/run.py')

        #: When
        resource = ref.find_resource(path)

        #: Then
        assert resource is None, 'only a file named as a Markdown document is a resource'

    def test_find_resource_with_the_skill_directory_itself_returns_none(self) -> None:
        #: Given
        ref = SkillRef(ResolvedPath(RootRelativePath.parse('.agents/skills')), PathComponent.parse('review'))
        path = SkillRelativePath.parse('.')

        #: When
        resource = ref.find_resource(path)

        #: Then
        assert resource is None, 'the skill directory has no name, so it names no resource'

    def test_find_resource_with_a_nested_skill_file_returns_its_ref(self) -> None:
        #: Given
        ref = SkillRef(ResolvedPath(RootRelativePath.parse('.agents/skills')), PathComponent.parse('review'))
        path = SkillRelativePath.parse('examples/SKILL.md')

        #: When
        resource = ref.find_resource(path)

        #: Then
        assert resource == SkillResourceRef(ref, SkillRelativePath.parse('examples/SKILL.md')), (
            'a SKILL.md below the top level is a Markdown file inside the skill like any other, so a resource'
        )


@pytest.mark.unit
class TestSkillResourceRef:
    def test_path_with_a_path_inside_the_skill_returns_it_under_the_skill_directory(self) -> None:
        #: Given
        ref = SkillResourceRef(
            SkillRef(ResolvedPath(RootRelativePath.parse('.agents/skills')), PathComponent.parse('review')),
            SkillRelativePath.parse('guides/d.md'),
        )

        #: When
        path = ref.path

        #: Then
        assert path == RootRelativePath.parse('.agents/skills/review/guides/d.md'), (
            'the report path is the path inside the skill, spelled from the root through the skill directory'
        )

    def test_init_with_the_skill_file_as_the_path_raises_not_a_skill_resource_error(self) -> None:
        #: Given
        skill = SkillRef(ResolvedPath(RootRelativePath.parse('.agents/skills')), PathComponent.parse('review'))
        path = SkillRelativePath.parse('SKILL.md')

        #: When
        with pytest.raises(NotASkillResourceError) as exc_info:
            SkillResourceRef(skill, path)

        #: Then
        assert exc_info.value.path == path, 'the record refuses the skill file'

    def test_init_with_the_skill_directory_as_the_path_raises_not_a_skill_resource_error(self) -> None:
        #: Given
        skill = SkillRef(ResolvedPath(RootRelativePath.parse('.agents/skills')), PathComponent.parse('review'))
        path = SkillRelativePath.parse('.')

        #: When
        with pytest.raises(NotASkillResourceError) as exc_info:
            SkillResourceRef(skill, path)

        #: Then
        assert exc_info.value.path == path, 'the record refuses the skill directory'

    def test_init_with_a_file_not_named_as_a_document_raises_not_a_skill_resource_error(self) -> None:
        #: Given
        skill = SkillRef(ResolvedPath(RootRelativePath.parse('.agents/skills')), PathComponent.parse('review'))
        path = SkillRelativePath.parse('scripts/run.py')

        #: When
        with pytest.raises(NotASkillResourceError) as exc_info:
            SkillResourceRef(skill, path)

        #: Then
        assert exc_info.value.path == path, 'the record refuses a file not named as a document'
