"""`LEN003`, `too-many-words`, over the word caps of a document's sections.

The rule is pure, so every case here is a document's headings and the caps each specification resolved for its
sections, written as literals; no document is read.
"""

from typing import Final

import pytest

from lorecraft.core.num import NonZeroUnsignedInt
from lorecraft.core.path import RootRelativePath
from lorecraft.project.syntax import Heading, LineNumber
from lorecraft.rules.inputs import HeadingsInput, HeadingsSpec, SectionCap
from lorecraft.rules.location import Elsewhere, Note

from ..too_many_words import TooManyWords

CORPUS_SPEC: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/guide.structure.json')
"""A corpus structure specification."""

NAMESPACE_SPEC: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/guide-cli.structure.json')
"""A namespace structure specification under the same corpus, which sets caps of its own."""

TITLE: Final[Heading] = Heading(level=1, text='Setup', line=LineNumber.from_int(1), empty=False, words=0)
"""An H1 title on line 1, holding the sections below it."""

RUN: Final[Heading] = Heading(level=2, text='Run', line=LineNumber.from_int(3), empty=False, words=6)
"""An H2 section on line 3, of six prose words."""

CONFIGURATION: Final[Heading] = Heading(
    level=2, text='Configuration', line=LineNumber.from_int(7), empty=False, words=12
)
"""An H2 section on line 7, of twelve prose words."""


def _spec(spec: RootRelativePath, *, section_caps: tuple[SectionCap, ...]) -> HeadingsSpec:
    """What a specification states over the headings: its sections' word caps, alone.

    Args:
        spec: The structure specification file.
        section_caps: The cap that applies to each capped section, in document order.
    """
    return HeadingsSpec(
        spec=spec,
        title_cap=None,
        title_char_cap=None,
        title_mismatch=None,
        forbid_empty_sections=False,
        forbidden=(),
        section_caps=section_caps,
    )


def _cap(section: Heading, words: int) -> SectionCap:
    """The cap of `words` prose words on `section`.

    Args:
        section: The H2 heading the cap applies to.
        words: The most prose words the section may hold.
    """
    return SectionCap(section=section, words=NonZeroUnsignedInt(words))


@pytest.mark.unit
class TestTooManyWords:
    def test_check_with_a_section_over_its_cap_reports_it_at_its_heading(self) -> None:
        #: Given
        subject = HeadingsInput(
            headings=(TITLE, RUN, CONFIGURATION),
            corpus=_spec(CORPUS_SPEC, section_caps=(_cap(CONFIGURATION, 10),)),
            namespaces=(),
        )

        #: When
        occurrences = TooManyWords.check(subject)

        #: Then
        assert occurrences == (TooManyWords(spec=CORPUS_SPEC, line=LineNumber.from_int(7), word_count=12, cap=10),), (
            'a section over its cap is one occurrence, at its heading, naming the specification that sets the cap'
        )

    def test_check_with_a_section_at_its_cap_reports_nothing(self) -> None:
        #: Given
        subject = HeadingsInput(
            headings=(TITLE, RUN, CONFIGURATION),
            corpus=_spec(CORPUS_SPEC, section_caps=(_cap(CONFIGURATION, 12),)),
            namespaces=(),
        )

        #: When
        occurrences = TooManyWords.check(subject)

        #: Then
        assert occurrences == (), 'the cap is the most words allowed, so a section at its cap fits it'

    def test_check_with_no_section_capped_reports_nothing(self) -> None:
        #: Given
        subject = HeadingsInput(
            headings=(TITLE, RUN, CONFIGURATION), corpus=_spec(CORPUS_SPEC, section_caps=()), namespaces=()
        )

        #: When
        occurrences = TooManyWords.check(subject)

        #: Then
        assert occurrences == (), 'a section no cap applies to may hold any number of words'

    def test_check_with_two_sections_over_their_caps_reports_each_in_document_order(self) -> None:
        #: Given
        section_caps = (_cap(RUN, 5), _cap(CONFIGURATION, 10))
        subject = HeadingsInput(
            headings=(TITLE, RUN, CONFIGURATION), corpus=_spec(CORPUS_SPEC, section_caps=section_caps), namespaces=()
        )

        #: When
        occurrences = TooManyWords.check(subject)

        #: Then
        assert occurrences == (
            TooManyWords(spec=CORPUS_SPEC, line=LineNumber.from_int(3), word_count=6, cap=5),
            TooManyWords(spec=CORPUS_SPEC, line=LineNumber.from_int(7), word_count=12, cap=10),
        ), 'each section over its cap is reported, in document order'

    def test_check_with_a_section_over_only_the_namespace_cap_reports_that_cap(self) -> None:
        #: Given
        subject = HeadingsInput(
            headings=(TITLE, RUN, CONFIGURATION),
            corpus=_spec(CORPUS_SPEC, section_caps=(_cap(CONFIGURATION, 20),)),
            namespaces=(_spec(NAMESPACE_SPEC, section_caps=(_cap(CONFIGURATION, 10),)),),
        )

        #: When
        occurrences = TooManyWords.check(subject)

        #: Then
        assert occurrences == (
            TooManyWords(spec=NAMESPACE_SPEC, line=LineNumber.from_int(7), word_count=12, cap=10),
        ), 'a namespace cap does not replace the corpus one, so the section is held to it on its own'

    def test_check_with_a_section_over_both_caps_reports_each_in_order(self) -> None:
        #: Given
        subject = HeadingsInput(
            headings=(TITLE, RUN, CONFIGURATION),
            corpus=_spec(CORPUS_SPEC, section_caps=(_cap(CONFIGURATION, 10),)),
            namespaces=(_spec(NAMESPACE_SPEC, section_caps=(_cap(CONFIGURATION, 8),)),),
        )

        #: When
        occurrences = TooManyWords.check(subject)

        #: Then
        assert occurrences == (
            TooManyWords(spec=CORPUS_SPEC, line=LineNumber.from_int(7), word_count=12, cap=10),
            TooManyWords(spec=NAMESPACE_SPEC, line=LineNumber.from_int(7), word_count=12, cap=8),
        ), 'each specification applies on its own, so the section is reported once for each cap, in order'

    def test_message_with_an_occurrence_names_the_words_and_the_cap(self) -> None:
        #: Given
        occurrence = TooManyWords(spec=CORPUS_SPEC, line=LineNumber.from_int(7), word_count=12, cap=10)

        #: When
        message = occurrence.message()

        #: Then
        assert message == 'too many words (12 > 10)', 'the message sets the word count against the cap'

    def test_children_with_an_occurrence_point_at_the_spec(self) -> None:
        #: Given
        occurrence = TooManyWords(spec=CORPUS_SPEC, line=LineNumber.from_int(7), word_count=12, cap=10)

        #: When
        children = occurrence.children()

        #: Then
        assert children == (Note('the cap is set here', at=Elsewhere(CORPUS_SPEC)),), (
            'a note points at the specification that sets the cap'
        )
