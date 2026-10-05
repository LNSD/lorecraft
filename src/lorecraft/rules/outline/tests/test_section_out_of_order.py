"""`OUT007`, `section-out-of-order`, over where a document's sections first stop matching their outlines.

The rule is pure, so every case here is the divergence each outline found, written as literals; no document is
read and no outline is matched.
"""

from typing import Final

import pytest

from lorecraft.core.path import RootRelativePath
from lorecraft.project.schemas import SectionName
from lorecraft.project.syntax import Heading, LineNumber
from lorecraft.rules.inputs import (
    AbsentSection,
    MisplacedSection,
    OutlineDivergenceInput,
    OutlineDivergenceSpec,
    UnlistedSection,
)
from lorecraft.rules.location import Elsewhere, Here, Label, Note

from ..section_out_of_order import SectionOutOfOrder

CORPUS_SPEC: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/guide.structure.json')
"""A corpus structure specification."""

NAMESPACE_SPEC: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/guide-cli.structure.json')
"""A namespace structure specification under the same corpus."""

USAGE: Final[SectionName] = SectionName.parse('Usage')
"""The section the outline places where `Options` is written, which the document writes further down."""

OPTIONS: Final[Heading] = Heading(level=2, text='Options', line=LineNumber.from_int(3), empty=False, words=4)
"""An H2 section on line 3, written where `Usage` was expected."""

EXAMPLES: Final[Heading] = Heading(level=2, text='Examples', line=LineNumber.from_int(11), empty=False, words=6)
"""An H2 section on line 11, left over after every section the outline matched."""


@pytest.mark.unit
class TestSectionOutOfOrder:
    def test_check_with_a_section_in_place_of_a_later_one_reports_it_at_its_heading(self) -> None:
        #: Given
        misplaced = MisplacedSection(section=OPTIONS, expected=USAGE)
        subject = OutlineDivergenceInput(specs=(OutlineDivergenceSpec(spec=CORPUS_SPEC, divergence=misplaced),))

        #: When
        occurrences = SectionOutOfOrder.check(subject)

        #: Then
        assert occurrences == (
            SectionOutOfOrder(spec=CORPUS_SPEC, line=OPTIONS.line, section=OPTIONS.text, expected=USAGE),
        ), 'a section standing where the outline places a later one is one occurrence, at its heading'

    def test_check_with_a_section_left_over_reports_it_with_nothing_expected(self) -> None:
        #: Given
        misplaced = MisplacedSection(section=EXAMPLES, expected=None)
        subject = OutlineDivergenceInput(specs=(OutlineDivergenceSpec(spec=CORPUS_SPEC, divergence=misplaced),))

        #: When
        occurrences = SectionOutOfOrder.check(subject)

        #: Then
        assert occurrences == (
            SectionOutOfOrder(spec=CORPUS_SPEC, line=EXAMPLES.line, section=EXAMPLES.text, expected=None),
        ), 'a named section left over once the outline is used up is reported at its heading, with none expected'

    def test_check_with_an_absent_section_reports_nothing(self) -> None:
        #: Given
        absent = AbsentSection(name=USAGE, description=None, example=None, before=OPTIONS)
        subject = OutlineDivergenceInput(specs=(OutlineDivergenceSpec(spec=CORPUS_SPEC, divergence=absent),))

        #: When
        occurrences = SectionOutOfOrder.check(subject)

        #: Then
        assert occurrences == (), 'a missing section is never a section out of order'

    def test_check_with_an_unlisted_section_reports_nothing(self) -> None:
        #: Given
        unlisted = UnlistedSection(section=OPTIONS, expected=USAGE)
        subject = OutlineDivergenceInput(specs=(OutlineDivergenceSpec(spec=CORPUS_SPEC, divergence=unlisted),))

        #: When
        occurrences = SectionOutOfOrder.check(subject)

        #: Then
        assert occurrences == (), 'a section the outline does not name is never a section out of order'

    def test_check_with_no_divergence_reports_nothing(self) -> None:
        #: Given
        subject = OutlineDivergenceInput(specs=(OutlineDivergenceSpec(spec=CORPUS_SPEC, divergence=None),))

        #: When
        occurrences = SectionOutOfOrder.check(subject)

        #: Then
        assert occurrences == (), 'a document that matches its outline has no section out of order'

    def test_check_with_a_section_out_of_order_under_both_specifications_reports_each_in_order(self) -> None:
        #: Given
        subject = OutlineDivergenceInput(
            specs=(
                OutlineDivergenceSpec(spec=CORPUS_SPEC, divergence=MisplacedSection(section=OPTIONS, expected=USAGE)),
                OutlineDivergenceSpec(
                    spec=NAMESPACE_SPEC, divergence=MisplacedSection(section=EXAMPLES, expected=None)
                ),
            )
        )

        #: When
        occurrences = SectionOutOfOrder.check(subject)

        #: Then
        assert occurrences == (
            SectionOutOfOrder(spec=CORPUS_SPEC, line=OPTIONS.line, section=OPTIONS.text, expected=USAGE),
            SectionOutOfOrder(spec=NAMESPACE_SPEC, line=EXAMPLES.line, section=EXAMPLES.text, expected=None),
        ), 'each specification applies on its own, so the document is reported once for each, in order'

    def test_message_with_an_occurrence_names_the_section(self) -> None:
        #: Given
        occurrence = SectionOutOfOrder(spec=CORPUS_SPEC, line=OPTIONS.line, section=OPTIONS.text, expected=USAGE)

        #: When
        message = occurrence.message()

        #: Then
        assert message == 'section `Options` is out of order', 'the message names the section written out of order'

    def test_labels_with_a_section_expected_name_it(self) -> None:
        #: Given
        occurrence = SectionOutOfOrder(spec=CORPUS_SPEC, line=OPTIONS.line, section=OPTIONS.text, expected=USAGE)

        #: When
        labels = occurrence.labels()

        #: Then
        assert labels == (Label(Here(LineNumber.from_int(3)), 'expected `Usage` here'),), (
            'the label marks the section, and names the one the outline places there instead'
        )

    def test_labels_with_no_section_expected_say_it_is_left_over(self) -> None:
        #: Given
        occurrence = SectionOutOfOrder(spec=CORPUS_SPEC, line=EXAMPLES.line, section=EXAMPLES.text, expected=None)

        #: When
        labels = occurrence.labels()

        #: Then
        assert labels == (Label(Here(LineNumber.from_int(11)), 'left over after every section the outline matched'),), (
            'the label marks the section, and says it comes after every section the outline matched'
        )

    def test_children_with_an_occurrence_point_at_the_specification(self) -> None:
        #: Given
        occurrence = SectionOutOfOrder(spec=CORPUS_SPEC, line=OPTIONS.line, section=OPTIONS.text, expected=USAGE)

        #: When
        children = occurrence.children()

        #: Then
        assert children == (Note('the document structure is set here', at=Elsewhere(CORPUS_SPEC)),), (
            'a note points at the specification whose outline sets the order'
        )
