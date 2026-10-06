"""`LEN004`, `title-too-many-words`, over the word cap of a document's title.

The rule is pure, so every case here is a document's headings and the title cap each specification resolved,
written as literals; no document is read.
"""

from typing import Final

import pytest

from lorecraft.core.num import NonZeroUnsignedInt
from lorecraft.core.path import RootRelativePath
from lorecraft.project.syntax import Heading, LineNumber
from lorecraft.rules.inputs import HeadingsInput, HeadingsSpec, TitleCap
from lorecraft.rules.location import Elsewhere, Help, Note

from ..title_too_many_words import TitleTooManyWords

CORPUS_SPEC: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/guide.structure.json')
"""A corpus structure specification."""

NAMESPACE_SPEC: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/guide-cli.structure.json')
"""A namespace structure specification under the same corpus, which sets a title cap of its own."""

TITLE: Final[Heading] = Heading(
    level=1, text='Setting up the toolkit on a new machine', line=LineNumber.from_int(1), empty=False, words=6
)
"""An H1 title on line 1, of eight words, opening a section of six prose words."""

TITLE_WORDS: Final[int] = 8
"""The words of `TITLE`'s text."""

RUN: Final[Heading] = Heading(level=2, text='Run', line=LineNumber.from_int(3), empty=False, words=6)
"""An H2 section on line 3, of six prose words."""


def _spec(spec: RootRelativePath, cap: int | None) -> HeadingsSpec:
    """What a specification states over the headings: the cap it sets on `TITLE`'s words, alone.

    Args:
        spec: The structure specification file.
        cap: The most words the title may hold, or `None` for a specification that sets no cap.
    """
    if cap is None:
        return HeadingsSpec(
            spec=spec, title_cap=None, title_mismatch=None, forbid_empty_sections=False, forbidden=(), section_caps=()
        )
    title_cap = TitleCap(title=TITLE, title_words=TITLE_WORDS, words=NonZeroUnsignedInt(cap))
    return HeadingsSpec(
        spec=spec, title_cap=title_cap, title_mismatch=None, forbid_empty_sections=False, forbidden=(), section_caps=()
    )


@pytest.mark.unit
class TestTitleTooManyWords:
    def test_check_with_a_title_over_its_cap_reports_it_at_its_heading(self) -> None:
        #: Given
        subject = HeadingsInput(headings=(TITLE, RUN), corpus=_spec(CORPUS_SPEC, 5), namespaces=())

        #: When
        occurrences = TitleTooManyWords.check(subject)

        #: Then
        assert occurrences == (
            TitleTooManyWords(spec=CORPUS_SPEC, line=LineNumber.from_int(1), word_count=8, cap=5),
        ), 'a title over its cap is one occurrence, at its heading, naming the specification that sets the cap'

    def test_check_with_a_title_at_its_cap_reports_nothing(self) -> None:
        #: Given
        subject = HeadingsInput(headings=(TITLE, RUN), corpus=_spec(CORPUS_SPEC, 8), namespaces=())

        #: When
        occurrences = TitleTooManyWords.check(subject)

        #: Then
        assert occurrences == (), 'the cap is the most words allowed, so a title at its cap fits it'

    def test_check_with_a_specification_setting_no_cap_reports_nothing(self) -> None:
        #: Given
        subject = HeadingsInput(headings=(TITLE, RUN), corpus=_spec(CORPUS_SPEC, None), namespaces=())

        #: When
        occurrences = TitleTooManyWords.check(subject)

        #: Then
        assert occurrences == (), 'a title no cap applies to may hold any number of words'

    def test_check_with_a_document_without_a_title_reports_nothing(self) -> None:
        #: Given
        # the builder holds no title cap for a document with no title, though the specification sets one
        subject = HeadingsInput(headings=(RUN,), corpus=_spec(CORPUS_SPEC, None), namespaces=())

        #: When
        occurrences = TitleTooManyWords.check(subject)

        #: Then
        assert occurrences == (), 'a missing title is reported as missing alone, not as a title over its cap'

    def test_check_with_a_cap_set_by_the_namespace_alone_reports_it_under_the_namespace(self) -> None:
        #: Given
        subject = HeadingsInput(
            headings=(TITLE, RUN), corpus=_spec(CORPUS_SPEC, None), namespaces=(_spec(NAMESPACE_SPEC, 6),)
        )

        #: When
        occurrences = TitleTooManyWords.check(subject)

        #: Then
        assert occurrences == (
            TitleTooManyWords(spec=NAMESPACE_SPEC, line=LineNumber.from_int(1), word_count=8, cap=6),
        ), 'a cap is the specification that sets it, so it is reported under the namespace, not the corpus'

    def test_check_with_a_title_over_only_the_namespace_cap_reports_that_cap(self) -> None:
        #: Given
        subject = HeadingsInput(
            headings=(TITLE, RUN), corpus=_spec(CORPUS_SPEC, 10), namespaces=(_spec(NAMESPACE_SPEC, 6),)
        )

        #: When
        occurrences = TitleTooManyWords.check(subject)

        #: Then
        assert occurrences == (
            TitleTooManyWords(spec=NAMESPACE_SPEC, line=LineNumber.from_int(1), word_count=8, cap=6),
        ), 'a namespace cap does not replace the corpus one, so the title is held to it on its own'

    def test_check_with_a_title_over_both_caps_reports_each_in_order(self) -> None:
        #: Given
        subject = HeadingsInput(
            headings=(TITLE, RUN), corpus=_spec(CORPUS_SPEC, 7), namespaces=(_spec(NAMESPACE_SPEC, 5),)
        )

        #: When
        occurrences = TitleTooManyWords.check(subject)

        #: Then
        assert occurrences == (
            TitleTooManyWords(spec=CORPUS_SPEC, line=LineNumber.from_int(1), word_count=8, cap=7),
            TitleTooManyWords(spec=NAMESPACE_SPEC, line=LineNumber.from_int(1), word_count=8, cap=5),
        ), 'each specification applies on its own, so the title is reported once for each cap, in order'

    def test_message_with_an_occurrence_names_the_words_and_the_cap(self) -> None:
        #: Given
        occurrence = TitleTooManyWords(spec=CORPUS_SPEC, line=LineNumber.from_int(1), word_count=8, cap=5)

        #: When
        message = occurrence.message()

        #: Then
        assert message == 'too many words in the title (8 > 5)', 'the message sets the word count against the cap'

    def test_children_with_an_occurrence_point_at_the_spec_and_say_how_many_words_to_cut(self) -> None:
        #: Given
        occurrence = TitleTooManyWords(spec=CORPUS_SPEC, line=LineNumber.from_int(1), word_count=8, cap=5)

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Note('the cap is set here', at=Elsewhere(CORPUS_SPEC)),
            Help('cut at least 3 words'),
        ), 'a note points at the specification that sets the cap, and a help names the words over it'
