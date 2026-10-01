"""Link validation over the links of a ``SKILL.md``'s parse tree.

``validate_skill_links`` is pure, so every case here is a tuple of links built in memory; no ``SKILL.md`` is read or
parsed.
"""

import pytest

from lorecraft.project.syntax import LineNumber, Link

from ..reporting import Violation
from ..skill_link import validate_skill_links


@pytest.mark.unit
class TestValidateSkillLinks:
    def test_validate_skill_links_with_an_absolute_link_reports_it_on_its_line(self) -> None:
        #: Given
        links = (Link(url='/docs/guide.md', line=LineNumber(7)),)

        #: When
        result = validate_skill_links(links=links)

        #: Then
        assert result.violations == (
            Violation(
                line=LineNumber(7),
                rule='skill.link-absolute',
                message='`/docs/guide.md` is absolute; link relative to the skill root',
            ),
        ), 'a link from the filesystem root is one violation, on the line the link is on'

    def test_validate_skill_links_with_a_relative_link_returns_no_violations(self) -> None:
        #: Given
        links = (Link(url='references/guide.md', line=LineNumber(3)),)

        #: When
        result = validate_skill_links(links=links)

        #: Then
        assert result.violations == (), 'a link relative to the skill root is what the rule asks for'

    def test_validate_skill_links_with_a_parent_relative_link_returns_no_violations(self) -> None:
        #: Given
        links = (Link(url='../../docs/guide.md', line=LineNumber(3)),)

        #: When
        result = validate_skill_links(links=links)

        #: Then
        assert result.violations == (), 'a link climbing out of the skill is relative, so it is not this rule'

    def test_validate_skill_links_with_a_url_scheme_returns_no_violations(self) -> None:
        #: Given
        links = (
            Link(url='https://agentskills.io/specification', line=LineNumber(3)),
            Link(url='mailto:team@example.com', line=LineNumber(4)),
        )

        #: When
        result = validate_skill_links(links=links)

        #: Then
        assert result.violations == (), 'a URL with a scheme points outside the skill, not at a path'

    def test_validate_skill_links_with_a_fragment_only_link_returns_no_violations(self) -> None:
        #: Given
        links = (Link(url='#checklist', line=LineNumber(3)),)

        #: When
        result = validate_skill_links(links=links)

        #: Then
        assert result.violations == (), 'a fragment-only link stays in the SKILL.md'

    def test_validate_skill_links_with_several_absolute_links_reports_each_in_the_order_given(self) -> None:
        #: Given
        links = (
            Link(url='/a.md', line=LineNumber(5)),
            Link(url='b.md', line=LineNumber(6)),
            Link(url='/c.png', line=LineNumber(9)),
        )

        #: When
        result = validate_skill_links(links=links)

        #: Then
        assert [(violation.line, violation.message) for violation in result.violations] == [
            (LineNumber(5), '`/a.md` is absolute; link relative to the skill root'),
            (LineNumber(9), '`/c.png` is absolute; link relative to the skill root'),
        ], 'every absolute link is its own violation, in document order, and the relative one between them is not'
