"""`OUT005`, `forbidden-section`, over a document's headings.

Every case is a document written as text, read through a fake context that parses it as the real parser does, under
structure specifications decoded from JSON; no document is read from disk.
"""

from typing import Final

import pytest

from lorecraft.core.path import RootRelativePath
from lorecraft.project.syntax import LineNumber
from lorecraft.rules.location import Elsewhere, Note
from lorecraft.rules.tests.fake_context import FakeDocumentContext, namespace_spec, structure_spec_path

from ..forbidden_section import ForbiddenSection

CORPUS_SPEC: Final[RootRelativePath] = structure_spec_path('guide')
"""The corpus structure specification."""

NAMESPACE_SPEC: Final[RootRelativePath] = structure_spec_path('guide-cli')
"""A namespace structure specification under the same corpus."""

FORBIDS_CHANGELOG: Final[str] = '{"forbidden": ["Changelog"]}'
"""A structure specification that forbids the section `Changelog`."""

FORBIDS_NOTHING: Final[str] = '{"empty_sections": "forbidden"}'
"""A structure specification that states another rule, and forbids no section."""

RUN: Final[str] = '# Setup\n\n## Run\n\nRun the toolkit once over the repository.\n'
"""A document of five lines: its title, then the section `Run` on line 3."""

WITH_CHANGELOG: Final[str] = RUN + '\n## Changelog\n\nAdded the run step.\n'
"""`RUN`, followed by the section `Changelog` on line 7."""


@pytest.mark.unit
class TestForbiddenSection:
    def test_check_with_a_forbidden_section_reports_it_at_its_heading(self) -> None:
        #: Given
        subject = FakeDocumentContext(WITH_CHANGELOG, corpus='guide', structure=FORBIDS_CHANGELOG)

        #: When
        occurrences = ForbiddenSection.check(subject)

        #: Then
        assert occurrences == (ForbiddenSection(spec=CORPUS_SPEC, line=LineNumber.from_int(7), section='Changelog'),), (
            'a forbidden section is one occurrence, at its heading, naming the specification that forbids it'
        )

    def test_check_with_no_forbidden_section_present_reports_nothing(self) -> None:
        #: Given
        subject = FakeDocumentContext(RUN, corpus='guide', structure=FORBIDS_CHANGELOG)

        #: When
        occurrences = ForbiddenSection.check(subject)

        #: Then
        assert occurrences == (), 'a document without the forbidden section breaks nothing'

    def test_check_with_nothing_forbidden_reports_nothing(self) -> None:
        #: Given
        subject = FakeDocumentContext(WITH_CHANGELOG, corpus='guide', structure=FORBIDS_NOTHING)

        #: When
        occurrences = ForbiddenSection.check(subject)

        #: Then
        assert occurrences == (), 'a specification that forbids no section allows every section'

    def test_check_with_a_deeper_heading_of_a_forbidden_name_reports_nothing(self) -> None:
        #: Given
        subject = FakeDocumentContext(
            RUN + '\n### Changelog\n\nAdded the run step.\n', corpus='guide', structure=FORBIDS_CHANGELOG
        )

        #: When
        occurrences = ForbiddenSection.check(subject)

        #: Then
        assert occurrences == (), 'a deeper heading of a forbidden name is a subsection, not a forbidden section'

    def test_check_with_a_forbidden_section_written_twice_reports_each_in_order(self) -> None:
        #: Given
        text = WITH_CHANGELOG + '\n## Changelog\n\nAdded the title.\n'
        subject = FakeDocumentContext(text, corpus='guide', structure=FORBIDS_CHANGELOG)

        #: When
        occurrences = ForbiddenSection.check(subject)

        #: Then
        assert occurrences == (
            ForbiddenSection(spec=CORPUS_SPEC, line=LineNumber.from_int(7), section='Changelog'),
            ForbiddenSection(spec=CORPUS_SPEC, line=LineNumber.from_int(11), section='Changelog'),
        ), 'every occurrence of a forbidden section is reported, not only the first, in document order'

    def test_check_with_two_forbidden_sections_reports_each_in_document_order(self) -> None:
        #: Given
        text = RUN + '\n## History\n\nFirst written.\n\n## Changelog\n\nAdded the run step.\n'
        subject = FakeDocumentContext(text, corpus='guide', structure='{"forbidden": ["Changelog", "History"]}')

        #: When
        occurrences = ForbiddenSection.check(subject)

        #: Then
        assert occurrences == (
            ForbiddenSection(spec=CORPUS_SPEC, line=LineNumber.from_int(7), section='History'),
            ForbiddenSection(spec=CORPUS_SPEC, line=LineNumber.from_int(11), section='Changelog'),
        ), 'each forbidden section is reported in document order, not in the order the specification names them'

    def test_check_with_two_specifications_forbidding_the_section_reports_each_in_order(self) -> None:
        #: Given
        subject = FakeDocumentContext(
            WITH_CHANGELOG,
            corpus='guide',
            structure=FORBIDS_CHANGELOG,
            namespaces=(namespace_spec('guide', 'cli', FORBIDS_CHANGELOG),),
        )

        #: When
        occurrences = ForbiddenSection.check(subject)

        #: Then
        assert occurrences == (
            ForbiddenSection(spec=CORPUS_SPEC, line=LineNumber.from_int(7), section='Changelog'),
            ForbiddenSection(spec=NAMESPACE_SPEC, line=LineNumber.from_int(7), section='Changelog'),
        ), 'each specification applies on its own, so the section is reported once for each, in order'

    def test_check_with_one_of_two_specifications_forbidding_the_section_reports_under_it_alone(self) -> None:
        #: Given
        subject = FakeDocumentContext(
            WITH_CHANGELOG,
            corpus='guide',
            structure=FORBIDS_NOTHING,
            namespaces=(namespace_spec('guide', 'cli', FORBIDS_CHANGELOG),),
        )

        #: When
        occurrences = ForbiddenSection.check(subject)

        #: Then
        assert occurrences == (
            ForbiddenSection(spec=NAMESPACE_SPEC, line=LineNumber.from_int(7), section='Changelog'),
        ), 'a section is reported only under the specification that forbids it'

    def test_message_with_an_occurrence_names_the_section(self) -> None:
        #: Given
        occurrence = ForbiddenSection(spec=CORPUS_SPEC, line=LineNumber.from_int(7), section='Changelog')

        #: When
        message = occurrence.message()

        #: Then
        assert message == 'section `Changelog` is forbidden', 'the message names the forbidden section'

    def test_children_with_an_occurrence_point_at_the_specification(self) -> None:
        #: Given
        occurrence = ForbiddenSection(spec=CORPUS_SPEC, line=LineNumber.from_int(7), section='Changelog')

        #: When
        children = occurrence.children()

        #: Then
        assert children == (Note('the document structure is set here', at=Elsewhere(CORPUS_SPEC)),), (
            'a note points at the specification that forbids the section'
        )
