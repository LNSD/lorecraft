"""The relative path a link's destination spells, read without resolving it against any directory."""

from pathlib import PurePosixPath

import pytest

from ..link import Link
from ..position import LineNumber


@pytest.mark.unit
class TestLinkToRelativePath:
    def test_to_relative_path_with_a_relative_destination_returns_its_path(self) -> None:
        #: Given
        link = Link(url='references/guide.md', line=LineNumber(1))

        #: When
        path = link.to_relative_path()

        #: Then
        assert path == PurePosixPath('references/guide.md'), f'a relative destination is its own path, got {path}'

    def test_to_relative_path_with_parent_components_keeps_them_unnormalised(self) -> None:
        #: Given
        link = Link(url='references/../../SKILL.md', line=LineNumber(1))

        #: When
        path = link.to_relative_path()

        #: Then
        assert path == PurePosixPath('references/../../SKILL.md'), (
            f'the path is read as written, and normalising it is for the caller, got {path}'
        )

    def test_to_relative_path_with_a_fragment_returns_the_path_before_it(self) -> None:
        #: Given
        link = Link(url='other.md#usage', line=LineNumber(1))

        #: When
        path = link.to_relative_path()

        #: Then
        assert path == PurePosixPath('other.md'), f'the fragment is not part of the path, got {path}'

    def test_to_relative_path_with_a_query_returns_the_path_before_it(self) -> None:
        #: Given
        link = Link(url='other.md?from=/../x#usage', line=LineNumber(1))

        #: When
        path = link.to_relative_path()

        #: Then
        assert path == PurePosixPath('other.md'), f'the query is not part of the path, got {path}'

    def test_to_relative_path_with_a_percent_encoded_destination_returns_it_decoded(self) -> None:
        #: Given
        link = Link(url='%2E%2E/a%20b.md', line=LineNumber(1))

        #: When
        path = link.to_relative_path()

        #: Then
        assert path == PurePosixPath('../a b.md'), f'the path is percent-decoded, as the author wrote it, got {path}'

    def test_to_relative_path_with_a_url_scheme_returns_none(self) -> None:
        #: Given
        link = Link(url='https://agentskills.io/specification', line=LineNumber(1))

        #: When
        path = link.to_relative_path()

        #: Then
        assert path is None, f'a URL with a scheme spells no relative path, got {path}'

    def test_to_relative_path_with_a_scheme_without_slashes_returns_none(self) -> None:
        #: Given
        link = Link(url='mailto:team@example.com', line=LineNumber(1))

        #: When
        path = link.to_relative_path()

        #: Then
        assert path is None, f'a scheme needs no `//` to make a URL, got {path}'

    def test_to_relative_path_with_an_absolute_destination_returns_none(self) -> None:
        #: Given
        link = Link(url='/docs/guide.md', line=LineNumber(1))

        #: When
        path = link.to_relative_path()

        #: Then
        assert path is None, f'a destination from the filesystem root is not relative, got {path}'

    def test_to_relative_path_with_an_encoded_leading_slash_returns_none(self) -> None:
        #: Given
        link = Link(url='%2Fdocs/guide.md', line=LineNumber(1))

        #: When
        path = link.to_relative_path()

        #: Then
        assert path is None, f'a destination absolute once decoded is not relative either, got {path}'

    def test_to_relative_path_with_a_fragment_only_destination_returns_none(self) -> None:
        #: Given
        link = Link(url='#usage', line=LineNumber(1))

        #: When
        path = link.to_relative_path()

        #: Then
        assert path is None, f'a fragment-only destination stays in its own file and spells no path, got {path}'

    def test_to_relative_path_with_an_empty_destination_returns_none(self) -> None:
        #: Given
        link = Link(url='', line=LineNumber(1))

        #: When
        path = link.to_relative_path()

        #: Then
        assert path is None, f'an empty destination spells no path, got {path}'
