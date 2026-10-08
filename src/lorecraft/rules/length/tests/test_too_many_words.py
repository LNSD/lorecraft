"""`LEN003`, `too-many-words`, over the word caps of a document's sections.

Every case is a document written as text, read through a fake context that parses it as the real parser does, under
structure specifications decoded from JSON; no document is read from disk.
"""

from typing import Final

import pytest

from lorecraft.core.path import RootRelativePath
from lorecraft.project.syntax import LineNumber
from lorecraft.rules.location import Elsewhere, Help, Here, Label, Note
from lorecraft.rules.tests.fake_context import FakeDocumentContext, namespace_spec, structure_spec_path

from ..too_many_words import AnyRunCap, NamedSectionCap, TooManyWords

CORPUS_SPEC: Final[RootRelativePath] = structure_spec_path('guide')
"""The corpus structure specification."""

NAMESPACE_SPEC: Final[RootRelativePath] = structure_spec_path('guide-cli')
"""A namespace structure specification under the same corpus, which sets caps of its own."""

TEXT: Final[str] = (
    '# Setup\n'
    '\n'
    '## Run\n'
    '\n'
    'Run the toolkit over the repository.\n'
    '\n'
    '## Configuration\n'
    '\n'
    'Every option has a default, and each one is documented right below.\n'
)
"""A title, then the sections `Run`, on line 3, of six prose words, and `Configuration`, on line 7, of twelve."""


def _outline(*, run: int | None, configuration: int | None) -> str:
    """A structure specification whose outline names both sections of `TEXT`, each with the cap given.

    Args:
        run: The most prose words `Run` may hold, or `None` for no cap.
        configuration: The most prose words `Configuration` may hold, or `None` for no cap.
    """
    run_entry = '{"section": "Run"}' if run is None else f'{{"section": "Run", "words": {run}}}'
    configuration_entry = (
        '{"section": "Configuration"}'
        if configuration is None
        else f'{{"section": "Configuration", "words": {configuration}}}'
    )
    return f'{{"outline": [{run_entry}, {configuration_entry}]}}'


@pytest.mark.unit
class TestTooManyWords:
    def test_check_with_a_section_over_its_cap_reports_it_at_its_heading(self) -> None:
        #: Given
        subject = FakeDocumentContext(TEXT, corpus='guide', structure=_outline(run=None, configuration=10))

        #: When
        occurrences = TooManyWords.check(subject)

        #: Then
        assert occurrences == (
            TooManyWords(
                spec=CORPUS_SPEC,
                line=LineNumber.from_int(7),
                section='Configuration',
                word_count=12,
                cap=10,
                cap_source=NamedSectionCap(),
            ),
        ), 'a section over its cap is one occurrence, at its heading, naming the specification that sets the cap'

    def test_check_with_a_section_at_its_cap_reports_nothing(self) -> None:
        #: Given
        subject = FakeDocumentContext(TEXT, corpus='guide', structure=_outline(run=None, configuration=12))

        #: When
        occurrences = TooManyWords.check(subject)

        #: Then
        assert occurrences == (), 'the cap is the most words allowed, so a section at its cap fits it'

    def test_check_with_no_section_capped_reports_nothing(self) -> None:
        #: Given
        subject = FakeDocumentContext(TEXT, corpus='guide', structure=_outline(run=None, configuration=None))

        #: When
        occurrences = TooManyWords.check(subject)

        #: Then
        assert occurrences == (), 'a section no cap applies to may hold any number of words'

    def test_check_with_two_sections_over_their_caps_reports_each_in_document_order(self) -> None:
        #: Given
        subject = FakeDocumentContext(TEXT, corpus='guide', structure=_outline(run=5, configuration=10))

        #: When
        occurrences = TooManyWords.check(subject)

        #: Then
        assert occurrences == (
            TooManyWords(
                spec=CORPUS_SPEC,
                line=LineNumber.from_int(3),
                section='Run',
                word_count=6,
                cap=5,
                cap_source=NamedSectionCap(),
            ),
            TooManyWords(
                spec=CORPUS_SPEC,
                line=LineNumber.from_int(7),
                section='Configuration',
                word_count=12,
                cap=10,
                cap_source=NamedSectionCap(),
            ),
        ), 'each section over its cap is reported, in document order'

    def test_check_with_unnamed_sections_holds_each_to_the_cap_of_the_any_run_it_falls_in(self) -> None:
        #: Given
        # `Rule` takes its entry's cap, `Aside` the cap of the `any` run after `Rule`, and `Checklist` none
        text = (
            '# Typing\n'
            '\n'
            '## Rule\n'
            '\n'
            'Annotate every signature.\n'
            '\n'
            '## Aside\n'
            '\n'
            'Read the rationale once.\n'
            '\n'
            '## Checklist\n'
            '\n'
            'Every signature is annotated, and every annotation is honest.\n'
        )
        outline = '{"outline": [{"section": "Rule", "words": 2}, {"any": true, "words": 2}, {"section": "Checklist"}]}'
        subject = FakeDocumentContext(text, corpus='guide', structure=outline)

        #: When
        occurrences = TooManyWords.check(subject)

        #: Then
        assert occurrences == (
            TooManyWords(
                spec=CORPUS_SPEC,
                line=LineNumber.from_int(3),
                section='Rule',
                word_count=3,
                cap=2,
                cap_source=NamedSectionCap(),
            ),
            TooManyWords(
                spec=CORPUS_SPEC,
                line=LineNumber.from_int(7),
                section='Aside',
                word_count=4,
                cap=2,
                cap_source=AnyRunCap(),
            ),
        ), 'a named section is held to its entry cap, an unnamed one to its run cap, and one with no cap to none'

    def test_check_with_two_any_runs_holds_each_unnamed_section_to_its_own_run_cap(self) -> None:
        #: Given
        # `Intro` falls in the first run, capped at 1 word, and `Detail`, after `Middle`, in the second, capped at 5
        text = '# Guide\n\n## Intro\n\nOne.\n\n## Middle\n\nText.\n\n## Detail\n\nOne two three.\n'
        outline = '{"outline": [{"any": true, "words": 1}, {"section": "Middle"}, {"any": true, "words": 5}]}'
        subject = FakeDocumentContext(text, corpus='guide', structure=outline)

        #: When
        occurrences = TooManyWords.check(subject)

        #: Then
        assert occurrences == (), 'a section after `Middle` falls in the second run, capped at 5 words, not 1'

    def test_check_with_a_section_over_only_the_namespace_cap_reports_that_cap(self) -> None:
        #: Given
        subject = FakeDocumentContext(
            TEXT,
            corpus='guide',
            structure=_outline(run=None, configuration=20),
            namespaces=(namespace_spec('guide', 'cli', _outline(run=None, configuration=10)),),
        )

        #: When
        occurrences = TooManyWords.check(subject)

        #: Then
        assert occurrences == (
            TooManyWords(
                spec=NAMESPACE_SPEC,
                line=LineNumber.from_int(7),
                section='Configuration',
                word_count=12,
                cap=10,
                cap_source=NamedSectionCap(),
            ),
        ), 'a namespace cap does not replace the corpus one, so the section is held to it on its own'

    def test_check_with_a_section_over_both_caps_reports_each_in_order(self) -> None:
        #: Given
        subject = FakeDocumentContext(
            TEXT,
            corpus='guide',
            structure=_outline(run=None, configuration=10),
            namespaces=(namespace_spec('guide', 'cli', _outline(run=None, configuration=8)),),
        )

        #: When
        occurrences = TooManyWords.check(subject)

        #: Then
        assert occurrences == (
            TooManyWords(
                spec=CORPUS_SPEC,
                line=LineNumber.from_int(7),
                section='Configuration',
                word_count=12,
                cap=10,
                cap_source=NamedSectionCap(),
            ),
            TooManyWords(
                spec=NAMESPACE_SPEC,
                line=LineNumber.from_int(7),
                section='Configuration',
                word_count=12,
                cap=8,
                cap_source=NamedSectionCap(),
            ),
        ), 'each specification applies on its own, so the section is reported once for each cap, in order'

    def test_message_with_an_occurrence_names_the_words_and_the_cap(self) -> None:
        #: Given
        occurrence = _named_occurrence()

        #: When
        message = occurrence.message()

        #: Then
        assert message == 'too many words in the section (12 > 10)', 'the message sets the words against the cap'

    def test_labels_with_an_occurrence_name_the_section_and_its_overrun_at_its_heading(self) -> None:
        #: Given
        occurrence = _named_occurrence()

        #: When
        labels = occurrence.labels()

        #: Then
        assert labels == (
            Label(Here(LineNumber.from_int(7)), '`Configuration` holds 12 prose words, 2 over its cap'),
        ), 'the label sits on the section heading and says how far past its cap the section runs'

    def test_children_with_a_cap_of_the_sections_entry_point_at_the_spec_then_help_then_the_entry(self) -> None:
        #: Given
        occurrence = _named_occurrence()

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Note('the limit is set here', at=Elsewhere(CORPUS_SPEC)),
            Help(
                'split the section, or move its detail into a document of its own; code blocks and table rows do not '
                'count toward the cap'
            ),
            Note("the cap is the `Configuration` entry's"),
        ), 'the specification note comes first, then the help, then whose cap it is'

    def test_children_with_a_cap_of_an_any_run_say_it_caps_each_section_the_outline_does_not_name(self) -> None:
        #: Given
        occurrence = TooManyWords(
            spec=CORPUS_SPEC,
            line=LineNumber.from_int(7),
            section='Aside',
            word_count=4,
            cap=2,
            cap_source=AnyRunCap(),
        )

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Note('the limit is set here', at=Elsewhere(CORPUS_SPEC)),
            Help(
                'split the section, or move its detail into a document of its own; code blocks and table rows do not '
                'count toward the cap'
            ),
            Note("the cap is the `any` run's, which caps each section the outline does not name"),
        ), 'a section the outline does not name is held to the run it falls in, and the note says so'


def _named_occurrence() -> TooManyWords:
    """The `Configuration` section of `TEXT` over a cap of 10 its own outline entry sets."""
    return TooManyWords(
        spec=CORPUS_SPEC,
        line=LineNumber.from_int(7),
        section='Configuration',
        word_count=12,
        cap=10,
        cap_source=NamedSectionCap(),
    )
