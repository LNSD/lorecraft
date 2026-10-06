"""`OUT009`, `invalid-title`, over the pattern a document's title must match.

Every case is a document written as text, read through a fake context that parses it as the real parser does, under
structure specifications decoded from JSON; no document is read from disk.
"""

from typing import Final

import pytest

from lorecraft.core.path import RootRelativePath
from lorecraft.project.syntax import LineNumber
from lorecraft.rules.location import Elsewhere, Note
from lorecraft.rules.tests.fake_context import FakeDocumentContext, namespace_spec, structure_spec_path

from ..invalid_title import InvalidTitle

CORPUS_SPEC: Final[RootRelativePath] = structure_spec_path('guide')
"""The corpus structure specification."""

NAMESPACE_SPEC: Final[RootRelativePath] = structure_spec_path('guide-cli')
"""A namespace structure specification under the same corpus, which sets a title pattern of its own."""

TEXT: Final[str] = '# setup: first steps\n\n## Install\n\nInstall the toolkit once.\n'
"""A document whose H1 title, on line 1, is in lowercase and holds a colon, followed by one section."""

CAPITALIZED: Final[str] = '{"title": {"pattern": "^[A-Z]"}}'
"""A structure specification holding the title to open with a capital letter."""

NO_COLON: Final[str] = '{"title": {"pattern": "^[^:]+$"}}'
"""A structure specification holding the title to hold no colon."""

NO_PATTERN: Final[str] = '{"empty_sections": "forbidden"}'
"""A structure specification that sets no pattern on the title."""


@pytest.mark.unit
class TestInvalidTitle:
    def test_check_with_a_title_failing_its_pattern_reports_it_at_its_heading(self) -> None:
        #: Given
        subject = FakeDocumentContext(TEXT, corpus='guide', structure=CAPITALIZED)

        #: When
        occurrences = InvalidTitle.check(subject)

        #: Then
        assert occurrences == (
            InvalidTitle(spec=CORPUS_SPEC, line=LineNumber.from_int(1), title='setup: first steps', pattern='^[A-Z]'),
        ), 'a title failing its pattern is one occurrence, at its heading, naming the specification and the pattern'

    def test_check_with_a_title_matching_its_pattern_reports_nothing(self) -> None:
        #: Given
        subject = FakeDocumentContext('# Setup\n\nInstall the toolkit once.\n', corpus='guide', structure=CAPITALIZED)

        #: When
        occurrences = InvalidTitle.check(subject)

        #: Then
        assert occurrences == (), 'a title its pattern matches is not reported'

    def test_check_with_a_pattern_found_inside_the_title_reports_nothing(self) -> None:
        #: Given
        subject = FakeDocumentContext(TEXT, corpus='guide', structure='{"title": {"pattern": "first"}}')

        #: When
        occurrences = InvalidTitle.check(subject)

        #: Then
        assert occurrences == (), 'a pattern is searched for anywhere in the title, so one found inside it matches'

    def test_check_with_a_specification_setting_no_pattern_reports_nothing(self) -> None:
        #: Given
        subject = FakeDocumentContext(TEXT, corpus='guide', structure=NO_PATTERN)

        #: When
        occurrences = InvalidTitle.check(subject)

        #: Then
        assert occurrences == (), 'a specification setting no pattern holds the title to none'

    def test_check_with_a_document_without_a_title_reports_nothing(self) -> None:
        #: Given
        subject = FakeDocumentContext(
            '## install\n\nInstall the toolkit once.\n', corpus='guide', structure=CAPITALIZED
        )

        #: When
        occurrences = InvalidTitle.check(subject)

        #: Then
        assert occurrences == (), 'a missing title is reported as missing alone, not as a title off its pattern'

    def test_check_with_a_later_h1_failing_the_pattern_reports_nothing(self) -> None:
        #: Given
        text = '# Setup\n\nInstall the toolkit once.\n\n# setup again\n'
        subject = FakeDocumentContext(text, corpus='guide', structure=CAPITALIZED)

        #: When
        occurrences = InvalidTitle.check(subject)

        #: Then
        assert occurrences == (), 'only the first H1 is the title, so a later one is not held to the pattern'

    def test_check_with_a_title_failing_only_the_namespace_pattern_reports_that_pattern(self) -> None:
        #: Given
        subject = FakeDocumentContext(
            TEXT, corpus='guide', structure=NO_PATTERN, namespaces=(namespace_spec('guide', 'cli', NO_COLON),)
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
        subject = FakeDocumentContext(
            TEXT, corpus='guide', structure=CAPITALIZED, namespaces=(namespace_spec('guide', 'cli', NO_COLON),)
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
