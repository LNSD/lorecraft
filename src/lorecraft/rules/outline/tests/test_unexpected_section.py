"""`OUT008`, `unexpected-section`, over where a document's sections first stop matching their outlines.

The rule is pure, so every case here is the divergence each outline found, written as literals; no document is
read and no outline is matched.
"""

from typing import Final

import pytest

from lorecraft.core.path import RootRelativePath
from lorecraft.project.schemas import (
    AbsentSection,
    MisplacedSection,
    OutlineDivergenceSpec,
    SectionName,
    UnlistedSection,
)
from lorecraft.project.syntax import Heading, LineNumber
from lorecraft.rules.inputs import OutlineDivergenceInput
from lorecraft.rules.location import Elsewhere, Here, Label, Note

from ..unexpected_section import UnexpectedSection

CORPUS_SPEC: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/guide.structure.json')
"""A corpus structure specification."""

NAMESPACE_SPEC: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/guide-cli.structure.json')
"""A namespace structure specification under the same corpus."""

OPTIONS: Final[SectionName] = SectionName.parse('Options')
"""The section the outline places where `Tips` is written, which the document writes further down."""

TIPS: Final[Heading] = Heading(level=2, text='Tips', line=LineNumber.from_int(7), empty=False, words=5)
"""An H2 section on line 7, which the outline does not name, written where `Options` was expected."""

AFTERWORD: Final[Heading] = Heading(level=2, text='Afterword', line=LineNumber.from_int(15), empty=False, words=3)
"""An H2 section on line 15, which the outline does not name, after the outline's end."""


@pytest.mark.unit
class TestUnexpectedSection:
    def test_check_with_an_unlisted_section_in_place_of_a_later_one_reports_it_at_its_heading(self) -> None:
        #: Given
        unlisted = UnlistedSection(section=TIPS, expected=OPTIONS)
        subject = OutlineDivergenceInput(specs=(OutlineDivergenceSpec(spec=CORPUS_SPEC, divergence=unlisted),))

        #: When
        occurrences = UnexpectedSection.check(subject)

        #: Then
        assert occurrences == (
            UnexpectedSection(spec=CORPUS_SPEC, line=TIPS.line, section=TIPS.text, expected=OPTIONS),
        ), 'a section the outline does not name, where it places a later one, is one occurrence, at its heading'

    def test_check_with_an_unlisted_section_after_the_outline_reports_it_with_nothing_expected(self) -> None:
        #: Given
        unlisted = UnlistedSection(section=AFTERWORD, expected=None)
        subject = OutlineDivergenceInput(specs=(OutlineDivergenceSpec(spec=CORPUS_SPEC, divergence=unlisted),))

        #: When
        occurrences = UnexpectedSection.check(subject)

        #: Then
        assert occurrences == (
            UnexpectedSection(spec=CORPUS_SPEC, line=AFTERWORD.line, section=AFTERWORD.text, expected=None),
        ), 'a section the outline does not name, after its end, is reported at its heading, with none expected'

    def test_check_with_an_absent_section_reports_nothing(self) -> None:
        #: Given
        absent = AbsentSection(name=OPTIONS, description=None, example=None, before=TIPS)
        subject = OutlineDivergenceInput(specs=(OutlineDivergenceSpec(spec=CORPUS_SPEC, divergence=absent),))

        #: When
        occurrences = UnexpectedSection.check(subject)

        #: Then
        assert occurrences == (), 'a missing section is never an unexpected section'

    def test_check_with_a_misplaced_section_reports_nothing(self) -> None:
        #: Given
        misplaced = MisplacedSection(section=TIPS, expected=OPTIONS)
        subject = OutlineDivergenceInput(specs=(OutlineDivergenceSpec(spec=CORPUS_SPEC, divergence=misplaced),))

        #: When
        occurrences = UnexpectedSection.check(subject)

        #: Then
        assert occurrences == (), 'a section the outline names, out of its place, is never an unexpected section'

    def test_check_with_no_divergence_reports_nothing(self) -> None:
        #: Given
        subject = OutlineDivergenceInput(specs=(OutlineDivergenceSpec(spec=CORPUS_SPEC, divergence=None),))

        #: When
        occurrences = UnexpectedSection.check(subject)

        #: Then
        assert occurrences == (), 'a document that matches its outline has no unexpected section'

    def test_check_with_an_unexpected_section_under_both_specifications_reports_each_in_order(self) -> None:
        #: Given
        subject = OutlineDivergenceInput(
            specs=(
                OutlineDivergenceSpec(spec=CORPUS_SPEC, divergence=UnlistedSection(section=TIPS, expected=OPTIONS)),
                OutlineDivergenceSpec(
                    spec=NAMESPACE_SPEC, divergence=UnlistedSection(section=AFTERWORD, expected=None)
                ),
            )
        )

        #: When
        occurrences = UnexpectedSection.check(subject)

        #: Then
        assert occurrences == (
            UnexpectedSection(spec=CORPUS_SPEC, line=TIPS.line, section=TIPS.text, expected=OPTIONS),
            UnexpectedSection(spec=NAMESPACE_SPEC, line=AFTERWORD.line, section=AFTERWORD.text, expected=None),
        ), 'each specification applies on its own, so the document is reported once for each, in order'

    def test_message_with_an_occurrence_names_the_section(self) -> None:
        #: Given
        occurrence = UnexpectedSection(spec=CORPUS_SPEC, line=TIPS.line, section=TIPS.text, expected=OPTIONS)

        #: When
        message = occurrence.message()

        #: Then
        assert message == 'unexpected section `Tips`', 'the message names the section the outline does not name'

    def test_labels_with_a_section_expected_name_it(self) -> None:
        #: Given
        occurrence = UnexpectedSection(spec=CORPUS_SPEC, line=TIPS.line, section=TIPS.text, expected=OPTIONS)

        #: When
        labels = occurrence.labels()

        #: Then
        assert labels == (Label(Here(LineNumber.from_int(7)), 'expected `Options` here'),), (
            'the label marks the section, and names the one the outline places there instead'
        )

    def test_labels_with_no_section_expected_say_the_outline_ends_before_it(self) -> None:
        #: Given
        occurrence = UnexpectedSection(spec=CORPUS_SPEC, line=AFTERWORD.line, section=AFTERWORD.text, expected=None)

        #: When
        labels = occurrence.labels()

        #: Then
        assert labels == (Label(Here(LineNumber.from_int(15)), 'the outline ends before it'),), (
            'the label marks the section, and says the outline ends before it'
        )

    def test_children_with_an_occurrence_point_at_the_specification(self) -> None:
        #: Given
        occurrence = UnexpectedSection(spec=CORPUS_SPEC, line=TIPS.line, section=TIPS.text, expected=OPTIONS)

        #: When
        children = occurrence.children()

        #: Then
        assert children == (Note('the document structure is set here', at=Elsewhere(CORPUS_SPEC)),), (
            'a note points at the specification whose outline does not allow the section'
        )
