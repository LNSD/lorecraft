"""`LINK001`, `absolute-link`, over the links of one Markdown file.

Every case is a Markdown file written as text and parsed by the real parser, through a fake resource context; the rule
reads what any Markdown file has, so a document and a `SKILL.md` are judged the same way.
"""

import pytest

from lorecraft.project.syntax import LineNumber
from lorecraft.rules.location import Help
from lorecraft.rules.tests.fake_context import FakeSkillResourceContext

from ..absolute_link import AbsoluteLink


@pytest.mark.unit
class TestAbsoluteLink:
    def test_check_with_a_link_starting_with_a_slash_reports_it_on_its_line(self) -> None:
        #: Given
        subject = FakeSkillResourceContext('# Guide\n\nRead [the setup](/docs/guide/setup.md).\n')

        #: When
        occurrences = AbsoluteLink.check(subject)

        #: Then
        assert occurrences == (AbsoluteLink(line=LineNumber.from_int(3), url='/docs/guide/setup.md'),), (
            'a link whose destination starts with / is one occurrence, on the line the link is on'
        )

    def test_check_with_an_image_starting_with_a_slash_reports_it_on_its_line(self) -> None:
        #: Given
        subject = FakeSkillResourceContext('# Guide\n\n![the diagram](/assets/flow.png)\n')

        #: When
        occurrences = AbsoluteLink.check(subject)

        #: Then
        assert occurrences == (AbsoluteLink(line=LineNumber.from_int(3), url='/assets/flow.png'),), (
            "an image's source is a destination like a link's, so one starting with / is reported too"
        )

    def test_check_with_a_url_with_a_scheme_reports_nothing(self) -> None:
        #: Given
        subject = FakeSkillResourceContext('# Guide\n\nRead [the setup](https://example.com/setup).\n')

        #: When
        occurrences = AbsoluteLink.check(subject)

        #: Then
        assert occurrences == (), 'a URL with a scheme starts with its scheme, not with /, so it is not absolute'

    def test_check_with_a_fragment_only_link_reports_nothing(self) -> None:
        #: Given
        subject = FakeSkillResourceContext('# Guide\n\n## Usage\n\nSee [usage](#usage).\n')

        #: When
        occurrences = AbsoluteLink.check(subject)

        #: Then
        assert occurrences == (), 'a link to a heading of the same file starts with #, not with /'

    def test_check_with_a_relative_link_reports_nothing(self) -> None:
        #: Given
        subject = FakeSkillResourceContext('# Guide\n\nRead [the setup](setup.md).\n')

        #: When
        occurrences = AbsoluteLink.check(subject)

        #: Then
        assert occurrences == (), 'a relative path names no filesystem root'

    def test_check_with_several_absolute_links_reports_each_in_document_order(self) -> None:
        #: Given
        subject = FakeSkillResourceContext('# Guide\n\nRead [b](/b.md), then [setup](setup.md).\n\nAnd [a](/a.md).\n')

        #: When
        occurrences = AbsoluteLink.check(subject)

        #: Then
        assert occurrences == (
            AbsoluteLink(line=LineNumber.from_int(3), url='/b.md'),
            AbsoluteLink(line=LineNumber.from_int(5), url='/a.md'),
        ), 'each absolute link is its own occurrence, in the order the file holds them, and the relative one none'

    def test_message_with_a_percent_encoded_destination_shows_it_decoded(self) -> None:
        #: Given
        # The destination of `[x](</a b.md>)`, as the parser percent-encodes it.
        occurrence = AbsoluteLink(line=LineNumber.from_int(1), url='/a%20b.md')

        #: When
        message = occurrence.message()

        #: Then
        assert message == 'link `/a b.md` is absolute', 'the message shows the destination as the author wrote it'

    def test_children_with_an_occurrence_say_to_link_by_a_relative_path(self) -> None:
        #: Given
        occurrence = AbsoluteLink(line=LineNumber.from_int(3), url='/docs/guide/setup.md')

        #: When
        children = occurrence.children()

        #: Then
        assert children == (Help('link by a relative path, which holds wherever the files are placed'),), (
            'a help says how to fix the link, naming no directory it is read from, which depends on the file'
        )
