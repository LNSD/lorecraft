"""`OUT004`, `empty-section`, over a document's headings.

The rule is pure, so every case here is a document's headings and what each specification states, written as
literals; no document is read.
"""

from typing import Final

import pytest

from lorecraft.core.path import RootRelativePath
from lorecraft.project.syntax import Heading, LineNumber
from lorecraft.rules.inputs import HeadingsInput, HeadingsSpec
from lorecraft.rules.location import Elsewhere, Help, Note

from ..empty_section import EmptySection

CORPUS_SPEC: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/guide.structure.json')
"""A corpus structure specification."""

NAMESPACE_SPEC: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/guide-cli.structure.json')
"""A namespace structure specification under the same corpus."""

TITLE: Final[Heading] = Heading(level=1, text='Setup', line=LineNumber.from_int(1), empty=False, words=0)
"""An H1 title on line 1, holding the sections below it."""

INSTALL: Final[Heading] = Heading(level=2, text='Install', line=LineNumber.from_int(3), empty=True, words=0)
"""An empty H2 section on line 3."""

RUN: Final[Heading] = Heading(level=2, text='Run', line=LineNumber.from_int(5), empty=False, words=6)
"""An H2 section on line 5, holding prose."""


def _spec(spec: RootRelativePath, *, forbid_empty_sections: bool) -> HeadingsSpec:
    """What a specification states over the headings: whether it forbids empty sections, alone.

    Args:
        spec: The structure specification file.
        forbid_empty_sections: True when it forbids empty sections.
    """
    return HeadingsSpec(
        spec=spec,
        title_mismatch=None,
        forbid_empty_sections=forbid_empty_sections,
        forbidden=(),
    )


@pytest.mark.unit
class TestEmptySection:
    def test_check_with_an_empty_section_reports_it_at_its_heading(self) -> None:
        #: Given
        subject = HeadingsInput(
            headings=(TITLE, INSTALL, RUN), corpus=_spec(CORPUS_SPEC, forbid_empty_sections=True), namespaces=()
        )

        #: When
        occurrences = EmptySection.check(subject)

        #: Then
        assert occurrences == (EmptySection(spec=CORPUS_SPEC, line=LineNumber.from_int(3), section='Install'),), (
            'an empty section is one occurrence, at its heading, naming the specification that forbids it'
        )

    def test_check_with_empty_sections_allowed_reports_nothing(self) -> None:
        #: Given
        subject = HeadingsInput(
            headings=(TITLE, INSTALL, RUN), corpus=_spec(CORPUS_SPEC, forbid_empty_sections=False), namespaces=()
        )

        #: When
        occurrences = EmptySection.check(subject)

        #: Then
        assert occurrences == (), 'a specification that does not forbid empty sections allows them'

    def test_check_with_every_section_holding_content_reports_nothing(self) -> None:
        #: Given
        subject = HeadingsInput(
            headings=(TITLE, RUN), corpus=_spec(CORPUS_SPEC, forbid_empty_sections=True), namespaces=()
        )

        #: When
        occurrences = EmptySection.check(subject)

        #: Then
        assert occurrences == (), 'a document whose every section holds content has no empty section'

    def test_check_with_an_empty_title_reports_it(self) -> None:
        #: Given
        title = Heading(level=1, text='Setup', line=LineNumber.from_int(1), empty=True, words=0)
        subject = HeadingsInput(headings=(title,), corpus=_spec(CORPUS_SPEC, forbid_empty_sections=True), namespaces=())

        #: When
        occurrences = EmptySection.check(subject)

        #: Then
        assert occurrences == (EmptySection(spec=CORPUS_SPEC, line=LineNumber.from_int(1), section='Setup'),), (
            'a lone title, which nothing follows, is an empty section like any other'
        )

    def test_check_with_empty_sections_of_different_levels_reports_each_in_order(self) -> None:
        #: Given
        subsection = Heading(level=3, text='Linux', line=LineNumber.from_int(7), empty=True, words=0)
        subject = HeadingsInput(
            headings=(TITLE, INSTALL, RUN, subsection),
            corpus=_spec(CORPUS_SPEC, forbid_empty_sections=True),
            namespaces=(),
        )

        #: When
        occurrences = EmptySection.check(subject)

        #: Then
        assert occurrences == (
            EmptySection(spec=CORPUS_SPEC, line=LineNumber.from_int(3), section='Install'),
            EmptySection(spec=CORPUS_SPEC, line=LineNumber.from_int(7), section='Linux'),
        ), 'every empty heading is reported, whatever its level, in document order'

    def test_check_with_two_specifications_forbidding_empty_sections_reports_each_in_order(self) -> None:
        #: Given
        subject = HeadingsInput(
            headings=(TITLE, INSTALL, RUN),
            corpus=_spec(CORPUS_SPEC, forbid_empty_sections=True),
            namespaces=(_spec(NAMESPACE_SPEC, forbid_empty_sections=True),),
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
        subject = HeadingsInput(
            headings=(TITLE, INSTALL, RUN),
            corpus=_spec(CORPUS_SPEC, forbid_empty_sections=False),
            namespaces=(_spec(NAMESPACE_SPEC, forbid_empty_sections=True),),
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
