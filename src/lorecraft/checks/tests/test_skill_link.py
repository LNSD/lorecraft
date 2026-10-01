"""Link validation over the links and the heading anchors of a ``SKILL.md``'s parse tree.

``validate_skill_links`` is pure, so every case here is a tuple of links and a set of ``Anchor`` values built in
memory; no ``SKILL.md`` is read or parsed.
"""

import pytest

from lorecraft.project.syntax import Anchor, LineNumber, Link

from ..reporting import Violation
from ..skill_link import validate_skill_links


@pytest.mark.unit
class TestValidateSkillLinks:
    def test_validate_skill_links_with_an_absolute_link_reports_it_on_its_line(self) -> None:
        #: Given
        links = (Link(url='/docs/guide.md', line=LineNumber(7)),)

        #: When
        result = validate_skill_links(links=links, anchors=frozenset())

        #: Then
        assert result.violations == (
            Violation(
                line=LineNumber(7),
                rule='skill.link-absolute',
                message='`/docs/guide.md` is absolute; link relative to the skill root',
            ),
        ), 'a link from the filesystem root is one violation, on the line the link is on'

    def test_validate_skill_links_with_an_encoded_absolute_link_shows_it_decoded(self) -> None:
        #: Given
        links = (Link(url='/a%20b', line=LineNumber(3)),)

        #: When
        result = validate_skill_links(links=links, anchors=frozenset())

        #: Then
        assert result.violations == (
            Violation(
                line=LineNumber(3),
                rule='skill.link-absolute',
                message='`/a b` is absolute; link relative to the skill root',
            ),
        ), 'the message shows the destination as it was written, not as the parser percent-encoded it'

    def test_validate_skill_links_with_a_relative_link_returns_no_violations(self) -> None:
        #: Given
        links = (Link(url='references/guide.md', line=LineNumber(3)),)

        #: When
        result = validate_skill_links(links=links, anchors=frozenset())

        #: Then
        assert result.violations == (), 'a link relative to the skill root is what the rule asks for'

    def test_validate_skill_links_with_a_parent_relative_link_returns_no_violations(self) -> None:
        #: Given
        links = (Link(url='../../docs/guide.md', line=LineNumber(3)),)

        #: When
        result = validate_skill_links(links=links, anchors=frozenset())

        #: Then
        assert result.violations == (), 'a link climbing out of the skill is relative, so it is not this rule'

    def test_validate_skill_links_with_a_url_scheme_returns_no_violations(self) -> None:
        #: Given
        links = (
            Link(url='https://agentskills.io/specification', line=LineNumber(3)),
            Link(url='mailto:team@example.com', line=LineNumber(4)),
        )

        #: When
        result = validate_skill_links(links=links, anchors=frozenset())

        #: Then
        assert result.violations == (), 'a URL with a scheme points outside the skill, not at a path'

    def test_validate_skill_links_with_a_fragment_naming_a_heading_returns_no_violations(self) -> None:
        #: Given
        links = (Link(url='#checklist', line=LineNumber(3)),)
        anchors = frozenset({Anchor('overview'), Anchor('checklist')})

        #: When
        result = validate_skill_links(links=links, anchors=anchors)

        #: Then
        assert result.violations == (), 'a fragment naming a heading of the SKILL.md points at something it holds'

    def test_validate_skill_links_with_a_fragment_naming_no_heading_reports_it_on_its_line(self) -> None:
        #: Given
        links = (Link(url='#usage', line=LineNumber(4)),)
        anchors = frozenset({Anchor('overview'), Anchor('checklist')})

        #: When
        result = validate_skill_links(links=links, anchors=anchors)

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
        result = validate_skill_links(links=links, anchors=anchors)

        #: Then
        assert result.violations == (), 'the fragment is percent-decoded before it is looked up among the anchors'

    def test_validate_skill_links_with_an_uppercase_fragment_matches_the_lowercase_heading_anchor(self) -> None:
        #: Given
        links = (Link(url='#Usage', line=LineNumber(3)),)
        anchors = frozenset({Anchor('usage')})

        #: When
        result = validate_skill_links(links=links, anchors=anchors)

        #: Then
        assert result.violations == (), 'GitHub resolves a fragment regardless of case, so the check does too'

    def test_validate_skill_links_with_a_dangling_non_ascii_fragment_shows_it_decoded(self) -> None:
        #: Given
        links = (Link(url='#Stra%C3%9Fe', line=LineNumber(3)),)
        anchors = frozenset({Anchor('usage')})

        #: When
        result = validate_skill_links(links=links, anchors=anchors)

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
        result = validate_skill_links(links=links, anchors=anchors)

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
        result = validate_skill_links(links=links, anchors=frozenset())

        #: Then
        assert result.violations == (), 'an empty fragment names no heading, so there is none to miss'

    def test_validate_skill_links_with_a_fragment_into_another_file_returns_no_violations(self) -> None:
        #: Given
        links = (Link(url='references/guide.md#usage', line=LineNumber(3)),)

        #: When
        result = validate_skill_links(links=links, anchors=frozenset())

        #: Then
        assert result.violations == (), 'a fragment into another file is not checked against the SKILL.md headings'

    def test_validate_skill_links_with_a_fragment_after_the_skill_md_path_returns_no_violations(self) -> None:
        #: Given
        links = (Link(url='SKILL.md#usage', line=LineNumber(4)),)

        #: When
        result = validate_skill_links(links=links, anchors=frozenset())

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
        result = validate_skill_links(links=links, anchors=anchors)

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
                message='`/a.md` is absolute; link relative to the skill root',
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

        #: When
        result = validate_skill_links(links=links, anchors=frozenset())

        #: Then
        assert [(violation.line, violation.message) for violation in result.violations] == [
            (LineNumber(5), '`/a.md` is absolute; link relative to the skill root'),
            (LineNumber(9), '`/c.png` is absolute; link relative to the skill root'),
        ], 'every absolute link is its own violation, in document order, and the relative one between them is not'
