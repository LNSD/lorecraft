"""`OUT008`, `unexpected-section`, over where a document's sections first stop matching their outlines.

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

from ..unexpected_section import UnexpectedSection

CORPUS_SPEC: Final[RootRelativePath] = structure_spec_path('guide')
"""The corpus structure specification."""

NAMESPACE_SPEC: Final[RootRelativePath] = structure_spec_path('guide-cli')
"""A namespace structure specification under the same corpus."""

OPTIONS: Final[SectionName] = SectionName.parse('Options')
"""The section the outline places where `Tips` is written, which the document writes further down."""

OUTLINE: Final[str] = '{"outline": [{"section": "Usage"}, {"section": "Options"}]}'
"""An outline requiring `Usage`, then `Options`."""

FOLLOWS: Final[str] = '# Check\n\n## Usage\n\nRun it.\n\n## Options\n\nPass a flag.\n'
"""A document writing `Usage`, then `Options`."""

TIPS_BETWEEN: Final[str] = '# Check\n\n## Usage\n\nRun it.\n\n## Tips\n\nA tip.\n\n## Options\n\nPass a flag.\n'
"""A document writing `Usage`, then `Tips` on line 7, which no outline here names, then `Options`."""

AFTERWORD: Final[str] = FOLLOWS + '\n## Afterword\n\nThanks.\n'
"""`FOLLOWS`, then `Afterword` on line 11, which no outline here names."""


@pytest.mark.unit
class TestUnexpectedSection:
    def test_check_with_an_unlisted_section_in_place_of_a_later_one_reports_it_at_its_heading(self) -> None:
        #: Given
        subject = FakeDocumentContext(TIPS_BETWEEN, corpus='guide', structure=OUTLINE)

        #: When
        occurrences = UnexpectedSection.check(subject)

        #: Then
        assert occurrences == (
            UnexpectedSection(spec=CORPUS_SPEC, line=LineNumber.from_int(7), section='Tips', expected=OPTIONS),
        ), 'a section the outline does not name, where it places a later one, is one occurrence, at its heading'

    def test_check_with_an_unlisted_section_after_the_outline_reports_it_with_nothing_expected(self) -> None:
        #: Given
        subject = FakeDocumentContext(AFTERWORD, corpus='guide', structure=OUTLINE)

        #: When
        occurrences = UnexpectedSection.check(subject)

        #: Then
        assert occurrences == (
            UnexpectedSection(spec=CORPUS_SPEC, line=LineNumber.from_int(11), section='Afterword', expected=None),
        ), 'a section the outline does not name, after its end, is reported at its heading, with none expected'

    def test_check_with_an_absent_section_reports_nothing(self) -> None:
        #: Given
        subject = FakeDocumentContext('# Check\n\n## Usage\n\nRun it.\n', corpus='guide', structure=OUTLINE)

        #: When
        occurrences = UnexpectedSection.check(subject)

        #: Then
        assert occurrences == (), 'a missing section is never an unexpected section'

    def test_check_with_a_misplaced_section_reports_nothing(self) -> None:
        #: Given
        out_of_order = '# Check\n\n## Options\n\nPass a flag.\n\n## Usage\n\nRun it.\n'
        subject = FakeDocumentContext(out_of_order, corpus='guide', structure=OUTLINE)

        #: When
        occurrences = UnexpectedSection.check(subject)

        #: Then
        assert occurrences == (), 'a section the outline names, out of its place, is never an unexpected section'

    def test_check_with_no_divergence_reports_nothing(self) -> None:
        #: Given
        subject = FakeDocumentContext(FOLLOWS, corpus='guide', structure=OUTLINE)

        #: When
        occurrences = UnexpectedSection.check(subject)

        #: Then
        assert occurrences == (), 'a document that matches its outline has no unexpected section'

    def test_check_with_an_unexpected_section_under_both_specifications_reports_each_in_order(self) -> None:
        #: Given
        # the namespace's outline lets any section stand between `Usage` and `Options`, so `Tips` is allowed there
        any_between = '{"outline": [{"section": "Usage"}, {"any": true}, {"section": "Options"}]}'
        subject = FakeDocumentContext(
            TIPS_BETWEEN + '\n## Afterword\n\nThanks.\n',
            corpus='guide',
            structure=OUTLINE,
            namespaces=(namespace_spec('guide', 'cli', any_between),),
        )

        #: When
        occurrences = UnexpectedSection.check(subject)

        #: Then
        assert occurrences == (
            UnexpectedSection(spec=CORPUS_SPEC, line=LineNumber.from_int(7), section='Tips', expected=OPTIONS),
            UnexpectedSection(spec=NAMESPACE_SPEC, line=LineNumber.from_int(15), section='Afterword', expected=None),
        ), 'each specification applies on its own, so the document is reported once for each, in order'

    def test_message_with_an_occurrence_names_the_section(self) -> None:
        #: Given
        occurrence = UnexpectedSection(spec=CORPUS_SPEC, line=LineNumber.from_int(7), section='Tips', expected=OPTIONS)

        #: When
        message = occurrence.message()

        #: Then
        assert message == 'unexpected section `Tips`', 'the message names the section the outline does not name'

    def test_labels_with_a_section_expected_name_it(self) -> None:
        #: Given
        occurrence = UnexpectedSection(spec=CORPUS_SPEC, line=LineNumber.from_int(7), section='Tips', expected=OPTIONS)

        #: When
        labels = occurrence.labels()

        #: Then
        assert labels == (Label(Here(LineNumber.from_int(7)), 'expected `Options` here'),), (
            'the label marks the section, and names the one the outline places there instead'
        )

    def test_labels_with_no_section_expected_say_the_outline_ends_before_it(self) -> None:
        #: Given
        occurrence = UnexpectedSection(
            spec=CORPUS_SPEC, line=LineNumber.from_int(11), section='Afterword', expected=None
        )

        #: When
        labels = occurrence.labels()

        #: Then
        assert labels == (Label(Here(LineNumber.from_int(11)), 'the outline ends before it'),), (
            'the label marks the section, and says the outline ends before it'
        )

    def test_children_with_an_occurrence_point_at_the_specification(self) -> None:
        #: Given
        occurrence = UnexpectedSection(spec=CORPUS_SPEC, line=LineNumber.from_int(7), section='Tips', expected=OPTIONS)

        #: When
        children = occurrence.children()

        #: Then
        assert children == (Note('the document structure is set here', at=Elsewhere(CORPUS_SPEC)),), (
            'a note points at the specification whose outline does not allow the section'
        )
