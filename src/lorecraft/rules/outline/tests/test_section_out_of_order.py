"""`OUT007`, `section-out-of-order`, over where a document's sections first stop matching their outlines.

Every case is a document written as text, read through a fake context that parses it and matches it against its
outlines as the real parser and matcher do, under structure specifications decoded from JSON; no document is read from
disk. Where each divergence falls is the matcher's, tested beside it, so a case here only shows which one the rule
reports.
"""

from typing import Final

import pytest

from lorecraft.core.path import RootRelativePath
from lorecraft.project.schemas import ExpectedSection, LeftOver, SectionName
from lorecraft.project.syntax import LineNumber
from lorecraft.rules.location import Elsewhere, Help, Here, Label, Note
from lorecraft.rules.tests.fake_context import FakeDocumentContext, heading_in, namespace_spec, structure_spec_path

from ..section_out_of_order import SectionOutOfOrder

CORPUS_SPEC: Final[RootRelativePath] = structure_spec_path('guide')
"""The corpus structure specification."""

NAMESPACE_SPEC: Final[RootRelativePath] = structure_spec_path('guide-cli')
"""A namespace structure specification under the same corpus."""


OUTLINE: Final[str] = '{"outline": [{"section": "Usage"}, {"section": "Options"}]}'
"""An outline requiring `Usage`, then `Options`."""

FOLLOWS: Final[str] = '# Check\n\n## Usage\n\nRun it.\n\n## Options\n\nPass a flag.\n'
"""A document writing `Usage`, then `Options`."""

OUT_OF_ORDER: Final[str] = '# Check\n\n## Options\n\nPass a flag.\n\n## Usage\n\nRun it.\n'
"""A document writing `Options` on line 3, then `Usage`."""

LEFT_OVER: Final[str] = FOLLOWS + '\n## Usage\n\nRun it again.\n'
"""`FOLLOWS`, then `Usage` once more on line 11, after every section the outline matched."""

EXPECTED_USAGE: Final[ExpectedSection] = ExpectedSection(
    name=SectionName.parse('Usage'), written_at=heading_in(OUT_OF_ORDER, 'Usage')
)
"""The section the outline places where `Options` is written, with its heading in `OUT_OF_ORDER`, on line 7."""

REPEATS_USAGE: Final[LeftOver] = LeftOver(earlier=heading_in(FOLLOWS, 'Usage'))
"""The section left over in `LEFT_OVER`, which repeats the `Usage` written on line 3."""


@pytest.mark.unit
class TestSectionOutOfOrder:
    def test_check_with_a_section_in_place_of_a_later_one_reports_it_at_its_heading(self) -> None:
        #: Given
        subject = FakeDocumentContext(OUT_OF_ORDER, corpus='guide', structure=OUTLINE)

        #: When
        occurrences = SectionOutOfOrder.check(subject)

        #: Then
        assert occurrences == (
            SectionOutOfOrder(
                spec=CORPUS_SPEC, line=LineNumber.from_int(3), section='Options', placement=EXPECTED_USAGE
            ),
        ), 'a section standing where the outline places a later one is one occurrence, at its heading'

    def test_check_with_a_section_left_over_reports_it_with_the_heading_it_repeats(self) -> None:
        #: Given
        subject = FakeDocumentContext(LEFT_OVER, corpus='guide', structure=OUTLINE)

        #: When
        occurrences = SectionOutOfOrder.check(subject)

        #: Then
        assert occurrences == (
            SectionOutOfOrder(spec=CORPUS_SPEC, line=LineNumber.from_int(11), section='Usage', placement=REPEATS_USAGE),
        ), 'a named section left over once the outline is used up is reported at its heading, with the one it repeats'

    def test_check_with_an_absent_section_reports_nothing(self) -> None:
        #: Given
        subject = FakeDocumentContext('# Check\n\n## Options\n\nPass a flag.\n', corpus='guide', structure=OUTLINE)

        #: When
        occurrences = SectionOutOfOrder.check(subject)

        #: Then
        assert occurrences == (), 'a missing section is never a section out of order'

    def test_check_with_an_unlisted_section_reports_nothing(self) -> None:
        #: Given
        subject = FakeDocumentContext(FOLLOWS + '\n## Afterword\n\nThanks.\n', corpus='guide', structure=OUTLINE)

        #: When
        occurrences = SectionOutOfOrder.check(subject)

        #: Then
        assert occurrences == (), 'a section the outline does not name is never a section out of order'

    def test_check_with_no_divergence_reports_nothing(self) -> None:
        #: Given
        subject = FakeDocumentContext(FOLLOWS, corpus='guide', structure=OUTLINE)

        #: When
        occurrences = SectionOutOfOrder.check(subject)

        #: Then
        assert occurrences == (), 'a document that matches its outline has no section out of order'

    def test_check_with_a_section_out_of_order_under_both_specifications_reports_each_in_order(self) -> None:
        #: Given
        # the namespace's outline reverses the corpus's, so it matches `Options` and `Usage`, then finds `Options` again
        reversed_outline = '{"outline": [{"section": "Options"}, {"section": "Usage"}]}'
        subject = FakeDocumentContext(
            OUT_OF_ORDER + '\n## Options\n\nPass another flag.\n',
            corpus='guide',
            structure=OUTLINE,
            namespaces=(namespace_spec('guide', 'cli', reversed_outline),),
        )

        #: When
        occurrences = SectionOutOfOrder.check(subject)

        #: Then
        assert occurrences == (
            SectionOutOfOrder(
                spec=CORPUS_SPEC, line=LineNumber.from_int(3), section='Options', placement=EXPECTED_USAGE
            ),
            SectionOutOfOrder(
                spec=NAMESPACE_SPEC,
                line=LineNumber.from_int(11),
                section='Options',
                placement=LeftOver(earlier=heading_in(OUT_OF_ORDER, 'Options')),
            ),
        ), 'each specification applies on its own, so the document is reported once for each, in order'

    def test_check_with_a_skipped_optional_section_written_late_reports_it_with_nothing_earlier(self) -> None:
        #: Given
        outline = '{"outline": [{"section": "Usage", "optional": true}, {"section": "Options"}]}'
        text = '# Check\n\n## Options\n\nPass a flag.\n\n## Usage\n\nRun it.\n'
        subject = FakeDocumentContext(text, corpus='guide', structure=outline)

        #: When
        occurrences = SectionOutOfOrder.check(subject)

        #: Then
        assert occurrences == (
            SectionOutOfOrder(
                spec=CORPUS_SPEC, line=LineNumber.from_int(7), section='Usage', placement=LeftOver(earlier=None)
            ),
        ), 'an optional section skipped and written after the outline is used up repeats no earlier heading'

    def test_message_with_an_occurrence_names_the_section(self) -> None:
        #: Given
        occurrence = SectionOutOfOrder(
            spec=CORPUS_SPEC, line=LineNumber.from_int(3), section='Options', placement=EXPECTED_USAGE
        )

        #: When
        message = occurrence.message()

        #: Then
        assert message == 'section `Options` is out of order', 'the message names the section written out of order'

    def test_labels_with_a_section_expected_mark_it_and_where_the_expected_one_is_written(self) -> None:
        #: Given
        occurrence = SectionOutOfOrder(
            spec=CORPUS_SPEC, line=LineNumber.from_int(3), section='Options', placement=EXPECTED_USAGE
        )

        #: When
        labels = occurrence.labels()

        #: Then
        assert labels == (
            Label(Here(LineNumber.from_int(3)), 'expected `Usage` here'),
            Label(Here(LineNumber.from_int(7)), '`Usage` is written here'),
        ), 'the labels mark the section, name the one the outline places there, and mark where that one is written'

    def test_labels_with_a_section_repeated_mark_it_and_the_heading_it_repeats(self) -> None:
        #: Given
        occurrence = SectionOutOfOrder(
            spec=CORPUS_SPEC, line=LineNumber.from_int(11), section='Usage', placement=REPEATS_USAGE
        )

        #: When
        labels = occurrence.labels()

        #: Then
        assert labels == (
            Label(Here(LineNumber.from_int(11)), 'left over after every section the outline matched'),
            Label(Here(LineNumber.from_int(3)), 'already written here'),
        ), 'the labels mark the section left over, and the heading of the same text written before it'

    def test_labels_with_a_section_left_over_and_nothing_earlier_mark_it_alone(self) -> None:
        #: Given
        occurrence = SectionOutOfOrder(
            spec=CORPUS_SPEC, line=LineNumber.from_int(7), section='Usage', placement=LeftOver(earlier=None)
        )

        #: When
        labels = occurrence.labels()

        #: Then
        assert labels == (Label(Here(LineNumber.from_int(7)), 'left over after every section the outline matched'),), (
            'a section with no heading of its text before it has nothing to point back at'
        )

    def test_children_with_a_section_expected_point_at_the_specification_and_say_to_move_it(self) -> None:
        #: Given
        occurrence = SectionOutOfOrder(
            spec=CORPUS_SPEC, line=LineNumber.from_int(3), section='Options', placement=EXPECTED_USAGE
        )

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Note('the document structure is set here', at=Elsewhere(CORPUS_SPEC)),
            Help('move `Usage` above `Options`'),
        ), 'a note points at the specification whose outline sets the order, and a help says which section to move'

    def test_children_with_a_section_left_over_point_at_the_specification_alone(self) -> None:
        #: Given
        occurrence = SectionOutOfOrder(
            spec=CORPUS_SPEC, line=LineNumber.from_int(11), section='Usage', placement=REPEATS_USAGE
        )

        #: When
        children = occurrence.children()

        #: Then
        assert children == (Note('the document structure is set here', at=Elsewhere(CORPUS_SPEC)),), (
            'no section is expected there, so there is none to say to move'
        )
