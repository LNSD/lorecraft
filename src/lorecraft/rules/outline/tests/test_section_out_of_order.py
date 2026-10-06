"""`OUT007`, `section-out-of-order`, over where a document's sections first stop matching their outlines.

Every case is a document written as text, read through a fake context that parses it and matches it against its
outlines as the real parser and matcher do, under structure specifications decoded from JSON; no document is read from
disk. Where each divergence falls is the matcher's, tested beside it, so a case here only shows which one the rule
reports.
"""

from typing import Final

import pytest

from lorecraft.core.path import RootRelativePath
from lorecraft.project.schemas import SectionName
from lorecraft.project.syntax import LineNumber
from lorecraft.rules.location import Elsewhere, Here, Label, Note
from lorecraft.rules.tests.fake_context import FakeDocumentContext, namespace_spec, structure_spec_path

from ..section_out_of_order import SectionOutOfOrder

CORPUS_SPEC: Final[RootRelativePath] = structure_spec_path('guide')
"""The corpus structure specification."""

NAMESPACE_SPEC: Final[RootRelativePath] = structure_spec_path('guide-cli')
"""A namespace structure specification under the same corpus."""

USAGE: Final[SectionName] = SectionName.parse('Usage')
"""The section the outline places where `Options` is written, which the document writes further down."""

OUTLINE: Final[str] = '{"outline": [{"section": "Usage"}, {"section": "Options"}]}'
"""An outline requiring `Usage`, then `Options`."""

FOLLOWS: Final[str] = '# Check\n\n## Usage\n\nRun it.\n\n## Options\n\nPass a flag.\n'
"""A document writing `Usage`, then `Options`."""

OUT_OF_ORDER: Final[str] = '# Check\n\n## Options\n\nPass a flag.\n\n## Usage\n\nRun it.\n'
"""A document writing `Options` on line 3, then `Usage`."""

LEFT_OVER: Final[str] = FOLLOWS + '\n## Usage\n\nRun it again.\n'
"""`FOLLOWS`, then `Usage` once more on line 11, after every section the outline matched."""


@pytest.mark.unit
class TestSectionOutOfOrder:
    def test_check_with_a_section_in_place_of_a_later_one_reports_it_at_its_heading(self) -> None:
        #: Given
        subject = FakeDocumentContext(OUT_OF_ORDER, corpus='guide', structure=OUTLINE)

        #: When
        occurrences = SectionOutOfOrder.check(subject)

        #: Then
        assert occurrences == (
            SectionOutOfOrder(spec=CORPUS_SPEC, line=LineNumber.from_int(3), section='Options', expected=USAGE),
        ), 'a section standing where the outline places a later one is one occurrence, at its heading'

    def test_check_with_a_section_left_over_reports_it_with_nothing_expected(self) -> None:
        #: Given
        subject = FakeDocumentContext(LEFT_OVER, corpus='guide', structure=OUTLINE)

        #: When
        occurrences = SectionOutOfOrder.check(subject)

        #: Then
        assert occurrences == (
            SectionOutOfOrder(spec=CORPUS_SPEC, line=LineNumber.from_int(11), section='Usage', expected=None),
        ), 'a named section left over once the outline is used up is reported at its heading, with none expected'

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
            SectionOutOfOrder(spec=CORPUS_SPEC, line=LineNumber.from_int(3), section='Options', expected=USAGE),
            SectionOutOfOrder(spec=NAMESPACE_SPEC, line=LineNumber.from_int(11), section='Options', expected=None),
        ), 'each specification applies on its own, so the document is reported once for each, in order'

    def test_message_with_an_occurrence_names_the_section(self) -> None:
        #: Given
        occurrence = SectionOutOfOrder(spec=CORPUS_SPEC, line=LineNumber.from_int(3), section='Options', expected=USAGE)

        #: When
        message = occurrence.message()

        #: Then
        assert message == 'section `Options` is out of order', 'the message names the section written out of order'

    def test_labels_with_a_section_expected_name_it(self) -> None:
        #: Given
        occurrence = SectionOutOfOrder(spec=CORPUS_SPEC, line=LineNumber.from_int(3), section='Options', expected=USAGE)

        #: When
        labels = occurrence.labels()

        #: Then
        assert labels == (Label(Here(LineNumber.from_int(3)), 'expected `Usage` here'),), (
            'the label marks the section, and names the one the outline places there instead'
        )

    def test_labels_with_no_section_expected_say_it_is_left_over(self) -> None:
        #: Given
        occurrence = SectionOutOfOrder(spec=CORPUS_SPEC, line=LineNumber.from_int(11), section='Usage', expected=None)

        #: When
        labels = occurrence.labels()

        #: Then
        assert labels == (Label(Here(LineNumber.from_int(11)), 'left over after every section the outline matched'),), (
            'the label marks the section, and says it comes after every section the outline matched'
        )

    def test_children_with_an_occurrence_point_at_the_specification(self) -> None:
        #: Given
        occurrence = SectionOutOfOrder(spec=CORPUS_SPEC, line=LineNumber.from_int(3), section='Options', expected=USAGE)

        #: When
        children = occurrence.children()

        #: Then
        assert children == (Note('the document structure is set here', at=Elsewhere(CORPUS_SPEC)),), (
            'a note points at the specification whose outline sets the order'
        )
