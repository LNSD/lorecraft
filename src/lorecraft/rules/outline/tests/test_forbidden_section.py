"""`OUT005`, `forbidden-section`, over a document's headings.

The rule is pure, so every case here is a document's headings and what each specification states, written as
literals; no document is read.
"""

from typing import Final

import pytest

from lorecraft.core.path import RootRelativePath
from lorecraft.project.schemas import SectionName
from lorecraft.project.syntax import Heading, LineNumber
from lorecraft.rules.inputs import HeadingsInput, HeadingsSpec
from lorecraft.rules.location import Elsewhere, Note

from ..forbidden_section import ForbiddenSection

CORPUS_SPEC: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/guide.structure.json')
"""A corpus structure specification."""

NAMESPACE_SPEC: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/guide-cli.structure.json')
"""A namespace structure specification under the same corpus."""

CHANGELOG: Final[SectionName] = SectionName.parse('Changelog')
"""A section name a specification forbids."""

TITLE: Final[Heading] = Heading(level=1, text='Setup', line=LineNumber.from_int(1), empty=False, words=0)
"""An H1 title on line 1, holding the sections below it."""

RUN: Final[Heading] = Heading(level=2, text='Run', line=LineNumber.from_int(3), empty=False, words=6)
"""An H2 section on line 3, holding prose."""

CHANGELOG_SECTION: Final[Heading] = Heading(
    level=2, text='Changelog', line=LineNumber.from_int(7), empty=False, words=4
)
"""An H2 section named `Changelog` on line 7, holding prose."""


def _spec(spec: RootRelativePath, *, forbidden: tuple[SectionName, ...]) -> HeadingsSpec:
    """What a specification states over the headings: the sections it forbids, alone.

    Args:
        spec: The structure specification file.
        forbidden: The sections it forbids.
    """
    return HeadingsSpec(
        spec=spec,
        title_cap=None,
        title_mismatch=None,
        forbid_empty_sections=False,
        forbidden=forbidden,
        section_caps=(),
    )


@pytest.mark.unit
class TestForbiddenSection:
    def test_check_with_a_forbidden_section_reports_it_at_its_heading(self) -> None:
        #: Given
        subject = HeadingsInput(
            headings=(TITLE, RUN, CHANGELOG_SECTION), corpus=_spec(CORPUS_SPEC, forbidden=(CHANGELOG,)), namespaces=()
        )

        #: When
        occurrences = ForbiddenSection.check(subject)

        #: Then
        assert occurrences == (ForbiddenSection(spec=CORPUS_SPEC, line=LineNumber.from_int(7), section='Changelog'),), (
            'a forbidden section is one occurrence, at its heading, naming the specification that forbids it'
        )

    def test_check_with_no_forbidden_section_present_reports_nothing(self) -> None:
        #: Given
        subject = HeadingsInput(headings=(TITLE, RUN), corpus=_spec(CORPUS_SPEC, forbidden=(CHANGELOG,)), namespaces=())

        #: When
        occurrences = ForbiddenSection.check(subject)

        #: Then
        assert occurrences == (), 'a document without the forbidden section breaks nothing'

    def test_check_with_nothing_forbidden_reports_nothing(self) -> None:
        #: Given
        subject = HeadingsInput(
            headings=(TITLE, RUN, CHANGELOG_SECTION), corpus=_spec(CORPUS_SPEC, forbidden=()), namespaces=()
        )

        #: When
        occurrences = ForbiddenSection.check(subject)

        #: Then
        assert occurrences == (), 'a specification that forbids no section allows every section'

    def test_check_with_a_deeper_heading_of_a_forbidden_name_reports_nothing(self) -> None:
        #: Given
        subsection = Heading(level=3, text='Changelog', line=LineNumber.from_int(5), empty=False, words=4)
        subject = HeadingsInput(
            headings=(TITLE, RUN, subsection), corpus=_spec(CORPUS_SPEC, forbidden=(CHANGELOG,)), namespaces=()
        )

        #: When
        occurrences = ForbiddenSection.check(subject)

        #: Then
        assert occurrences == (), 'a deeper heading of a forbidden name is a subsection, not a forbidden section'

    def test_check_with_a_forbidden_section_written_twice_reports_each_in_order(self) -> None:
        #: Given
        again = Heading(level=2, text='Changelog', line=LineNumber.from_int(11), empty=False, words=3)
        subject = HeadingsInput(
            headings=(TITLE, RUN, CHANGELOG_SECTION, again),
            corpus=_spec(CORPUS_SPEC, forbidden=(CHANGELOG,)),
            namespaces=(),
        )

        #: When
        occurrences = ForbiddenSection.check(subject)

        #: Then
        assert occurrences == (
            ForbiddenSection(spec=CORPUS_SPEC, line=LineNumber.from_int(7), section='Changelog'),
            ForbiddenSection(spec=CORPUS_SPEC, line=LineNumber.from_int(11), section='Changelog'),
        ), 'every occurrence of a forbidden section is reported, not only the first, in document order'

    def test_check_with_two_forbidden_sections_reports_each_in_document_order(self) -> None:
        #: Given
        history = Heading(level=2, text='History', line=LineNumber.from_int(5), empty=False, words=2)
        forbidden = (CHANGELOG, SectionName.parse('History'))
        subject = HeadingsInput(
            headings=(TITLE, RUN, history, CHANGELOG_SECTION),
            corpus=_spec(CORPUS_SPEC, forbidden=forbidden),
            namespaces=(),
        )

        #: When
        occurrences = ForbiddenSection.check(subject)

        #: Then
        assert occurrences == (
            ForbiddenSection(spec=CORPUS_SPEC, line=LineNumber.from_int(5), section='History'),
            ForbiddenSection(spec=CORPUS_SPEC, line=LineNumber.from_int(7), section='Changelog'),
        ), 'each forbidden section is reported in document order, not in the order the specification names them'

    def test_check_with_two_specifications_forbidding_the_section_reports_each_in_order(self) -> None:
        #: Given
        subject = HeadingsInput(
            headings=(TITLE, RUN, CHANGELOG_SECTION),
            corpus=_spec(CORPUS_SPEC, forbidden=(CHANGELOG,)),
            namespaces=(_spec(NAMESPACE_SPEC, forbidden=(CHANGELOG,)),),
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
        subject = HeadingsInput(
            headings=(TITLE, RUN, CHANGELOG_SECTION),
            corpus=_spec(CORPUS_SPEC, forbidden=()),
            namespaces=(_spec(NAMESPACE_SPEC, forbidden=(CHANGELOG,)),),
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
