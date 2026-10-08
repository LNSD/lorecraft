"""`LINK004`, `escaping-link`, over the relative links of one of a skill's Markdown files.

Every case is a skill's file written as text and parsed by the real parser, through a fake resource context; the rule
reads what any of a skill's files has, so a `SKILL.md` is judged the same way.
"""

import pytest

from lorecraft.project.syntax import LineNumber
from lorecraft.rules.location import Help, Note
from lorecraft.rules.tests.fake_context import FakeSkillResourceContext

from ..escaping_link import EscapingLink


@pytest.mark.unit
class TestEscapingLink:
    def test_check_with_a_link_climbing_above_the_skill_root_reports_it_on_its_line(self) -> None:
        #: Given
        subject = FakeSkillResourceContext('# Checklist\n\nStart from [the steps](../SKILL.md).\n')

        #: When
        occurrences = EscapingLink.check(subject)

        #: Then
        assert occurrences == (EscapingLink(line=LineNumber.from_int(3), url='../SKILL.md'),), (
            'a path read from the skill root that climbs above it is one occurrence, on the line of the link'
        )

    def test_check_with_a_link_back_in_by_the_repository_path_reports_it(self) -> None:
        #: Given
        subject = FakeSkillResourceContext('[the steps](../../skills/review/SKILL.md)\n')

        #: When
        occurrences = EscapingLink.check(subject)

        #: Then
        assert occurrences == (EscapingLink(line=LineNumber.from_int(1), url='../../skills/review/SKILL.md'),), (
            'the path alone decides, so a link out and back in by where the skill lies in the repository escapes'
        )

    def test_check_with_an_image_climbing_above_the_skill_root_reports_it(self) -> None:
        #: Given
        subject = FakeSkillResourceContext('![flow](../../flow.png)\n')

        #: When
        occurrences = EscapingLink.check(subject)

        #: Then
        assert occurrences == (EscapingLink(line=LineNumber.from_int(1), url='../../flow.png'),), (
            "an image's source is read from the skill root like a link's"
        )

    def test_check_with_percent_encoded_dots_climbing_above_the_skill_root_reports_it(self) -> None:
        #: Given
        subject = FakeSkillResourceContext('[a b](%2E%2E/a%20b.md)\n')

        #: When
        occurrences = EscapingLink.check(subject)

        #: Then
        assert occurrences == (EscapingLink(line=LineNumber.from_int(1), url='%2E%2E/a%20b.md'),), (
            'the path is percent-decoded before it is read, so encoded dots climb above the skill root as `..` does'
        )

    def test_check_with_a_link_climbing_and_coming_back_inside_reports_nothing(self) -> None:
        #: Given
        subject = FakeSkillResourceContext('[the steps](references/../SKILL.md)\n')

        #: When
        occurrences = EscapingLink.check(subject)

        #: Then
        assert occurrences == (), 'references/../SKILL.md normalises to SKILL.md, inside the skill'

    def test_check_with_a_link_to_the_skill_root_itself_reports_nothing(self) -> None:
        #: Given
        subject = FakeSkillResourceContext('[the skill](references/..)\n')

        #: When
        occurrences = EscapingLink.check(subject)

        #: Then
        assert occurrences == (), 'references/.. normalises to the skill root itself, which is not above it'

    def test_check_with_a_url_with_a_scheme_reports_nothing(self) -> None:
        #: Given
        subject = FakeSkillResourceContext('[the spec](https://example.com/../spec)\n')

        #: When
        occurrences = EscapingLink.check(subject)

        #: Then
        assert occurrences == (), 'a URL with a scheme spells no relative path, so it never escapes'

    def test_check_with_an_absolute_link_reports_nothing(self) -> None:
        #: Given
        subject = FakeSkillResourceContext('[up](/../outside.md)\n')

        #: When
        occurrences = EscapingLink.check(subject)

        #: Then
        assert occurrences == (), 'an absolute link spells no relative path; it is LINK001, not this rule'

    def test_check_with_a_fragment_only_link_reports_nothing(self) -> None:
        #: Given
        subject = FakeSkillResourceContext('# Checklist\n\nSee [the top](#checklist).\n')

        #: When
        occurrences = EscapingLink.check(subject)

        #: Then
        assert occurrences == (), 'a fragment-only link spells no path at all'

    def test_message_with_a_percent_encoded_destination_shows_it_decoded(self) -> None:
        #: Given
        # The destination of `[x](<../a b.md>)`, as the parser percent-encodes it.
        occurrence = EscapingLink(line=LineNumber.from_int(1), url='../a%20b.md')

        #: When
        message = occurrence.message()

        #: Then
        assert message == '`../a b.md` leaves the skill root', (
            'the message shows the destination as the author wrote it'
        )

    def test_children_with_an_occurrence_say_to_link_inside_the_skill_from_its_root(self) -> None:
        #: Given
        occurrence = EscapingLink(line=LineNumber.from_int(1), url='../SKILL.md')

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Note("the Agent Skills specification reads a skill's relative links from the skill root"),
            Help('link a file inside the skill, relative to the skill root'),
        ), 'the specification note comes first, then a help saying to name a file by its path from the skill root'
