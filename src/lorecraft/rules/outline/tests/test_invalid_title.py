"""`OUT009`, `invalid-title`, over the pattern a document's title must match.

The rule is pure, so every case here is a document's headings and the title mismatch each specification resolved,
written as literals; no document is read. Whether a title matches is the input builder's to decide, so a case
holding no mismatch stands for a title that matched, for a specification that sets no pattern, or for no title.
"""

from typing import Final

import pytest

from lorecraft.core.path import RootRelativePath
from lorecraft.project.syntax import Heading, LineNumber
from lorecraft.rules.inputs import HeadingsInput, HeadingsSpec, TitleMismatch
from lorecraft.rules.location import Elsewhere, Note

from ..invalid_title import InvalidTitle

CORPUS_SPEC: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/guide.structure.json')
"""A corpus structure specification."""

NAMESPACE_SPEC: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/guide-cli.structure.json')
"""A namespace structure specification under the same corpus, which sets a title pattern of its own."""

TITLE: Final[Heading] = Heading(level=1, text='setup: first steps', line=LineNumber.from_int(1), empty=False, words=6)
"""An H1 title on line 1, in lowercase and holding a colon."""

INSTALL: Final[Heading] = Heading(level=2, text='Install', line=LineNumber.from_int(3), empty=False, words=6)
"""An H2 section on line 3."""

CAPITALIZED: Final[str] = '^[A-Z]'
"""A pattern a title opening with a capital letter matches."""

NO_COLON: Final[str] = '^[^:]+$'
"""A pattern a title holding no colon matches."""


def _spec(spec: RootRelativePath, mismatch: TitleMismatch | None) -> HeadingsSpec:
    """What a specification states over the headings: the mismatch its title pattern resolved, alone.

    Args:
        spec: The structure specification file.
        mismatch: The title and the pattern it does not match, or `None` when the specification found none.
    """
    return HeadingsSpec(
        spec=spec,
        title_cap=None,
        title_char_cap=None,
        title_mismatch=mismatch,
        forbid_empty_sections=False,
        forbidden=(),
        section_caps=(),
    )


@pytest.mark.unit
class TestInvalidTitle:
    def test_check_with_a_title_failing_its_pattern_reports_it_at_its_heading(self) -> None:
        #: Given
        mismatch = TitleMismatch(title=TITLE, pattern=CAPITALIZED)
        subject = HeadingsInput(headings=(TITLE, INSTALL), corpus=_spec(CORPUS_SPEC, mismatch), namespaces=())

        #: When
        occurrences = InvalidTitle.check(subject)

        #: Then
        assert occurrences == (
            InvalidTitle(spec=CORPUS_SPEC, line=LineNumber.from_int(1), title='setup: first steps', pattern='^[A-Z]'),
        ), 'a title failing its pattern is one occurrence, at its heading, naming the specification and the pattern'

    def test_check_with_a_title_matching_its_pattern_reports_nothing(self) -> None:
        #: Given
        # the builder holds no mismatch for a title its pattern matches
        subject = HeadingsInput(headings=(TITLE, INSTALL), corpus=_spec(CORPUS_SPEC, None), namespaces=())

        #: When
        occurrences = InvalidTitle.check(subject)

        #: Then
        assert occurrences == (), 'a title its pattern matches is not reported'

    def test_check_with_a_specification_setting_no_pattern_reports_nothing(self) -> None:
        #: Given
        # the builder holds no mismatch for a specification that sets no pattern
        subject = HeadingsInput(headings=(TITLE, INSTALL), corpus=_spec(CORPUS_SPEC, None), namespaces=())

        #: When
        occurrences = InvalidTitle.check(subject)

        #: Then
        assert occurrences == (), 'a specification setting no pattern holds the title to none'

    def test_check_with_a_document_without_a_title_reports_nothing(self) -> None:
        #: Given
        # the builder holds no mismatch for a document with no title, though the title rule sets a pattern
        subject = HeadingsInput(headings=(INSTALL,), corpus=_spec(CORPUS_SPEC, None), namespaces=())

        #: When
        occurrences = InvalidTitle.check(subject)

        #: Then
        assert occurrences == (), 'a missing title is reported as missing alone, not as a title off its pattern'

    def test_check_with_a_title_failing_only_the_namespace_pattern_reports_that_pattern(self) -> None:
        #: Given
        mismatch = TitleMismatch(title=TITLE, pattern=NO_COLON)
        subject = HeadingsInput(
            headings=(TITLE, INSTALL), corpus=_spec(CORPUS_SPEC, None), namespaces=(_spec(NAMESPACE_SPEC, mismatch),)
        )

        #: When
        occurrences = InvalidTitle.check(subject)

        #: Then
        assert occurrences == (
            InvalidTitle(
                spec=NAMESPACE_SPEC, line=LineNumber.from_int(1), title='setup: first steps', pattern='^[^:]+$'
            ),
        ), 'a namespace pattern does not replace the corpus one, so the title is held to it on its own'

    def test_check_with_a_title_failing_both_patterns_reports_each_in_order(self) -> None:
        #: Given
        corpus_mismatch = TitleMismatch(title=TITLE, pattern=CAPITALIZED)
        namespace_mismatch = TitleMismatch(title=TITLE, pattern=NO_COLON)
        subject = HeadingsInput(
            headings=(TITLE, INSTALL),
            corpus=_spec(CORPUS_SPEC, corpus_mismatch),
            namespaces=(_spec(NAMESPACE_SPEC, namespace_mismatch),),
        )

        #: When
        occurrences = InvalidTitle.check(subject)

        #: Then
        assert occurrences == (
            InvalidTitle(spec=CORPUS_SPEC, line=LineNumber.from_int(1), title='setup: first steps', pattern='^[A-Z]'),
            InvalidTitle(
                spec=NAMESPACE_SPEC, line=LineNumber.from_int(1), title='setup: first steps', pattern='^[^:]+$'
            ),
        ), 'each specification applies on its own, so the title is reported once for each pattern, in order'

    def test_message_with_an_occurrence_names_the_title(self) -> None:
        #: Given
        occurrence = InvalidTitle(
            spec=CORPUS_SPEC, line=LineNumber.from_int(1), title='setup: first steps', pattern='^[A-Z]'
        )

        #: When
        message = occurrence.message()

        #: Then
        assert message == 'title `setup: first steps` does not match the pattern', 'the message names the title'

    def test_children_with_an_occurrence_point_at_the_spec_and_give_the_pattern(self) -> None:
        #: Given
        occurrence = InvalidTitle(
            spec=CORPUS_SPEC, line=LineNumber.from_int(1), title='setup: first steps', pattern='^[A-Z]'
        )

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Note('the document structure is set here', at=Elsewhere(CORPUS_SPEC)),
            Note('the title must match `^[A-Z]`'),
        ), 'a note points at the specification that sets the pattern, and another gives the pattern'
