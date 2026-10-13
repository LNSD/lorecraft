"""What a link's destination is: percent-decoded, then classified, its relative path normalised lexically."""

from pathlib import PurePosixPath

import pytest

from ..link import (
    AbsoluteDestination,
    ExternalDestination,
    FragmentDestination,
    Link,
    NormalisedLinkPath,
    RelativeDestination,
)
from ..position import LineNumber


@pytest.mark.unit
class TestLinkToDestination:
    def test_to_destination_with_a_scheme_returns_external(self) -> None:
        #: Given
        link = Link(url='https://example.com/a.md', line=LineNumber.from_int(1))

        #: When
        destination = link.to_destination()

        #: Then
        assert destination == ExternalDestination(), f'a destination with a scheme is external, got {destination}'

    def test_to_destination_with_an_encoded_leading_slash_returns_absolute(self) -> None:
        #: Given
        link = Link(url='%2Fetc/x.md', line=LineNumber.from_int(1))

        #: When
        destination = link.to_destination()

        #: Then
        assert destination == AbsoluteDestination(), f'the path is decoded, then classified, got {destination}'

    def test_to_destination_with_a_fragment_only_returns_the_fragment(self) -> None:
        #: Given
        link = Link(url='#usage', line=LineNumber.from_int(1))

        #: When
        destination = link.to_destination()

        #: Then
        assert destination == FragmentDestination(fragment='usage'), (
            f'a destination with no path names only a fragment, got {destination}'
        )

    def test_to_destination_with_an_empty_destination_returns_an_empty_fragment(self) -> None:
        #: Given
        link = Link(url='', line=LineNumber.from_int(1))

        #: When
        destination = link.to_destination()

        #: Then
        assert destination == FragmentDestination(fragment=''), (
            f'an empty destination names no fragment, got {destination}'
        )

    def test_to_destination_with_a_query_before_a_fragment_returns_an_empty_fragment(self) -> None:
        #: Given
        link = Link(url='?a=b#usage', line=LineNumber.from_int(1))

        #: When
        destination = link.to_destination()

        #: Then
        assert destination == FragmentDestination(fragment=''), f'a query alone names no fragment, got {destination}'

    def test_to_destination_with_an_encoded_colon_returns_relative(self) -> None:
        #: Given
        link = Link(url='a%3Ab/./c.md#usage', line=LineNumber.from_int(1))

        #: When
        destination = link.to_destination()

        #: Then
        assert destination == RelativeDestination(path=NormalisedLinkPath.parse('a:b/./c.md')), (
            f'the scheme is read as written, so a decoded colon is part of the path, got {destination}'
        )

    def test_to_destination_with_a_dot_component_returns_it_dropped(self) -> None:
        #: Given
        link = Link(url='references/./a%20b.md#usage', line=LineNumber.from_int(1))

        #: When
        destination = link.to_destination()

        #: Then
        assert destination == RelativeDestination(path=NormalisedLinkPath(PurePosixPath('references/a b.md'))), (
            f'a `.` component names nothing and the path is decoded, got {destination}'
        )

    def test_to_destination_with_a_parent_component_returns_it_cancelled(self) -> None:
        #: Given
        link = Link(url='references/../SKILL.md', line=LineNumber.from_int(1))

        #: When
        destination = link.to_destination()

        #: Then
        assert destination == RelativeDestination(path=NormalisedLinkPath(PurePosixPath('SKILL.md'))), (
            f'a `..` cancels the component before it, got {destination}'
        )

    def test_to_destination_with_a_parent_cancelling_every_component_returns_the_start(self) -> None:
        #: Given
        link = Link(url='references/..', line=LineNumber.from_int(1))

        #: When
        destination = link.to_destination()

        #: Then
        assert destination == RelativeDestination(path=NormalisedLinkPath(PurePosixPath('.'))), (
            f'nothing is left but the directory the path is read from, got {destination}'
        )

    def test_to_destination_with_a_leading_parent_keeps_it_first(self) -> None:
        #: Given
        link = Link(url='a/../../b.md', line=LineNumber.from_int(1))

        #: When
        destination = link.to_destination()

        #: Then
        assert destination == RelativeDestination(path=NormalisedLinkPath(PurePosixPath('../b.md'))), (
            f'a `..` with nothing before it to cancel stays, got {destination}'
        )

    def test_to_destination_with_encoded_dots_returns_them_as_a_parent(self) -> None:
        #: Given
        link = Link(url='%2E%2E/a.md', line=LineNumber.from_int(1))

        #: When
        destination = link.to_destination()

        #: Then
        assert destination == RelativeDestination(path=NormalisedLinkPath(PurePosixPath('../a.md'))), (
            f'the path is decoded before it is normalised, got {destination}'
        )
