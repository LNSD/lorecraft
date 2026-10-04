"""The path values: what a root-relative path and a path component accept and reject, and the joins that stay valid."""

from pathlib import PurePosixPath

import pytest

from lorecraft.core.error import Error

from ..path import PathComponent, PathComponentError, RootRelativePath, RootRelativePathError


@pytest.mark.unit
class TestRootRelativePath:
    def test_parse_with_the_root_returns_the_root(self) -> None:
        #: Given
        valid_path = '.'

        #: When
        parsed = RootRelativePath.parse(valid_path)

        #: Then
        assert parsed.value == PurePosixPath('.'), "'.' is the root, spelled '.'"

    def test_parse_with_an_empty_string_returns_the_root(self) -> None:
        #: Given
        valid_path = ''

        #: When
        parsed = RootRelativePath.parse(valid_path)

        #: Then
        assert parsed.value == PurePosixPath('.'), "the empty string is the root, spelled '.'"

    def test_parse_with_a_nested_file_returns_it_unchanged(self) -> None:
        #: Given
        valid_path = 'docs/code/a.md'

        #: When
        parsed = RootRelativePath.parse(valid_path)

        #: Then
        assert parsed.value == PurePosixPath('docs/code/a.md'), 'a nested file path is kept as written'

    def test_parse_with_a_dot_directory_returns_it_unchanged(self) -> None:
        #: Given
        valid_path = '.agents/skills'

        #: When
        parsed = RootRelativePath.parse(valid_path)

        #: Then
        assert parsed.value == PurePosixPath('.agents/skills'), 'a leading-dot directory is a name, not the root'

    def test_parse_with_doubled_slashes_a_dot_and_a_trailing_slash_returns_it_normalized(self) -> None:
        #: Given
        valid_path = 'docs//code/./a.md/'

        #: When
        parsed = RootRelativePath.parse(valid_path)

        #: Then
        assert parsed.value == PurePosixPath('docs/code/a.md'), 'the path is normalized as PurePosixPath does'

    def test_parse_with_an_absolute_path_raises_root_relative_path_error(self) -> None:
        #: Given
        invalid_path = '/etc/passwd'

        #: When
        with pytest.raises(RootRelativePathError) as exc_info:
            RootRelativePath.parse(invalid_path)

        #: Then
        assert exc_info.value.path == PurePosixPath(invalid_path), 'the error retains the rejected absolute path'
        assert invalid_path in str(exc_info.value), 'the message names the rejected path'

    def test_parse_with_the_filesystem_root_raises_root_relative_path_error(self) -> None:
        #: Given
        invalid_path = '/'

        #: When
        with pytest.raises(RootRelativePathError) as exc_info:
            RootRelativePath.parse(invalid_path)

        #: Then
        assert exc_info.value.path == PurePosixPath(invalid_path), "the error retains the rejected '/'"

    def test_parse_with_the_parent_of_the_root_raises_root_relative_path_error(self) -> None:
        #: Given
        invalid_path = '..'

        #: When
        with pytest.raises(RootRelativePathError) as exc_info:
            RootRelativePath.parse(invalid_path)

        #: Then
        assert exc_info.value.path == PurePosixPath(invalid_path), "the error retains the rejected '..'"

    def test_parse_with_a_path_climbing_out_through_a_directory_raises_root_relative_path_error(self) -> None:
        #: Given
        invalid_path = 'docs/../..'

        #: When
        with pytest.raises(RootRelativePathError) as exc_info:
            RootRelativePath.parse(invalid_path)

        #: Then
        assert exc_info.value.path == PurePosixPath(invalid_path), 'the error retains the path that climbs out'

    def test_parse_with_a_path_climbing_and_returning_raises_root_relative_path_error(self) -> None:
        #: Given
        invalid_path = 'docs/../docs/a.md'

        #: When
        with pytest.raises(RootRelativePathError) as exc_info:
            RootRelativePath.parse(invalid_path)

        #: Then
        assert exc_info.value.path == PurePosixPath(invalid_path), (
            'a climb is rejected even when it returns, and the error retains the path'
        )

    def test_parse_with_an_absolute_path_raises_an_error_of_the_package_hierarchy(self) -> None:
        #: Given
        absolute = '/etc'

        #: When
        with pytest.raises(RootRelativePathError) as exc_info:
            RootRelativePath.parse(absolute)

        #: Then
        assert isinstance(exc_info.value, Error), 'callers catching the package hierarchy catch this too'

    def test_construct_with_an_absolute_path_raises_root_relative_path_error(self) -> None:
        #: Given
        absolute = PurePosixPath('/etc')

        #: When
        with pytest.raises(RootRelativePathError) as exc_info:
            RootRelativePath(absolute)

        #: Then
        assert exc_info.value.path == absolute, 'direct construction is checked like parse'

    def test_join_with_the_parent_name_raises_root_relative_path_error(self) -> None:
        #: Given
        docs = RootRelativePath.parse('docs')
        name = '..'

        #: When
        with pytest.raises(RootRelativePathError) as exc_info:
            docs / name

        #: Then
        assert exc_info.type is RootRelativePathError, "joining '..' climbs out of the path, so it is rejected"

    def test_join_with_an_absolute_name_raises_root_relative_path_error(self) -> None:
        #: Given
        docs = RootRelativePath.parse('docs')
        name = '/etc'

        #: When
        with pytest.raises(RootRelativePathError) as exc_info:
            docs / name

        #: Then
        assert exc_info.type is RootRelativePathError, "joining '/etc' would replace the path, so it is rejected"

    def test_join_with_a_climbing_subpath_raises_root_relative_path_error(self) -> None:
        #: Given
        docs = RootRelativePath.parse('docs')
        name = 'sub/../..'

        #: When
        with pytest.raises(RootRelativePathError) as exc_info:
            docs / name

        #: Then
        assert exc_info.type is RootRelativePathError, "joining 'sub/../..' climbs through a subpath, so it is rejected"

    def test_join_with_a_child_name_returns_the_child(self) -> None:
        #: Given
        docs = RootRelativePath.parse('docs')

        #: When
        child = docs / 'code'

        #: Then
        assert child == RootRelativePath.parse('docs/code'), 'a join appends the name as a component'

    def test_join_with_a_path_component_returns_the_child(self) -> None:
        #: Given
        docs = RootRelativePath.parse('docs')
        name = PathComponent.parse('code')

        #: When
        child = docs / name

        #: Then
        assert child == RootRelativePath.parse('docs/code'), 'a component joins as the one name it holds'

    def test_parent_of_the_root_returns_the_root(self) -> None:
        #: Given
        root = RootRelativePath.parse('.')

        #: When
        parent = root.parent

        #: Then
        assert parent == root, 'the root is its own parent, so no parent climbs above it'

    def test_parents_of_a_nested_path_returns_every_ancestor_nearest_first(self) -> None:
        #: Given
        nested = RootRelativePath.parse('docs/code/a.md')

        #: When
        parents = nested.parents

        #: Then
        assert parents == (
            RootRelativePath.parse('docs/code'),
            RootRelativePath.parse('docs'),
            RootRelativePath.parse('.'),
        ), 'the ancestors run from the nearest to the root'

    def test_is_relative_to_with_an_ancestor_directory_returns_true(self) -> None:
        #: Given
        path = RootRelativePath.parse('docs/code/a.md')
        other = RootRelativePath.parse('docs')

        #: When
        contained = path.is_relative_to(other)

        #: Then
        assert contained is True, 'docs/code/a.md sits under its ancestor docs'

    def test_is_relative_to_with_the_path_itself_returns_true(self) -> None:
        #: Given
        path = RootRelativePath.parse('docs/code/a.md')
        other = RootRelativePath.parse('docs/code/a.md')

        #: When
        contained = path.is_relative_to(other)

        #: Then
        assert contained is True, 'a path is relative to itself'

    def test_is_relative_to_with_the_root_returns_true(self) -> None:
        #: Given
        path = RootRelativePath.parse('docs/code/a.md')
        other = RootRelativePath.parse('.')

        #: When
        contained = path.is_relative_to(other)

        #: Then
        assert contained is True, 'every path sits under the root'

    def test_is_relative_to_with_a_sibling_sharing_a_prefix_returns_false(self) -> None:
        #: Given
        path = RootRelativePath.parse('docs/code/a.md')
        other = RootRelativePath.parse('docs/code/a')

        #: When
        contained = path.is_relative_to(other)

        #: Then
        assert contained is False, 'docs/code/a is a string prefix of docs/code/a.md, not a component ancestor'

    def test_sort_with_unsorted_paths_orders_them_by_path(self) -> None:
        #: Given
        unsorted = [RootRelativePath.parse('docs/b.md'), RootRelativePath.parse('docs/a.md')]

        #: When
        ordered = sorted(unsorted)

        #: Then
        assert ordered == [RootRelativePath.parse('docs/a.md'), RootRelativePath.parse('docs/b.md')], (
            'paths sort as the snapshot sorts its records'
        )

    def test_str_with_a_nested_path_returns_the_posix_spelling(self) -> None:
        #: Given
        path = RootRelativePath.parse('docs/code/a.md')

        #: When
        text = str(path)

        #: Then
        assert text == 'docs/code/a.md', f'str should give the POSIX spelling, got {text!r}'


@pytest.mark.unit
class TestPathComponent:
    def test_parse_with_a_filename_returns_it_unchanged(self) -> None:
        #: Given
        valid_name = 'SKILL.md'

        #: When
        parsed = PathComponent.parse(valid_name)

        #: Then
        assert parsed.value == 'SKILL.md', 'a filename is kept exactly as written'

    def test_parse_with_a_leading_dot_name_returns_it_unchanged(self) -> None:
        #: Given
        valid_name = '.agents'

        #: When
        parsed = PathComponent.parse(valid_name)

        #: Then
        assert parsed.value == '.agents', 'a leading-dot name is a name, not the current directory'

    def test_parse_with_an_empty_name_raises_path_component_error(self) -> None:
        #: Given
        invalid_name = ''

        #: When
        with pytest.raises(PathComponentError) as exc_info:
            PathComponent.parse(invalid_name)

        #: Then
        assert exc_info.value.name == invalid_name, 'the error retains the rejected empty name'

    def test_parse_with_the_current_directory_raises_path_component_error(self) -> None:
        #: Given
        invalid_name = '.'

        #: When
        with pytest.raises(PathComponentError) as exc_info:
            PathComponent.parse(invalid_name)

        #: Then
        assert exc_info.value.name == invalid_name, "the error retains the rejected '.'"

    def test_parse_with_the_parent_directory_raises_path_component_error(self) -> None:
        #: Given
        invalid_name = '..'

        #: When
        with pytest.raises(PathComponentError) as exc_info:
            PathComponent.parse(invalid_name)

        #: Then
        assert exc_info.value.name == invalid_name, "the error retains the rejected '..'"
        assert repr(invalid_name) in str(exc_info.value), 'the message names the rejected name'

    def test_parse_with_a_name_holding_a_slash_raises_path_component_error(self) -> None:
        #: Given
        invalid_name = 'docs/a.md'

        #: When
        with pytest.raises(PathComponentError) as exc_info:
            PathComponent.parse(invalid_name)

        #: Then
        assert exc_info.value.name == invalid_name, 'the error retains the rejected name with its slash'

    def test_parse_with_an_empty_name_raises_an_error_of_the_package_hierarchy(self) -> None:
        #: Given
        invalid_name = ''

        #: When
        with pytest.raises(PathComponentError) as exc_info:
            PathComponent.parse(invalid_name)

        #: Then
        assert isinstance(exc_info.value, Error), 'callers catching the package hierarchy catch this too'

    def test_construct_with_a_name_holding_a_slash_raises_path_component_error(self) -> None:
        #: Given
        invalid_name = 'a/b'

        #: When
        with pytest.raises(PathComponentError) as exc_info:
            PathComponent(invalid_name)

        #: Then
        assert exc_info.value.name == invalid_name, 'direct construction is checked like parse'

    def test_sort_with_unsorted_components_orders_them_by_name(self) -> None:
        #: Given
        unsorted = [PathComponent.parse('b.md'), PathComponent.parse('a.md')]

        #: When
        ordered = sorted(unsorted)

        #: Then
        assert ordered == [PathComponent.parse('a.md'), PathComponent.parse('b.md')], (
            'components sort by name, as a listing sorts its entries'
        )

    def test_str_with_a_filename_returns_the_name(self) -> None:
        #: Given
        name = PathComponent.parse('SKILL.md')

        #: When
        text = str(name)

        #: Then
        assert text == 'SKILL.md', f'str should give the name as written, got {text!r}'
