"""`OUT004`, `empty-section`, over a document's headings.

Every case is a document written as text, read through a fake context that parses it as the real parser does, under
structure specifications decoded from JSON; no document is read from disk.
"""

from typing import Final

import pytest

from lorecraft.core.path import RootRelativePath
from lorecraft.project.syntax import LineNumber
from lorecraft.rules.location import Elsewhere, Help, Note
from lorecraft.rules.tests.fake_context import FakeDocumentContext, namespace_spec, structure_spec_path

from ..empty_section import EmptySection

CORPUS_SPEC: Final[RootRelativePath] = structure_spec_path('guide')
"""The corpus structure specification."""

NAMESPACE_SPEC: Final[RootRelativePath] = structure_spec_path('guide-cli')
"""A namespace structure specification under the same corpus."""

FORBIDS_EMPTY: Final[str] = '{"empty_sections": "forbidden"}'
"""A structure specification that forbids empty sections."""

ALLOWS_EMPTY: Final[str] = '{"forbidden": ["Changelog"]}'
"""A structure specification that states another rule, and leaves empty sections allowed."""

EMPTY_INSTALL: Final[str] = '# Setup\n\n## Install\n\n## Run\n\nRun the toolkit once over the repository.\n'
"""A document whose title holds two sections: `Install`, empty, on line 3, and `Run`, holding prose, on line 5."""


@pytest.mark.unit
class TestEmptySection:
    def test_check_with_an_empty_section_reports_it_at_its_heading(self) -> None:
        #: Given
        subject = FakeDocumentContext(EMPTY_INSTALL, corpus='guide', structure=FORBIDS_EMPTY)

        #: When
        occurrences = EmptySection.check(subject)

        #: Then
        assert occurrences == (EmptySection(spec=CORPUS_SPEC, line=LineNumber.from_int(3), section='Install'),), (
            'an empty section is one occurrence, at its heading, naming the specification that forbids it'
        )

    def test_check_with_empty_sections_allowed_reports_nothing(self) -> None:
        #: Given
        subject = FakeDocumentContext(EMPTY_INSTALL, corpus='guide', structure=ALLOWS_EMPTY)

        #: When
        occurrences = EmptySection.check(subject)

        #: Then
        assert occurrences == (), 'a specification that does not forbid empty sections allows them'

    def test_check_with_every_section_holding_content_reports_nothing(self) -> None:
        #: Given
        subject = FakeDocumentContext(
            '# Setup\n\n## Run\n\nRun the toolkit once over the repository.\n', corpus='guide', structure=FORBIDS_EMPTY
        )

        #: When
        occurrences = EmptySection.check(subject)

        #: Then
        assert occurrences == (), 'a document whose every section holds content has no empty section'

    def test_check_with_an_empty_title_reports_it(self) -> None:
        #: Given
        subject = FakeDocumentContext('# Setup\n', corpus='guide', structure=FORBIDS_EMPTY)

        #: When
        occurrences = EmptySection.check(subject)

        #: Then
        assert occurrences == (EmptySection(spec=CORPUS_SPEC, line=LineNumber.from_int(1), section='Setup'),), (
            'a lone title, which nothing follows, is an empty section like any other'
        )

    def test_check_with_empty_sections_of_different_levels_reports_each_in_order(self) -> None:
        #: Given
        subject = FakeDocumentContext(EMPTY_INSTALL + '\n### Linux\n', corpus='guide', structure=FORBIDS_EMPTY)

        #: When
        occurrences = EmptySection.check(subject)

        #: Then
        assert occurrences == (
            EmptySection(spec=CORPUS_SPEC, line=LineNumber.from_int(3), section='Install'),
            EmptySection(spec=CORPUS_SPEC, line=LineNumber.from_int(9), section='Linux'),
        ), 'every empty heading is reported, whatever its level, in document order'

    def test_check_with_two_specifications_forbidding_empty_sections_reports_each_in_order(self) -> None:
        #: Given
        subject = FakeDocumentContext(
            EMPTY_INSTALL,
            corpus='guide',
            structure=FORBIDS_EMPTY,
            namespaces=(namespace_spec('guide', 'cli', FORBIDS_EMPTY),),
        )

        #: When
        occurrences = EmptySection.check(subject)

        #: Then
        assert occurrences == (
            EmptySection(spec=CORPUS_SPEC, line=LineNumber.from_int(3), section='Install'),
            EmptySection(spec=NAMESPACE_SPEC, line=LineNumber.from_int(3), section='Install'),
        ), 'each specification applies on its own, so the section is reported once for each, in order'

    def test_check_with_one_of_two_specifications_forbidding_empty_sections_reports_under_it_alone(self) -> None:
        #: Given
        subject = FakeDocumentContext(
            EMPTY_INSTALL,
            corpus='guide',
            structure=ALLOWS_EMPTY,
            namespaces=(namespace_spec('guide', 'cli', FORBIDS_EMPTY),),
        )

        #: When
        occurrences = EmptySection.check(subject)

        #: Then
        assert occurrences == (EmptySection(spec=NAMESPACE_SPEC, line=LineNumber.from_int(3), section='Install'),), (
            'a section is reported only under the specification that forbids empty sections'
        )

    def test_message_with_an_occurrence_names_the_section(self) -> None:
        #: Given
        occurrence = EmptySection(spec=CORPUS_SPEC, line=LineNumber.from_int(3), section='Install')

        #: When
        message = occurrence.message()

        #: Then
        assert message == 'section `Install` is empty', 'the message names the empty section'

    def test_children_with_an_occurrence_point_at_the_specification_and_say_to_omit_it(self) -> None:
        #: Given
        occurrence = EmptySection(spec=CORPUS_SPEC, line=LineNumber.from_int(3), section='Install')

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Note('the document structure is set here', at=Elsewhere(CORPUS_SPEC)),
            Help('omit the section rather than leave it empty'),
        ), 'a note points at the specification that forbids empty sections, and a help says to omit the section'
