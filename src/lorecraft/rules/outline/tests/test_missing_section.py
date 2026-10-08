"""`OUT006`, `missing-section`, over where a document's sections first stop matching their outlines.

Every case is a document written as text, read through a fake context that parses it and matches it against its
outlines as the real parser and matcher do, under structure specifications decoded from JSON; no document is read from
disk. Where each divergence falls is the matcher's, tested beside it, so a case here only shows which one the rule
reports.
"""

from typing import Final

import pytest

from lorecraft.core.path import RootRelativePath
from lorecraft.project.schemas import DocumentEnd, SectionName
from lorecraft.project.syntax import Heading, LineNumber
from lorecraft.rules.location import Elsewhere, Help, Here, Label, Note
from lorecraft.rules.tests.fake_context import FakeDocumentContext, heading_in, namespace_spec, structure_spec_path

from ..missing_section import MissingSection

CORPUS_SPEC: Final[RootRelativePath] = structure_spec_path('guide')
"""The corpus structure specification."""

NAMESPACE_SPEC: Final[RootRelativePath] = structure_spec_path('guide-cli')
"""A namespace structure specification under the same corpus."""

USAGE: Final[SectionName] = SectionName.parse('Usage')
"""The section the outline requires and the document lacks."""

OUTLINE: Final[str] = '{"outline": [{"section": "Usage"}, {"section": "Options"}]}'
"""An outline requiring `Usage`, then `Options`."""

REVERSED_OUTLINE: Final[str] = '{"outline": [{"section": "Options"}, {"section": "Usage"}]}'
"""An outline requiring `Options`, then `Usage`."""

DESCRIBED_OUTLINE: Final[str] = (
    '{"outline": [{"section": "Usage", "description": "How to invoke the command.", '
    '"examples": ["Run `lorecraft check`.", "Run it with `--strict`."]}, {"section": "Options"}]}'
)
"""`OUTLINE`, whose `Usage` entry states a description and two examples."""

OPTIONS_ONLY: Final[str] = '# Check\n\n## Options\n\nPass a flag.\n'
"""A document of five lines, its one section `Options` on line 3."""

USAGE_ONLY: Final[str] = '# Check\n\n## Usage\n\nRun it.\n'
"""A document of five lines, its one section `Usage` on line 3."""

FOLLOWS: Final[str] = '# Check\n\n## Usage\n\nRun it.\n\n## Options\n\nPass a flag.\n'
"""A document writing `Usage`, then `Options`."""

OUT_OF_ORDER: Final[str] = '# Check\n\n## Options\n\nPass a flag.\n\n## Usage\n\nRun it.\n'
"""A document writing `Options`, then `Usage`."""

BEFORE_OPTIONS: Final[Heading] = heading_in(OPTIONS_ONLY, 'Options')
"""The `Options` section of `OPTIONS_ONLY`, on line 3, before which `Usage` belongs."""

END_AFTER_USAGE: Final[DocumentEnd] = DocumentEnd(
    last_line=LineNumber.from_int(5), after=heading_in(USAGE_ONLY, 'Usage')
)
"""The end of `USAGE_ONLY`, on line 5, after its last section `Usage`."""

END_AFTER_OPTIONS: Final[DocumentEnd] = DocumentEnd(
    last_line=LineNumber.from_int(5), after=heading_in(OPTIONS_ONLY, 'Options')
)
"""The end of `OPTIONS_ONLY`, on line 5, after its last section `Options`."""


@pytest.mark.unit
class TestMissingSection:
    def test_check_with_a_section_absent_before_another_reports_it_at_that_section(self) -> None:
        #: Given
        subject = FakeDocumentContext(OPTIONS_ONLY, corpus='guide', structure=DESCRIBED_OUTLINE)

        #: When
        occurrences = MissingSection.check(subject)

        #: Then
        assert occurrences == (
            MissingSection(
                spec=CORPUS_SPEC,
                line=LineNumber.from_int(3),
                section=USAGE,
                before=BEFORE_OPTIONS,
                description='How to invoke the command.',
                example='Run `lorecraft check`.',
            ),
        ), 'a section absent before another is one occurrence, at that section, with the entry and its first example'

    def test_check_with_a_section_absent_at_the_end_reports_it_at_the_last_line(self) -> None:
        #: Given
        subject = FakeDocumentContext(USAGE_ONLY, corpus='guide', structure=OUTLINE)

        #: When
        occurrences = MissingSection.check(subject)

        #: Then
        assert occurrences == (
            MissingSection(
                spec=CORPUS_SPEC,
                line=LineNumber.from_int(5),
                section=SectionName.parse('Options'),
                before=END_AFTER_USAGE,
                description=None,
                example=None,
            ),
        ), "a section expected at the end of the document is reported at the document's last line"

    def test_check_with_a_misplaced_section_reports_nothing(self) -> None:
        #: Given
        subject = FakeDocumentContext(OUT_OF_ORDER, corpus='guide', structure=OUTLINE)

        #: When
        occurrences = MissingSection.check(subject)

        #: Then
        assert occurrences == (), 'a section out of order is never a missing section'

    def test_check_with_an_unlisted_section_reports_nothing(self) -> None:
        #: Given
        subject = FakeDocumentContext(FOLLOWS + '\n## Afterword\n\nThanks.\n', corpus='guide', structure=OUTLINE)

        #: When
        occurrences = MissingSection.check(subject)

        #: Then
        assert occurrences == (), 'an unexpected section is never a missing section'

    def test_check_with_no_divergence_reports_nothing(self) -> None:
        #: Given
        subject = FakeDocumentContext(FOLLOWS, corpus='guide', structure=OUTLINE)

        #: When
        occurrences = MissingSection.check(subject)

        #: Then
        assert occurrences == (), 'a document that matches its outline lacks no section'

    def test_check_with_a_section_absent_under_both_specifications_reports_each_in_order(self) -> None:
        #: Given
        subject = FakeDocumentContext(
            OPTIONS_ONLY,
            corpus='guide',
            structure=OUTLINE,
            namespaces=(namespace_spec('guide', 'cli', REVERSED_OUTLINE),),
        )

        #: When
        occurrences = MissingSection.check(subject)

        #: Then
        assert occurrences == (
            MissingSection(
                spec=CORPUS_SPEC,
                line=LineNumber.from_int(3),
                section=USAGE,
                before=BEFORE_OPTIONS,
                description=None,
                example=None,
            ),
            MissingSection(
                spec=NAMESPACE_SPEC,
                line=LineNumber.from_int(5),
                section=USAGE,
                before=END_AFTER_OPTIONS,
                description=None,
                example=None,
            ),
        ), 'each specification applies on its own, so the document is reported once for each, in order'

    def test_message_with_an_occurrence_names_the_missing_section(self) -> None:
        #: Given
        occurrence = MissingSection(
            spec=CORPUS_SPEC,
            line=LineNumber.from_int(3),
            section=USAGE,
            before=BEFORE_OPTIONS,
            description=None,
            example=None,
        )

        #: When
        message = occurrence.message()

        #: Then
        assert message == 'missing required section `Usage`', 'the message names the section the document lacks'

    def test_labels_with_a_section_after_mark_that_section(self) -> None:
        #: Given
        occurrence = MissingSection(
            spec=CORPUS_SPEC,
            line=LineNumber.from_int(3),
            section=USAGE,
            before=BEFORE_OPTIONS,
            description=None,
            example=None,
        )

        #: When
        labels = occurrence.labels()

        #: Then
        assert labels == (Label(Here(LineNumber.from_int(3)), 'expected `Usage` before `Options`'),), (
            'the label marks the section the missing one should come before, and names it'
        )

    def test_labels_at_the_end_of_the_document_mark_its_last_line_and_its_last_section(self) -> None:
        #: Given
        occurrence = MissingSection(
            spec=CORPUS_SPEC,
            line=LineNumber.from_int(5),
            section=SectionName.parse('Options'),
            before=END_AFTER_USAGE,
            description=None,
            example=None,
        )

        #: When
        labels = occurrence.labels()

        #: Then
        assert labels == (
            Label(Here(LineNumber.from_int(5)), 'expected `Options` before the end of the document'),
            Label(Here(LineNumber.from_int(3)), 'expected `Options` after `Usage`'),
        ), 'the labels mark the last line, where the section would end, and the last section it follows'

    def test_labels_at_the_end_of_a_document_without_a_section_mark_its_last_line_alone(self) -> None:
        #: Given
        occurrence = MissingSection(
            spec=CORPUS_SPEC,
            line=LineNumber.from_int(1),
            section=USAGE,
            before=DocumentEnd(last_line=LineNumber.from_int(1), after=None),
            description=None,
            example=None,
        )

        #: When
        labels = occurrence.labels()

        #: Then
        assert labels == (Label(Here(LineNumber.from_int(1)), 'expected `Usage` before the end of the document'),), (
            'a document with no section has none to follow, so only its last line is marked'
        )

    def test_labels_at_the_end_of_a_document_ending_on_its_last_heading_mark_it_once(self) -> None:
        #: Given
        document = '# Check\n\n## Usage'
        occurrence = MissingSection(
            spec=CORPUS_SPEC,
            line=LineNumber.from_int(3),
            section=SectionName.parse('Options'),
            before=DocumentEnd(last_line=LineNumber.from_int(3), after=heading_in(document, 'Usage')),
            description=None,
            example=None,
        )

        #: When
        labels = occurrence.labels()

        #: Then
        assert labels == (Label(Here(LineNumber.from_int(3)), 'expected `Options` after `Usage`'),), (
            'when the last heading is the last line, one label says where the section follows'
        )

    def test_children_with_a_description_and_an_example_give_both_after_the_specification_note(self) -> None:
        #: Given
        occurrence = MissingSection(
            spec=CORPUS_SPEC,
            line=LineNumber.from_int(3),
            section=USAGE,
            before=BEFORE_OPTIONS,
            description='How to invoke the command.',
            example='Run `lorecraft check`.',
        )

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Note('the document structure is set here', at=Elsewhere(CORPUS_SPEC)),
            Help('How to invoke the command.'),
            Note('for example:\n## Usage\n\nRun `lorecraft check`.'),
        ), 'a note points at the specification, help gives the description, and a note the example under its heading'

    def test_children_with_only_a_description_give_it_as_help_alone(self) -> None:
        #: Given
        occurrence = MissingSection(
            spec=CORPUS_SPEC,
            line=LineNumber.from_int(3),
            section=USAGE,
            before=BEFORE_OPTIONS,
            description='How to invoke the command.',
            example=None,
        )

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Note('the document structure is set here', at=Elsewhere(CORPUS_SPEC)),
            Help('How to invoke the command.'),
        ), 'an entry stating no example adds no example note'

    def test_children_with_only_an_example_give_it_as_a_note_alone(self) -> None:
        #: Given
        occurrence = MissingSection(
            spec=CORPUS_SPEC,
            line=LineNumber.from_int(3),
            section=USAGE,
            before=BEFORE_OPTIONS,
            description=None,
            example='Run `lorecraft check`.',
        )

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Note('the document structure is set here', at=Elsewhere(CORPUS_SPEC)),
            Note('for example:\n## Usage\n\nRun `lorecraft check`.'),
        ), 'an entry stating no description adds no help'

    def test_children_without_a_description_or_an_example_point_at_the_specification_alone(self) -> None:
        #: Given
        occurrence = MissingSection(
            spec=CORPUS_SPEC,
            line=LineNumber.from_int(3),
            section=USAGE,
            before=BEFORE_OPTIONS,
            description=None,
            example=None,
        )

        #: When
        children = occurrence.children()

        #: Then
        assert children == (Note('the document structure is set here', at=Elsewhere(CORPUS_SPEC)),), (
            'an entry stating no description and no example adds nothing to the specification note'
        )
