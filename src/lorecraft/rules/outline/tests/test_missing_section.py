"""`OUT006`, `missing-section`, over where a document's sections first stop matching their outlines.

The rule is pure, so every case here is the divergence each outline found, written as literals; no document is
read and no outline is matched.
"""

from typing import Final

import pytest

from lorecraft.core.path import RootRelativePath
from lorecraft.project.schemas import (
    AbsentSection,
    DocumentEnd,
    MisplacedSection,
    OutlineDivergenceSpec,
    SectionName,
    UnlistedSection,
)
from lorecraft.project.syntax import Heading, LineNumber
from lorecraft.rules.inputs import OutlineDivergenceInput
from lorecraft.rules.location import Elsewhere, Help, Here, Label, Note

from ..missing_section import MissingSection

CORPUS_SPEC: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/guide.structure.json')
"""A corpus structure specification."""

NAMESPACE_SPEC: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/guide-cli.structure.json')
"""A namespace structure specification under the same corpus."""

USAGE: Final[SectionName] = SectionName.parse('Usage')
"""The section the outline requires and the document lacks."""

OPTIONS: Final[Heading] = Heading(level=2, text='Options', line=LineNumber.from_int(3), empty=False, words=4)
"""An H2 section on line 3, written where `Usage` was expected."""

DOCUMENT_END: Final[DocumentEnd] = DocumentEnd(last_line=LineNumber.from_int(9))
"""The end of a nine-line document."""


def _absent(before: Heading | DocumentEnd, description: str | None, example: str | None) -> AbsentSection:
    """`Usage`, absent from the document, expected before `before`.

    Args:
        before: The section it should come before, or the end of the document.
        description: What the outline entry says the section holds, or `None`.
        example: The outline entry's first example, or `None`.
    """
    return AbsentSection(name=USAGE, description=description, example=example, before=before)


@pytest.mark.unit
class TestMissingSection:
    def test_check_with_a_section_absent_before_another_reports_it_at_that_section(self) -> None:
        #: Given
        absent = _absent(OPTIONS, 'How to invoke the command.', 'Run `lorecraft check`.')
        subject = OutlineDivergenceInput(specs=(OutlineDivergenceSpec(spec=CORPUS_SPEC, divergence=absent),))

        #: When
        occurrences = MissingSection.check(subject)

        #: Then
        assert occurrences == (
            MissingSection(
                spec=CORPUS_SPEC,
                line=OPTIONS.line,
                section=USAGE,
                before=OPTIONS.text,
                description='How to invoke the command.',
                example='Run `lorecraft check`.',
            ),
        ), 'a section absent before another is one occurrence, at that section, with what the entry states'

    def test_check_with_a_section_absent_at_the_end_reports_it_at_the_last_line(self) -> None:
        #: Given
        subject = OutlineDivergenceInput(
            specs=(OutlineDivergenceSpec(spec=CORPUS_SPEC, divergence=_absent(DOCUMENT_END, None, None)),)
        )

        #: When
        occurrences = MissingSection.check(subject)

        #: Then
        assert occurrences == (
            MissingSection(
                spec=CORPUS_SPEC,
                line=LineNumber.from_int(9),
                section=USAGE,
                before=None,
                description=None,
                example=None,
            ),
        ), "a section expected at the end of the document is reported at the document's last line"

    def test_check_with_a_misplaced_section_reports_nothing(self) -> None:
        #: Given
        misplaced = MisplacedSection(section=OPTIONS, expected=USAGE)
        subject = OutlineDivergenceInput(specs=(OutlineDivergenceSpec(spec=CORPUS_SPEC, divergence=misplaced),))

        #: When
        occurrences = MissingSection.check(subject)

        #: Then
        assert occurrences == (), 'a section out of order is never a missing section'

    def test_check_with_an_unlisted_section_reports_nothing(self) -> None:
        #: Given
        unlisted = UnlistedSection(section=OPTIONS, expected=None)
        subject = OutlineDivergenceInput(specs=(OutlineDivergenceSpec(spec=CORPUS_SPEC, divergence=unlisted),))

        #: When
        occurrences = MissingSection.check(subject)

        #: Then
        assert occurrences == (), 'an unexpected section is never a missing section'

    def test_check_with_no_divergence_reports_nothing(self) -> None:
        #: Given
        subject = OutlineDivergenceInput(specs=(OutlineDivergenceSpec(spec=CORPUS_SPEC, divergence=None),))

        #: When
        occurrences = MissingSection.check(subject)

        #: Then
        assert occurrences == (), 'a document that matches its outline lacks no section'

    def test_check_with_a_section_absent_under_both_specifications_reports_each_in_order(self) -> None:
        #: Given
        subject = OutlineDivergenceInput(
            specs=(
                OutlineDivergenceSpec(spec=CORPUS_SPEC, divergence=_absent(OPTIONS, None, None)),
                OutlineDivergenceSpec(spec=NAMESPACE_SPEC, divergence=_absent(DOCUMENT_END, None, None)),
            )
        )

        #: When
        occurrences = MissingSection.check(subject)

        #: Then
        assert occurrences == (
            MissingSection(
                spec=CORPUS_SPEC, line=OPTIONS.line, section=USAGE, before=OPTIONS.text, description=None, example=None
            ),
            MissingSection(
                spec=NAMESPACE_SPEC,
                line=LineNumber.from_int(9),
                section=USAGE,
                before=None,
                description=None,
                example=None,
            ),
        ), 'each specification applies on its own, so the document is reported once for each, in order'

    def test_message_with_an_occurrence_names_the_missing_section(self) -> None:
        #: Given
        occurrence = MissingSection(
            spec=CORPUS_SPEC, line=OPTIONS.line, section=USAGE, before=OPTIONS.text, description=None, example=None
        )

        #: When
        message = occurrence.message()

        #: Then
        assert message == 'missing required section `Usage`', 'the message names the section the document lacks'

    def test_labels_with_a_section_after_mark_that_section(self) -> None:
        #: Given
        occurrence = MissingSection(
            spec=CORPUS_SPEC, line=OPTIONS.line, section=USAGE, before=OPTIONS.text, description=None, example=None
        )

        #: When
        labels = occurrence.labels()

        #: Then
        assert labels == (Label(Here(LineNumber.from_int(3)), 'expected `Usage` before `Options`'),), (
            'the label marks the section the missing one should come before, and names it'
        )

    def test_labels_at_the_end_of_the_document_mark_its_last_line(self) -> None:
        #: Given
        occurrence = MissingSection(
            spec=CORPUS_SPEC, line=LineNumber.from_int(9), section=USAGE, before=None, description=None, example=None
        )

        #: When
        labels = occurrence.labels()

        #: Then
        assert labels == (Label(Here(LineNumber.from_int(9)), 'expected `Usage` before the end of the document'),), (
            'the label marks the last line of the document, which the missing section should end'
        )

    def test_children_with_a_description_and_an_example_give_both_after_the_specification_note(self) -> None:
        #: Given
        occurrence = MissingSection(
            spec=CORPUS_SPEC,
            line=OPTIONS.line,
            section=USAGE,
            before=OPTIONS.text,
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

    def test_children_without_a_description_or_an_example_point_at_the_specification_alone(self) -> None:
        #: Given
        occurrence = MissingSection(
            spec=CORPUS_SPEC, line=OPTIONS.line, section=USAGE, before=OPTIONS.text, description=None, example=None
        )

        #: When
        children = occurrence.children()

        #: Then
        assert children == (Note('the document structure is set here', at=Elsewhere(CORPUS_SPEC)),), (
            'an entry stating no description and no example adds nothing to the specification note'
        )
