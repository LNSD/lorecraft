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


@pytest.mark.unit
class TestLinkToNormalisedRelativePath:
    def test_to_normalised_relative_path_with_dot_components_returns_them_dropped(self) -> None:
        #: Given
        link = Link(url='references/./a%20b.md#usage', line=LineNumber(1))

        #: When
        path = link.to_normalised_relative_path()

        #: Then
        assert path == PurePosixPath('references/a b.md'), f'a `.` component names nothing, got {path}'

    def test_to_normalised_relative_path_with_a_parent_below_the_start_returns_it_cancelled(self) -> None:
        #: Given
        link = Link(url='references/deep/../a.md', line=LineNumber(1))

        #: When
        path = link.to_normalised_relative_path()

        #: Then
        assert path == PurePosixPath('references/a.md'), f'a `..` cancels the component before it, got {path}'

    def test_to_normalised_relative_path_with_a_parent_cancelling_every_component_returns_the_start(self) -> None:
        #: Given
        link = Link(url='references/..', line=LineNumber(1))

        #: When
        path = link.to_normalised_relative_path()

        #: Then
        assert path == PurePosixPath('.'), f'nothing is left but the directory the path is read from, got {path}'

    def test_to_normalised_relative_path_with_a_leading_parent_keeps_it_first(self) -> None:
        #: Given
        link = Link(url='a/../../b.md', line=LineNumber(1))

        #: When
        path = link.to_normalised_relative_path()

        #: Then
        assert path == PurePosixPath('../b.md'), f'a `..` with nothing before it to cancel stays, got {path}'

    def test_to_normalised_relative_path_with_a_url_returns_none(self) -> None:
        #: Given
        link = Link(url='https://agentskills.io/../specification', line=LineNumber(1))

        #: When
        path = link.to_normalised_relative_path()

        #: Then
        assert path is None, f'a destination that spells no relative path has none to normalise, got {path}'
