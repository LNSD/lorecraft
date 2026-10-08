"""`LINK002`, `missing-fragment`, over the fragment-only links of one Markdown file and its own headings.

Every case is a Markdown file written as text and parsed by the real parser, through a fake resource context; the rule
reads what any Markdown file has, so a document and a `SKILL.md` are judged the same way.
"""

import pytest

from lorecraft.project.syntax import LineNumber
from lorecraft.rules.location import Note
from lorecraft.rules.tests.fake_context import FakeSkillResourceContext

from ..missing_fragment import MissingFragment


@pytest.mark.unit
class TestMissingFragment:
    def test_check_with_a_fragment_naming_no_heading_reports_it_on_its_line(self) -> None:
        #: Given
        subject = FakeSkillResourceContext('# Guide\n\nSee [usage](#usage).\n')

        #: When
        occurrences = MissingFragment.check(subject)

        #: Then
        assert occurrences == (MissingFragment(line=LineNumber.from_int(3), url='#usage', has_headings=True),), (
            'a fragment naming no heading of the file is one occurrence, on the line the link is on'
        )

    def test_check_with_a_file_holding_no_heading_reports_it_as_having_none(self) -> None:
        #: Given
        subject = FakeSkillResourceContext('See [usage](#usage).\n')

        #: When
        occurrences = MissingFragment.check(subject)

        #: Then
        assert occurrences == (MissingFragment(line=LineNumber.from_int(1), url='#usage', has_headings=False),), (
            'the occurrence records that the file has no heading to name'
        )

    def test_check_with_a_fragment_naming_a_heading_of_the_file_reports_nothing(self) -> None:
        #: Given
        subject = FakeSkillResourceContext('# Guide\n\nSee [usage](#usage).\n\n## Usage\n')

        #: When
        occurrences = MissingFragment.check(subject)

        #: Then
        assert occurrences == (), 'a fragment naming a heading the file has, wherever it is, goes somewhere'

    def test_check_with_a_fragment_written_in_another_case_reports_nothing(self) -> None:
        #: Given
        subject = FakeSkillResourceContext('# Guide\n\nSee [usage](#Usage).\n\n## Usage\n')

        #: When
        occurrences = MissingFragment.check(subject)

        #: Then
        assert occurrences == (), 'a fragment resolves regardless of case, so `#Usage` names `## Usage`'

    def test_check_with_a_fragment_no_heading_can_have_reports_it(self) -> None:
        #: Given
        # The parser percent-encodes the space of `<#a b>`; no anchor holds a space, whatever the headings are.
        subject = FakeSkillResourceContext('# Guide\n\nSee [x](<#a b>).\n\n## A b\n')

        #: When
        occurrences = MissingFragment.check(subject)

        #: Then
        assert occurrences == (MissingFragment(line=LineNumber.from_int(3), url='#a%20b', has_headings=True),), (
            'a fragment that is no anchor at all names no heading, so it is reported'
        )

    def test_check_with_a_bare_hash_reports_nothing(self) -> None:
        #: Given
        subject = FakeSkillResourceContext('# Guide\n\nBack to [the top](#).\n')

        #: When
        occurrences = MissingFragment.check(subject)

        #: Then
        assert occurrences == (), 'a bare # names no heading, so it names no missing one'

    def test_check_with_a_fragment_after_a_path_reports_nothing(self) -> None:
        #: Given
        subject = FakeSkillResourceContext('# Guide\n\nSee [usage](setup.md#usage).\n')

        #: When
        occurrences = MissingFragment.check(subject)

        #: Then
        assert occurrences == (), "a fragment after a path names another file's heading, which this rule does not check"

    def test_check_with_a_url_with_a_fragment_reports_nothing(self) -> None:
        #: Given
        subject = FakeSkillResourceContext('# Guide\n\nSee [usage](https://example.com/setup#usage).\n')

        #: When
        occurrences = MissingFragment.check(subject)

        #: Then
        assert occurrences == (), "a URL's fragment names a heading of another page, not of this file"

    def test_check_with_several_missing_fragments_reports_each_in_document_order(self) -> None:
        #: Given
        subject = FakeSkillResourceContext('# Guide\n\nSee [b](#b), [guide](#guide).\n\nAnd [a](#a).\n')

        #: When
        occurrences = MissingFragment.check(subject)

        #: Then
        assert occurrences == (
            MissingFragment(line=LineNumber.from_int(3), url='#b', has_headings=True),
            MissingFragment(line=LineNumber.from_int(5), url='#a', has_headings=True),
        ), 'each missing fragment is its own occurrence, in file order, and the one naming the title none'

    def test_message_with_a_percent_encoded_fragment_shows_it_decoded(self) -> None:
        #: Given
        # The destination of `[x](#Straße)`, as the parser percent-encodes it.
        occurrence = MissingFragment(line=LineNumber.from_int(1), url='#Stra%C3%9Fe', has_headings=True)

        #: When
        message = occurrence.message()

        #: Then
        assert message == '`#Straße` names a heading this file does not have', (
            'the message shows the destination as the author wrote it'
        )

    def test_children_with_a_file_holding_headings_are_none(self) -> None:
        #: Given
        occurrence = MissingFragment(line=LineNumber.from_int(3), url='#usage', has_headings=True)

        #: When
        children = occurrence.children()

        #: Then
        assert children == (), 'the message names the fragment, and the fix depends on which heading was meant'

    def test_children_with_a_file_holding_no_heading_note_that_it_has_none(self) -> None:
        #: Given
        occurrence = MissingFragment(line=LineNumber.from_int(3), url='#usage', has_headings=False)

        #: When
        children = occurrence.children()

        #: Then
        assert children == (Note('this file has no headings'),), 'no heading was meant when the file has none'
