"""The rulebook's rendering: a docstring split into its sections, a rule's page by kind, and the listing."""

import pytest

from lorecraft import rules
from lorecraft.rules.engine.invalid_utf8 import InvalidUtf8
from lorecraft.rules.frontmatter.missing_field import MissingField
from lorecraft.rules.outline.empty_section import EmptySection
from lorecraft.rules.outline.missing_title import MissingTitle
from lorecraft.rules.registry import Registry
from lorecraft.rules.tests.sample_rules import valid as valid_rules
from lorecraft.rules.tests.sample_rules.valid.retired import TabIndent
from lorecraft.rules.tests.sample_rules.valid.trailing_space import TrailingSpace

from ..rulebook import _DocSection, _parse_docstring, _RuleDoc, page_name, render_listing, render_page


@pytest.fixture(scope='module')
def package_registry() -> Registry:
    """The registry of the package's own rules; immutable, so shared by the module."""
    return Registry.load(rules)


@pytest.fixture(scope='module')
def sample_registry() -> Registry:
    """The registry of the sample rules, which hold an alias code and a removed rule; immutable, so shared."""
    return Registry.load(valid_rules)


@pytest.mark.unit
class TestParseDocstring:
    def test_parse_docstring_with_two_sections_returns_the_summary_and_each_section_in_order(self) -> None:
        #: Given
        docstring = """A line is long.

        ## What it does

        Checks for long lines.

        ## Why is this bad?

        A long line is hard to read.
        """

        #: When
        doc = _parse_docstring(docstring)

        #: Then
        assert doc == _RuleDoc(
            'A line is long.',
            (
                _DocSection('What it does', 'Checks for long lines.'),
                _DocSection('Why is this bad?', 'A long line is hard to read.'),
            ),
        ), 'the summary is the first paragraph, and each section keeps its heading and its text, in the order written'

    def test_parse_docstring_with_a_wrapped_summary_joins_its_lines(self) -> None:
        #: Given
        docstring = 'A section holds no content, under a\n    specification that forbids it.\n'

        #: When
        doc = _parse_docstring(docstring)

        #: Then
        assert doc == _RuleDoc('A section holds no content, under a specification that forbids it.', ()), (
            'the summary reads as one line'
        )

    def test_parse_docstring_with_a_heading_inside_a_fence_keeps_it_in_the_section(self) -> None:
        #: Given
        docstring = """A section is empty.

        ## Example

        ```markdown
        ## Install
        ```
        """

        #: When
        doc = _parse_docstring(docstring)

        #: Then
        assert doc == _RuleDoc('A section is empty.', (_DocSection('Example', '```markdown\n## Install\n```'),)), (
            'a heading in an example is text of the example, not a section'
        )

    def test_parse_docstring_with_an_attributes_block_leaves_it_out(self) -> None:
        #: Given
        docstring = """A line is long.

        ## Use instead

        Shorten it.

        Attributes:
            limit: The longest line allowed.
        """

        #: When
        doc = _parse_docstring(docstring)

        #: Then
        assert doc == _RuleDoc('A line is long.', (_DocSection('Use instead', 'Shorten it.'),)), (
            'the fields are for the maintainer, so the last section ends where they start'
        )

    def test_parse_docstring_with_no_docstring_returns_an_empty_summary_and_no_section(self) -> None:
        #: Given
        docstring = None

        #: When
        doc = _parse_docstring(docstring)

        #: Then
        assert doc == _RuleDoc('', ()), 'there is no summary and no section to render'


@pytest.mark.unit
class TestPageName:
    def test_page_name_with_a_rule_returns_its_code_then_its_name(self) -> None:
        #: Given
        declaration = EmptySection

        #: When
        name = page_name(declaration)

        #: Then
        assert name == 'OUT004-empty-section', 'the code comes first so the listing sorts in code order'


@pytest.mark.unit
class TestRenderPage:
    def test_render_page_with_a_rule_returns_its_frontmatter_title_facts_and_sections(
        self, package_registry: Registry
    ) -> None:
        #: Given
        declaration = EmptySection

        #: When
        page = render_page(declaration, package_registry)

        #: Then
        assert page.startswith(
            '---\n'
            'name: "OUT004-empty-section"\n'
            'description: "A section holds no content, under a structure specification that forbids empty sections"\n'
            '---\n\n'
            '# empty-section (OUT004)\n\n'
            'A section holds no content, under a structure specification that forbids empty sections.\n\n'
            '- **Code:** `OUT004`\n'
            '- **Group:** `OUT`, Outline checks\n'
            '- **Default level:** `deny`\n'
            '- **Stable since:** `0.3.0`\n'
        ), 'the page opens with its frontmatter, its title, its summary and what the class declares'
        assert '\n## What it does\n\nChecks for headings whose section holds nothing' in page, (
            'the docstring sections follow, each under its heading'
        )
        assert page.endswith('\n'), 'the file ends with one newline'

    def test_render_page_with_a_rule_leaves_the_attributes_block_out(self, package_registry: Registry) -> None:
        #: Given
        declaration = EmptySection

        #: When
        page = render_page(declaration, package_registry)

        #: Then
        assert 'Attributes:' not in page, 'the fields are documented for the maintainer, not on the page'

    def test_render_page_with_a_rule_links_the_module_that_declares_it(self, package_registry: Registry) -> None:
        #: Given
        declaration = EmptySection

        #: When
        page = render_page(declaration, package_registry)

        #: Then
        assert (
            '- **Declared in:** [`src/lorecraft/rules/outline/empty_section.py`]'
            '(https://github.com/LNSD/lorecraft/blob/main/src/lorecraft/rules/outline/empty_section.py)'
        ) in page, 'the link is the published source, which a reader without the repository can open'

    def test_render_page_with_a_rule_every_occurrence_of_which_names_a_specification_says_one_states_it(
        self, package_registry: Registry
    ) -> None:
        #: Given
        declaration = EmptySection

        #: When
        page = render_page(declaration, package_registry)

        #: Then
        assert '- **Origin:** a specification of the repository states it, and the diagnostic points' in page, (
            'a rule whose spec is always a file is stated by a specification'
        )

    def test_render_page_with_a_rule_the_package_states_says_lorecraft_states_it(
        self, package_registry: Registry
    ) -> None:
        #: Given
        declaration = MissingTitle

        #: When
        page = render_page(declaration, package_registry)

        #: Then
        assert '- **Origin:** Lorecraft states it, as no specification of the repository does' in page, (
            'a rule whose spec is always None is stated by the package'
        )

    def test_render_page_with_a_rule_over_a_document_and_a_skill_says_a_specification_or_lorecraft_states_it(
        self, package_registry: Registry
    ) -> None:
        #: Given
        declaration = MissingField

        #: When
        page = render_page(declaration, package_registry)

        #: Then
        assert '- **Origin:** a specification of the repository states it, or Lorecraft does where none does' in page, (
            'a rule whose spec is a file or None is stated by either'
        )

    def test_render_page_with_an_alias_code_lists_it_with_its_linter(self, sample_registry: Registry) -> None:
        #: Given
        declaration = TrailingSpace

        #: When
        page = render_page(declaration, sample_registry)

        #: Then
        assert '- **Aliases:** `MD009` of markdownlint\n' in page, 'the alias code points at the rule, with its linter'

    def test_render_page_with_a_rule_without_an_alias_code_lists_none(self, package_registry: Registry) -> None:
        #: Given
        declaration = EmptySection

        #: When
        page = render_page(declaration, package_registry)

        #: Then
        assert 'Aliases' not in page, 'a rule absorbed from no linter lists no alias'

    def test_render_page_with_a_removed_rule_gives_its_release_and_links_its_replacement(
        self, sample_registry: Registry
    ) -> None:
        #: Given
        declaration = TabIndent

        #: When
        page = render_page(declaration, sample_registry)

        #: Then
        assert '- **Removed in:** `1.3.0`\n' in page, 'the page states the release that removed the rule'
        assert '- **Replaced by:** [`SMP002`](SMP002-trailing-space.md)\n' in page, (
            'the page links the page of the rule that replaced it'
        )
        assert 'Default level' not in page, 'a removed rule has no level'

    def test_render_page_with_an_engine_condition_gives_its_severity_and_no_level(
        self, package_registry: Registry
    ) -> None:
        #: Given
        declaration = InvalidUtf8

        #: When
        page = render_page(declaration, package_registry)

        #: Then
        assert '- **Severity:** `error`, always: it has no level\n' in page, (
            'the page states the severity every occurrence is reported at'
        )
        assert 'Default level' not in page, 'an engine condition has no level'


@pytest.mark.unit
class TestRenderListing:
    def test_render_listing_with_the_sample_rules_returns_a_line_per_rule_in_code_order(
        self, sample_registry: Registry
    ) -> None:
        #: Given
        registry = sample_registry

        #: When
        listing = render_listing(registry)

        #: Then
        assert listing.splitlines() == [
            "LAYS001  uppercase-entry  deny     A layout entry's name holds an uppercase letter.",
            'SMP001   empty-line       allow    A line is empty.',
            'SMP002   trailing-space   warn     A line ends in a space.',
            'SMP003   tab-indent       removed  A line was indented with a tab; retired for `trailing-space`, '
            'which the samples needed more.',
        ], 'each rule has its code, name, level and condition, a removed rule showing removed in place of a level'

    def test_render_listing_with_an_engine_condition_shows_its_severity_in_place_of_a_level(
        self, package_registry: Registry
    ) -> None:
        #: Given
        registry = package_registry

        #: When
        listing = render_listing(registry)

        #: Then
        assert any(line.startswith('LC001') and ' error ' in line for line in listing.splitlines()), (
            'the engine condition is listed at the severity it is always reported at'
        )
