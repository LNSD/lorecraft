"""Link validation over the links and the heading anchors of a skill's ``SKILL.md`` and of its resources.

``validate_skill_links`` and ``validate_skill_resource_links`` are pure, so every case here is a tuple of links, a
set of ``Anchor`` values, what the snapshot holds at each path a link names and the paths ``metadata`` links in,
all built in memory; no file is read or parsed, and no path is looked up.
"""

from pathlib import PurePosixPath
from typing import Final

import pytest

from lorecraft.project.syntax import Anchor, LineNumber, Link

from ..reporting import Note, NoteKind, Violation
from ..skill_link import LinkTargetState, link_path_in_skill, validate_skill_links, validate_skill_resource_links

_BROKEN_HELP: Final[tuple[Note, ...]] = (
    Note(NoteKind.HELP, 'link a file or a directory the skill holds, relative to the skill root'),
)
"""The help a `skill.link-broken` violation carries, whatever the link."""

_ABSOLUTE_HELP: Final[tuple[Note, ...]] = (Note(NoteKind.HELP, 'link relative to the skill root'),)
"""The help a `skill.link-absolute` violation carries, whatever the link."""

_ESCAPE_HELP: Final[tuple[Note, ...]] = (
    Note(NoteKind.HELP, 'link a file inside the skill, relative to the skill root'),
)
"""The help a `skill.link-escapes` violation carries, whatever the link."""


@pytest.mark.unit
class TestValidateSkillLinks:
    def test_validate_skill_links_with_an_absolute_link_reports_it_on_its_line(self) -> None:
        #: Given
        links = (Link(url='/docs/guide.md', line=LineNumber(7)),)

        #: When
        result = validate_skill_links(links=links, anchors=frozenset(), targets={}, linked_in=frozenset())

        #: Then
        assert result.violations == (
            Violation(
                line=LineNumber(7),
                rule='skill.link-absolute',
                message='`/docs/guide.md` is absolute',
                notes=_ABSOLUTE_HELP,
            ),
        ), 'a link from the filesystem root is one violation, on the line the link is on'

    def test_validate_skill_links_with_an_encoded_absolute_link_shows_it_decoded(self) -> None:
        #: Given
        links = (Link(url='/a%20b', line=LineNumber(3)),)

        #: When
        result = validate_skill_links(links=links, anchors=frozenset(), targets={}, linked_in=frozenset())

        #: Then
        assert result.violations == (
            Violation(
                line=LineNumber(3),
                rule='skill.link-absolute',
                message='`/a b` is absolute',
                notes=_ABSOLUTE_HELP,
            ),
        ), 'the message shows the destination as it was written, not as the parser percent-encoded it'

    def test_validate_skill_links_with_a_relative_link_returns_no_violations(self) -> None:
        #: Given
        links = (Link(url='references/guide.md', line=LineNumber(3)),)
        targets = {PurePosixPath('references/guide.md'): LinkTargetState.PRESENT}

        #: When
        result = validate_skill_links(links=links, anchors=frozenset(), targets=targets, linked_in=frozenset())

        #: Then
        assert result.violations == (), 'a link relative to the skill root is what the rule asks for'

    def test_validate_skill_links_with_a_link_climbing_out_of_the_skill_reports_it_escaping(self) -> None:
        #: Given
        links = (Link(url='../../docs/guide.md', line=LineNumber(3)),)

        #: When
        result = validate_skill_links(links=links, anchors=frozenset(), targets={}, linked_in=frozenset())

        #: Then
        assert result.violations == (
            Violation(
                line=LineNumber(3),
                rule='skill.link-escapes',
                message='`../../docs/guide.md` leaves the skill directory',
                notes=_ESCAPE_HELP,
            ),
        ), 'a relative link leaving the skill escapes it, and is not absolute'

    def test_validate_skill_links_with_a_url_scheme_returns_no_violations(self) -> None:
        #: Given
        links = (
            Link(url='https://agentskills.io/specification', line=LineNumber(3)),
            Link(url='mailto:team@example.com', line=LineNumber(4)),
        )

        #: When
        result = validate_skill_links(links=links, anchors=frozenset(), targets={}, linked_in=frozenset())

        #: Then
        assert result.violations == (), 'a URL with a scheme points outside the skill, not at a path'

    def test_validate_skill_links_with_a_fragment_naming_a_heading_returns_no_violations(self) -> None:
        #: Given
        links = (Link(url='#checklist', line=LineNumber(3)),)
        anchors = frozenset({Anchor('overview'), Anchor('checklist')})

        #: When
        result = validate_skill_links(links=links, anchors=anchors, targets={}, linked_in=frozenset())

        #: Then
        assert result.violations == (), 'a fragment naming a heading of the SKILL.md points at something it holds'

    def test_validate_skill_links_with_a_fragment_naming_no_heading_reports_it_on_its_line(self) -> None:
        #: Given
        links = (Link(url='#usage', line=LineNumber(4)),)
        anchors = frozenset({Anchor('overview'), Anchor('checklist')})

        #: When
        result = validate_skill_links(links=links, anchors=anchors, targets={}, linked_in=frozenset())

        #: Then
        assert result.violations == (
            Violation(
                line=LineNumber(4),
                rule='skill.link-fragment',
                message='`#usage` names a heading this file does not have',
            ),
        ), 'a fragment naming no heading of the SKILL.md is one violation, on the line the link is on'

    def test_validate_skill_links_with_a_percent_encoded_fragment_matches_the_decoded_heading_anchor(self) -> None:
        #: Given
        links = (Link(url='#stra%C3%9Fe', line=LineNumber(3)),)
        anchors = frozenset({Anchor('straße')})

        #: When
        result = validate_skill_links(links=links, anchors=anchors, targets={}, linked_in=frozenset())

        #: Then
        assert result.violations == (), 'the fragment is percent-decoded before it is looked up among the anchors'

    def test_validate_skill_links_with_an_uppercase_fragment_matches_the_lowercase_heading_anchor(self) -> None:
        #: Given
        links = (Link(url='#Usage', line=LineNumber(3)),)
        anchors = frozenset({Anchor('usage')})

        #: When
        result = validate_skill_links(links=links, anchors=anchors, targets={}, linked_in=frozenset())

        #: Then
        assert result.violations == (), 'GitHub resolves a fragment regardless of case, so the check does too'

    def test_validate_skill_links_with_a_dangling_non_ascii_fragment_shows_it_decoded(self) -> None:
        #: Given
        links = (Link(url='#Stra%C3%9Fe', line=LineNumber(3)),)
        anchors = frozenset({Anchor('usage')})

        #: When
        result = validate_skill_links(links=links, anchors=anchors, targets={}, linked_in=frozenset())

        #: Then
        assert result.violations == (
            Violation(
                line=LineNumber(3),
                rule='skill.link-fragment',
                message='`#Straße` names a heading this file does not have',
            ),
        ), 'the message shows the fragment as it was written, not as the parser percent-encoded it'

    def test_validate_skill_links_with_a_fragment_no_heading_can_have_reports_it(self) -> None:
        #: Given
        links = (Link(url='#getting%20started', line=LineNumber(3)),)
        anchors = frozenset({Anchor('getting-started')})

        #: When
        result = validate_skill_links(links=links, anchors=anchors, targets={}, linked_in=frozenset())

        #: Then
        assert result.violations == (
            Violation(
                line=LineNumber(3),
                rule='skill.link-fragment',
                message='`#getting started` names a heading this file does not have',
            ),
        ), 'a fragment holding a space is no anchor, so it dangles even beside the anchor it was meant to name'

    def test_validate_skill_links_with_a_bare_hash_returns_no_violations(self) -> None:
        #: Given
        links = (Link(url='#', line=LineNumber(3)),)

        #: When
        result = validate_skill_links(links=links, anchors=frozenset(), targets={}, linked_in=frozenset())

        #: Then
        assert result.violations == (), 'an empty fragment names no heading, so there is none to miss'

    def test_validate_skill_links_with_a_fragment_into_another_file_returns_no_violations(self) -> None:
        #: Given
        links = (Link(url='references/guide.md#usage', line=LineNumber(3)),)
        targets = {PurePosixPath('references/guide.md'): LinkTargetState.PRESENT}

        #: When
        result = validate_skill_links(links=links, anchors=frozenset(), targets=targets, linked_in=frozenset())

        #: Then
        assert result.violations == (), 'a fragment into another file is not checked against the SKILL.md headings'

    def test_validate_skill_links_with_a_fragment_after_the_skill_md_path_returns_no_violations(self) -> None:
        #: Given
        links = (Link(url='SKILL.md#usage', line=LineNumber(4)),)
        targets = {PurePosixPath('SKILL.md'): LinkTargetState.PRESENT}

        #: When
        result = validate_skill_links(links=links, anchors=frozenset(), targets=targets, linked_in=frozenset())

        #: Then
        assert result.violations == (), 'only a fragment-only link is checked, even when the path names SKILL.md'

    def test_validate_skill_links_with_absolute_and_fragment_links_reports_each_in_the_order_given(self) -> None:
        #: Given
        links = (
            Link(url='#usage', line=LineNumber(5)),
            Link(url='/a.md', line=LineNumber(6)),
            Link(url='#checklist', line=LineNumber(7)),
            Link(url='#setup', line=LineNumber(8)),
        )
        anchors = frozenset({Anchor('checklist')})

        #: When
        result = validate_skill_links(links=links, anchors=anchors, targets={}, linked_in=frozenset())

        #: Then
        assert result.violations == (
            Violation(
                line=LineNumber(5),
                rule='skill.link-fragment',
                message='`#usage` names a heading this file does not have',
            ),
            Violation(
                line=LineNumber(6),
                rule='skill.link-absolute',
                message='`/a.md` is absolute',
                notes=_ABSOLUTE_HELP,
            ),
            Violation(
                line=LineNumber(8),
                rule='skill.link-fragment',
                message='`#setup` names a heading this file does not have',
            ),
        ), 'each rule reports in link order, and the fragment naming a heading between them is not reported'

    def test_validate_skill_links_with_several_absolute_links_reports_each_in_the_order_given(self) -> None:
        #: Given
        links = (
            Link(url='/a.md', line=LineNumber(5)),
            Link(url='b.md', line=LineNumber(6)),
            Link(url='/c.png', line=LineNumber(9)),
        )
        targets = {PurePosixPath('b.md'): LinkTargetState.PRESENT}

        #: When
        result = validate_skill_links(links=links, anchors=frozenset(), targets=targets, linked_in=frozenset())

        #: Then
        assert result.violations == (
            Violation(
                line=LineNumber(5),
                rule='skill.link-absolute',
                message='`/a.md` is absolute',
                notes=_ABSOLUTE_HELP,
            ),
            Violation(
                line=LineNumber(9),
                rule='skill.link-absolute',
                message='`/c.png` is absolute',
                notes=_ABSOLUTE_HELP,
            ),
        ), 'every absolute link is its own violation, in document order, and the relative one between them is not'

    def test_validate_skill_links_with_a_link_to_a_missing_file_reports_it_broken_on_its_line(self) -> None:
        #: Given
        links = (Link(url='references/gone.md', line=LineNumber(6)),)
        targets = {PurePosixPath('references/gone.md'): LinkTargetState.MISSING}

        #: When
        result = validate_skill_links(links=links, anchors=frozenset(), targets=targets, linked_in=frozenset())

        #: Then
        assert result.violations == (
            Violation(
                line=LineNumber(6),
                rule='skill.link-broken',
                message='`references/gone.md` names nothing in the skill',
                notes=_BROKEN_HELP,
            ),
        ), 'a link inside the skill to a path the snapshot holds nothing at is one violation, on its line, with help'

    def test_validate_skill_links_with_a_link_to_a_directory_the_skill_holds_returns_no_violations(self) -> None:
        #: Given
        # the run looks a directory up as it looks up a file, so either is present
        links = (Link(url='references/', line=LineNumber(3)),)
        targets = {PurePosixPath('references'): LinkTargetState.PRESENT}

        #: When
        result = validate_skill_links(links=links, anchors=frozenset(), targets=targets, linked_in=frozenset())

        #: Then
        assert result.violations == (), 'a directory the skill holds is something a link may name'

    def test_validate_skill_links_with_a_missing_file_metadata_links_in_returns_no_violations(self) -> None:
        #: Given
        links = (Link(url='references/logging.md', line=LineNumber(3)),)
        targets = {PurePosixPath('references/logging.md'): LinkTargetState.MISSING}
        linked_in = frozenset({PurePosixPath('references/logging.md')})

        #: When
        result = validate_skill_links(links=links, anchors=frozenset(), targets=targets, linked_in=linked_in)

        #: Then
        assert result.violations == (), (
            'a file metadata links in lands at that path once the skill is installed, so the link is not broken'
        )

    def test_validate_skill_links_with_metadata_unknown_judges_no_link_broken_but_still_reports_an_escape(
        self,
    ) -> None:
        #: Given
        # the frontmatter could not be read, so which files `metadata` links in is unknown
        links = (
            Link(url='references/gone.md', line=LineNumber(5)),
            Link(url='../out.md', line=LineNumber(6)),
        )
        targets = {PurePosixPath('references/gone.md'): LinkTargetState.MISSING}
        linked_in = None

        #: When
        result = validate_skill_links(links=links, anchors=frozenset(), targets=targets, linked_in=linked_in)

        #: Then
        assert [(violation.line, violation.rule) for violation in result.violations] == [
            (LineNumber(6), 'skill.link-escapes'),
        ], 'with metadata unknown any path might be linked in, so only the rules that need no metadata report'

    def test_validate_skill_links_with_a_link_breaking_each_rule_reports_each_link_once_in_the_order_given(
        self,
    ) -> None:
        #: Given
        links = (
            Link(url='gone.md', line=LineNumber(5)),
            Link(url='/a.md', line=LineNumber(6)),
            Link(url='#setup', line=LineNumber(7)),
            Link(url='../b.md', line=LineNumber(8)),
            Link(url='references/guide.md', line=LineNumber(9)),
        )
        targets = {
            PurePosixPath('gone.md'): LinkTargetState.MISSING,
            PurePosixPath('references/guide.md'): LinkTargetState.PRESENT,
        }

        #: When
        result = validate_skill_links(links=links, anchors=frozenset(), targets=targets, linked_in=frozenset())

        #: Then
        assert [(violation.line, violation.rule) for violation in result.violations] == [
            (LineNumber(5), 'skill.link-broken'),
            (LineNumber(6), 'skill.link-absolute'),
            (LineNumber(7), 'skill.link-fragment'),
            (LineNumber(8), 'skill.link-escapes'),
        ], 'each link breaks one rule at most, so the violations follow the links, and the present one has none'


@pytest.mark.unit
class TestValidateSkillResourceLinks:
    def test_validate_skill_resource_links_with_a_link_inside_the_skill_returns_no_violations(self) -> None:
        #: Given
        links = (Link(url='references/guide.md', line=LineNumber(3)),)
        targets = {PurePosixPath('references/guide.md'): LinkTargetState.PRESENT}

        #: When
        result = validate_skill_resource_links(links=links, targets=targets, linked_in=frozenset())

        #: Then
        assert result.violations == (), 'a link read from the skill root into the skill stays inside it'

    def test_validate_skill_resource_links_with_a_parent_link_reports_it_escaping_on_its_line(self) -> None:
        #: Given
        links = (Link(url='../SKILL.md', line=LineNumber(4)),)

        #: When
        result = validate_skill_resource_links(links=links, targets={}, linked_in=frozenset())

        #: Then
        assert result.violations == (
            Violation(
                line=LineNumber(4),
                rule='skill.link-escapes',
                message='`../SKILL.md` leaves the skill directory',
                notes=_ESCAPE_HELP,
            ),
        ), 'read from the skill root, not from the resource, `..` climbs out of the skill'

    def test_validate_skill_resource_links_with_a_link_climbing_above_the_root_reports_it_escaping(self) -> None:
        #: Given
        links = (Link(url='../../../../../outside.md', line=LineNumber(2)),)

        #: When
        result = validate_skill_resource_links(links=links, targets={}, linked_in=frozenset())

        #: Then
        assert result.violations == (
            Violation(
                line=LineNumber(2),
                rule='skill.link-escapes',
                message='`../../../../../outside.md` leaves the skill directory',
                notes=_ESCAPE_HELP,
            ),
        ), 'a link climbing past the repository root lies outside the skill too'

    def test_validate_skill_resource_links_with_a_parent_inside_the_skill_returns_no_violations(self) -> None:
        #: Given
        links = (Link(url='references/../SKILL.md', line=LineNumber(3)),)
        targets = {PurePosixPath('SKILL.md'): LinkTargetState.PRESENT}

        #: When
        result = validate_skill_resource_links(links=links, targets=targets, linked_in=frozenset())

        #: Then
        assert result.violations == (), 'a `..` that stays below the skill root normalises to a path inside it'

    def test_validate_skill_resource_links_with_a_link_climbing_back_in_by_the_skill_name_reports_it_escaping(
        self,
    ) -> None:
        #: Given
        links = (Link(url='../review/references/a.md', line=LineNumber(3)),)

        #: When
        result = validate_skill_resource_links(links=links, targets={}, linked_in=frozenset())

        #: Then
        assert result.violations == (
            Violation(
                line=LineNumber(3),
                rule='skill.link-escapes',
                message='`../review/references/a.md` leaves the skill directory',
                notes=_ESCAPE_HELP,
            ),
        ), 'the path alone decides: it climbs above the skill root, whatever directory the skill is installed as'

    def test_validate_skill_resource_links_with_a_link_climbing_back_in_by_the_repository_path_reports_it_escaping(
        self,
    ) -> None:
        #: Given
        links = (Link(url='../../skills/review/SKILL.md', line=LineNumber(3)),)

        #: When
        result = validate_skill_resource_links(links=links, targets={}, linked_in=frozenset())

        #: Then
        assert result.violations == (
            Violation(
                line=LineNumber(3),
                rule='skill.link-escapes',
                message='`../../skills/review/SKILL.md` leaves the skill directory',
                notes=_ESCAPE_HELP,
            ),
        ), 'a link naming the skill by the repository path breaks once the skill is installed elsewhere'

    def test_validate_skill_resource_links_with_a_dot_link_returns_no_violations(self) -> None:
        #: Given
        links = (Link(url='./SKILL.md', line=LineNumber(3)),)
        targets = {PurePosixPath('SKILL.md'): LinkTargetState.PRESENT}

        #: When
        result = validate_skill_resource_links(links=links, targets=targets, linked_in=frozenset())

        #: Then
        assert result.violations == (), 'a `.` component names the skill root itself'

    def test_validate_skill_resource_links_with_a_fragment_after_an_inside_path_returns_no_violations(self) -> None:
        #: Given
        links = (Link(url='SKILL.md#/../../outside', line=LineNumber(3)),)
        targets = {PurePosixPath('SKILL.md'): LinkTargetState.PRESENT}

        #: When
        result = validate_skill_resource_links(links=links, targets=targets, linked_in=frozenset())

        #: Then
        assert result.violations == (), 'the fragment after the path is not part of the path'

    def test_validate_skill_resource_links_with_a_query_after_an_inside_path_returns_no_violations(self) -> None:
        #: Given
        links = (Link(url='SKILL.md?from=/../../outside', line=LineNumber(3)),)
        targets = {PurePosixPath('SKILL.md'): LinkTargetState.PRESENT}

        #: When
        result = validate_skill_resource_links(links=links, targets=targets, linked_in=frozenset())

        #: Then
        assert result.violations == (), 'the query after the path is not part of the path'

    def test_validate_skill_resource_links_with_a_fragment_after_an_escaping_path_shows_the_whole_link(self) -> None:
        #: Given
        links = (Link(url='../../docs/guide.md#usage', line=LineNumber(5)),)

        #: When
        result = validate_skill_resource_links(links=links, targets={}, linked_in=frozenset())

        #: Then
        assert result.violations == (
            Violation(
                line=LineNumber(5),
                rule='skill.link-escapes',
                message='`../../docs/guide.md#usage` leaves the skill directory',
                notes=_ESCAPE_HELP,
            ),
        ), 'the path decides the rule, and the message shows the link as written, fragment included'

    def test_validate_skill_resource_links_with_a_url_scheme_returns_no_violations(self) -> None:
        #: Given
        links = (
            Link(url='https://agentskills.io/../specification', line=LineNumber(3)),
            Link(url='mailto:team@example.com', line=LineNumber(4)),
        )

        #: When
        result = validate_skill_resource_links(links=links, targets={}, linked_in=frozenset())

        #: Then
        assert result.violations == (), 'a URL with a scheme names no path in the skill, so it cannot leave it'

    def test_validate_skill_resource_links_with_an_absolute_link_returns_no_violations(self) -> None:
        #: Given
        links = (Link(url='/../outside.md', line=LineNumber(3)),)

        #: When
        result = validate_skill_resource_links(links=links, targets={}, linked_in=frozenset())

        #: Then
        assert result.violations == (), 'a link from the filesystem root is the absolute rule, not this one'

    def test_validate_skill_resource_links_with_a_fragment_only_link_returns_no_violations(self) -> None:
        #: Given
        links = (Link(url='#..', line=LineNumber(3)),)

        #: When
        result = validate_skill_resource_links(links=links, targets={}, linked_in=frozenset())

        #: Then
        assert result.violations == (), 'a fragment-only link stays in the file it is written in'

    def test_validate_skill_resource_links_with_percent_encoded_dots_reports_it_decoded(self) -> None:
        #: Given
        links = (Link(url='%2E%2E/a%20b.md', line=LineNumber(3)),)

        #: When
        result = validate_skill_resource_links(links=links, targets={}, linked_in=frozenset())

        #: Then
        assert result.violations == (
            Violation(
                line=LineNumber(3),
                rule='skill.link-escapes',
                message='`../a b.md` leaves the skill directory',
                notes=_ESCAPE_HELP,
            ),
        ), 'the path is percent-decoded before it is joined, and the message shows it as it was written'

    def test_validate_skill_resource_links_with_an_encoded_name_inside_returns_no_violations(self) -> None:
        #: Given
        links = (Link(url='references/a%20b.md', line=LineNumber(3)),)
        targets = {PurePosixPath('references/a b.md'): LinkTargetState.PRESENT}

        #: When
        result = validate_skill_resource_links(links=links, targets=targets, linked_in=frozenset())

        #: Then
        assert result.violations == (), 'an encoded name inside the skill decodes to a name inside it'

    def test_validate_skill_resource_links_with_an_escaping_image_reports_it(self) -> None:
        #: Given
        # an image's source arrives as a link like any other
        links = (Link(url='../../assets/flow.png', line=LineNumber(6)),)

        #: When
        result = validate_skill_resource_links(links=links, targets={}, linked_in=frozenset())

        #: Then
        assert result.violations == (
            Violation(
                line=LineNumber(6),
                rule='skill.link-escapes',
                message='`../../assets/flow.png` leaves the skill directory',
                notes=_ESCAPE_HELP,
            ),
        ), 'an image source outside the skill is a file the skill does not carry'

    def test_validate_skill_resource_links_with_several_escaping_links_reports_each_in_the_order_given(
        self,
    ) -> None:
        #: Given
        links = (
            Link(url='../a.md', line=LineNumber(2)),
            Link(url='SKILL.md', line=LineNumber(3)),
            Link(url='../b.md', line=LineNumber(7)),
        )
        targets = {PurePosixPath('SKILL.md'): LinkTargetState.PRESENT}

        #: When
        result = validate_skill_resource_links(links=links, targets=targets, linked_in=frozenset())

        #: Then
        assert result.violations == (
            Violation(
                line=LineNumber(2),
                rule='skill.link-escapes',
                message='`../a.md` leaves the skill directory',
                notes=_ESCAPE_HELP,
            ),
            Violation(
                line=LineNumber(7),
                rule='skill.link-escapes',
                message='`../b.md` leaves the skill directory',
                notes=_ESCAPE_HELP,
            ),
        ), 'every escaping link is its own violation, in document order, and the one inside is not'

    def test_validate_skill_resource_links_with_a_link_to_a_missing_file_reports_it_broken_on_its_line(self) -> None:
        #: Given
        links = (Link(url='references/gone.md', line=LineNumber(4)),)
        targets = {PurePosixPath('references/gone.md'): LinkTargetState.MISSING}

        #: When
        result = validate_skill_resource_links(links=links, targets=targets, linked_in=frozenset())

        #: Then
        assert result.violations == (
            Violation(
                line=LineNumber(4),
                rule='skill.link-broken',
                message='`references/gone.md` names nothing in the skill',
                notes=_BROKEN_HELP,
            ),
        ), 'a link in a resource is read from the skill root, and names nothing the snapshot holds there'

    def test_validate_skill_resource_links_with_a_link_to_a_directory_the_skill_holds_returns_no_violations(
        self,
    ) -> None:
        #: Given
        links = (Link(url='scripts', line=LineNumber(3)),)
        targets = {PurePosixPath('scripts'): LinkTargetState.PRESENT}

        #: When
        result = validate_skill_resource_links(links=links, targets=targets, linked_in=frozenset())

        #: Then
        assert result.violations == (), 'a directory the skill holds is something a link may name'

    def test_validate_skill_resource_links_with_a_missing_file_metadata_links_in_returns_no_violations(self) -> None:
        #: Given
        links = (Link(url='references/logging.md', line=LineNumber(3)),)
        targets = {PurePosixPath('references/logging.md'): LinkTargetState.MISSING}
        linked_in = frozenset({PurePosixPath('references/logging.md')})

        #: When
        result = validate_skill_resource_links(links=links, targets=targets, linked_in=linked_in)

        #: Then
        assert result.violations == (), (
            'a listed file that is missing is the metadata rule to report, so the link to it is not reported again'
        )

    def test_validate_skill_resource_links_with_a_fragment_after_a_missing_path_reports_the_whole_link(self) -> None:
        #: Given
        links = (Link(url='references/gone.md#usage', line=LineNumber(5)),)
        targets = {PurePosixPath('references/gone.md'): LinkTargetState.MISSING}

        #: When
        result = validate_skill_resource_links(links=links, targets=targets, linked_in=frozenset())

        #: Then
        assert result.violations == (
            Violation(
                line=LineNumber(5),
                rule='skill.link-broken',
                message='`references/gone.md#usage` names nothing in the skill',
                notes=_BROKEN_HELP,
            ),
        ), 'the path before the fragment decides the rule, and the message shows the link as written'

    def test_validate_skill_resource_links_with_a_query_after_a_present_path_returns_no_violations(self) -> None:
        #: Given
        links = (Link(url='SKILL.md?plain=1', line=LineNumber(3)),)
        targets = {PurePosixPath('SKILL.md'): LinkTargetState.PRESENT}

        #: When
        result = validate_skill_resource_links(links=links, targets=targets, linked_in=frozenset())

        #: Then
        assert result.violations == (), 'the query after the path is not part of the path the snapshot holds'

    def test_validate_skill_resource_links_with_an_escaping_link_reports_it_escaping_and_not_broken(self) -> None:
        #: Given
        # the run looks up no path above the skill root, so it has no target
        links = (Link(url='../gone.md', line=LineNumber(3)),)
        targets: dict[PurePosixPath, LinkTargetState] = {}

        #: When
        result = validate_skill_resource_links(links=links, targets=targets, linked_in=frozenset())

        #: Then
        assert [violation.rule for violation in result.violations] == ['skill.link-escapes'], (
            'a link leaving the skill is the escape rule alone, whatever lies where it leads'
        )

    def test_validate_skill_resource_links_with_a_percent_encoded_missing_name_reports_it_decoded(self) -> None:
        #: Given
        links = (Link(url='references/a%20b.md', line=LineNumber(3)),)
        targets = {PurePosixPath('references/a b.md'): LinkTargetState.MISSING}

        #: When
        result = validate_skill_resource_links(links=links, targets=targets, linked_in=frozenset())

        #: Then
        assert result.violations == (
            Violation(
                line=LineNumber(3),
                rule='skill.link-broken',
                message='`references/a b.md` names nothing in the skill',
                notes=_BROKEN_HELP,
            ),
        ), 'the path is looked up decoded, and the message shows it as it was written'

    def test_validate_skill_resource_links_with_a_missing_image_reports_it_broken(self) -> None:
        #: Given
        # an image's source arrives as a link like any other
        links = (Link(url='assets/flow.png', line=LineNumber(6)),)
        targets = {PurePosixPath('assets/flow.png'): LinkTargetState.MISSING}

        #: When
        result = validate_skill_resource_links(links=links, targets=targets, linked_in=frozenset())

        #: Then
        assert [violation.rule for violation in result.violations] == ['skill.link-broken'], (
            'an image source naming nothing in the skill is broken like a link'
        )

    def test_validate_skill_resource_links_with_broken_and_escaping_links_reports_each_in_the_order_given(
        self,
    ) -> None:
        #: Given
        links = (
            Link(url='b.md', line=LineNumber(2)),
            Link(url='SKILL.md', line=LineNumber(3)),
            Link(url='../c.md', line=LineNumber(4)),
            Link(url='a.md', line=LineNumber(7)),
        )
        targets = {
            PurePosixPath('a.md'): LinkTargetState.MISSING,
            PurePosixPath('b.md'): LinkTargetState.MISSING,
            PurePosixPath('SKILL.md'): LinkTargetState.PRESENT,
        }

        #: When
        result = validate_skill_resource_links(links=links, targets=targets, linked_in=frozenset())

        #: Then
        assert [(violation.line, violation.rule) for violation in result.violations] == [
            (LineNumber(2), 'skill.link-broken'),
            (LineNumber(4), 'skill.link-escapes'),
            (LineNumber(7), 'skill.link-broken'),
        ], 'the violations follow the links, whatever order their paths sort in, and the present one has none'


@pytest.mark.unit
class TestLinkPathInSkill:
    def test_link_path_in_skill_with_an_encoded_dotted_path_returns_it_decoded_and_normalised(self) -> None:
        #: Given
        link = Link(url='references/./a%20b.md#usage', line=LineNumber(3))

        #: When
        path = link_path_in_skill(link)

        #: Then
        assert path == PurePosixPath('references/a b.md'), 'the path is decoded, normalised, and has no fragment'

    def test_link_path_in_skill_with_a_parent_that_stays_inside_returns_the_skill_root(self) -> None:
        #: Given
        link = Link(url='references/..', line=LineNumber(3))

        #: When
        path = link_path_in_skill(link)

        #: Then
        assert path == PurePosixPath('.'), 'a `..` below the skill root cancels the component before it'

    def test_link_path_in_skill_with_an_escaping_link_returns_none(self) -> None:
        #: Given
        link = Link(url='references/../../outside.md', line=LineNumber(3))

        #: When
        path = link_path_in_skill(link)

        #: Then
        assert path is None, 'a link climbing above the skill root names nothing inside it'

    def test_link_path_in_skill_with_a_url_returns_none(self) -> None:
        #: Given
        link = Link(url='https://agentskills.io/specification', line=LineNumber(3))

        #: When
        path = link_path_in_skill(link)

        #: Then
        assert path is None, 'a URL with a scheme spells no path in the skill'
