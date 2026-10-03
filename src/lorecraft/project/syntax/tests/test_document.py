"""Parsing a document's text into its parse tree.

Where the frontmatter block is found, which headings count, how many prose words each section holds, which anchors
its headings give, and which links the document holds.

``parse_document`` and ``parse_frontmatter`` are pure, so every case here is a text literal. The Markdown parser
behind them decides what counts as a block; these pin the rules the checks report against.
"""

from textwrap import dedent

import pytest

from ..anchor import Anchor
from ..document import parse_document, parse_frontmatter
from ..frontmatter import Frontmatter, FrontmatterKey, InvalidYamlFrontmatter, MissingFrontmatter
from ..heading import Heading
from ..link import Link
from ..position import LineNumber


@pytest.mark.unit
class TestParseDocument:
    def test_parse_document_with_an_invalid_yaml_block_skips_it_as_frontmatter(self) -> None:
        #: Given
        text = dedent(
            """\
            ---
            name: [unclosed
            # Draft
            ---
            # Guide
            """
        )

        #: When
        document = parse_document(text)

        #: Then
        assert document.headings == (Heading(level=1, text='Guide', line=LineNumber(5), empty=True, words=0),), (
            'the block is skipped whether its YAML decodes or not, so a `#` line in it is no heading'
        )


@pytest.mark.unit
class TestParseFrontmatter:
    def test_parse_frontmatter_with_a_delimited_block_returns_its_frontmatter(self) -> None:
        #: Given
        text = '---\nname: guide\ntype: rule\n---\n# Guide\n'

        #: When
        frontmatter = parse_frontmatter(text)

        #: Then
        assert frontmatter == Frontmatter(
            data={'name': 'guide', 'type': 'rule'},
            keys=(FrontmatterKey('name', LineNumber(2)), FrontmatterKey('type', LineNumber(3))),
        ), 'the block between the delimiters is decoded, each key on its document line'

    def test_parse_frontmatter_with_trailing_whitespace_on_the_delimiters_returns_its_frontmatter(self) -> None:
        #: Given
        text = '---  \nname: guide\n--- \n'

        #: When
        frontmatter = parse_frontmatter(text)

        #: Then
        assert isinstance(frontmatter, Frontmatter), f'a delimiter may carry trailing whitespace, got {frontmatter!r}'

    def test_parse_frontmatter_with_crlf_line_endings_returns_each_key_on_its_document_line(self) -> None:
        #: Given
        text = '---\r\nname: guide\r\ntype: rule\r\n---\r\n# Guide\r\n'

        #: When
        frontmatter = parse_frontmatter(text)

        #: Then
        assert isinstance(frontmatter, Frontmatter), f'a CRLF block is found, got {frontmatter!r}'
        assert frontmatter.keys == (
            FrontmatterKey('name', LineNumber(2)),
            FrontmatterKey('type', LineNumber(3)),
        ), 'a CRLF line ending counts as one line break'

    def test_parse_frontmatter_with_invalid_yaml_returns_invalid_yaml_frontmatter(self) -> None:
        #: Given
        text = '---\nname: [unclosed\n---\n# Guide\n'

        #: When
        frontmatter = parse_frontmatter(text)

        #: Then
        assert isinstance(frontmatter, InvalidYamlFrontmatter), (
            f'a block that is not YAML is a value, not a failed parse, got {frontmatter!r}'
        )

    def test_parse_frontmatter_without_an_opening_delimiter_returns_missing(self) -> None:
        #: Given
        text = '# Guide\n\nname: guide\n'

        #: When
        frontmatter = parse_frontmatter(text)

        #: Then
        assert frontmatter == MissingFrontmatter(), 'a document not opening with `---` has no frontmatter'

    def test_parse_frontmatter_with_a_block_after_the_first_line_returns_missing(self) -> None:
        #: Given
        text = '\n---\nname: guide\n---\n'

        #: When
        frontmatter = parse_frontmatter(text)

        #: Then
        assert frontmatter == MissingFrontmatter(), 'the opening delimiter must be the first line'

    def test_parse_frontmatter_with_an_indented_opening_delimiter_returns_missing(self) -> None:
        #: Given
        text = '  ---\nname: guide\n---\n'

        #: When
        frontmatter = parse_frontmatter(text)

        #: Then
        assert frontmatter == MissingFrontmatter(), 'a delimiter allows no leading whitespace'

    def test_parse_frontmatter_without_a_closing_delimiter_returns_missing(self) -> None:
        #: Given
        text = '---\nname: guide\n'

        #: When
        frontmatter = parse_frontmatter(text)

        #: Then
        assert frontmatter == MissingFrontmatter(), 'an unclosed block is not frontmatter'


@pytest.mark.unit
class TestParseDocumentHeadings:
    def test_parse_document_with_headings_returns_each_with_its_level_text_and_line(self) -> None:
        #: Given
        text = '---\nname: guide\n---\n# Guide\n\nIntro.\n\n## Checklist\n\n- [ ] item\n'

        #: When
        document = parse_document(text)

        #: Then
        assert document.headings == (
            Heading(level=1, text='Guide', line=LineNumber(4), empty=False, words=5),
            Heading(level=2, text='Checklist', line=LineNumber(8), empty=False, words=4),
        ), 'each heading carries its level, its text, the document line it starts on and its prose words'

    def test_parse_document_with_inline_markup_in_a_heading_returns_its_plain_text(self) -> None:
        #: Given
        text = '## **Check** `list`\n\ntext\n'

        #: When
        document = parse_document(text)

        #: Then
        assert [heading.text for heading in document.headings] == ['Check list'], (
            'inline markup is stripped, so a spec can name the section by its words'
        )

    def test_parse_document_with_a_hash_line_in_a_fenced_block_returns_no_heading_for_it(self) -> None:
        #: Given
        text = '## Example\n\n```\n## not a heading\n```\n'

        #: When
        document = parse_document(text)

        #: Then
        assert [heading.text for heading in document.headings] == ['Example'], 'a `#` line in a code block is code'

    def test_parse_document_with_a_heading_in_a_blockquote_leaves_it_out(self) -> None:
        #: Given
        text = '## Example\n\n> ## Quoted\n'

        #: When
        document = parse_document(text)

        #: Then
        assert [heading.text for heading in document.headings] == ['Example'], (
            'a quoted heading illustrates a document, it does not section this one'
        )

    def test_parse_document_with_a_heading_in_a_list_item_leaves_it_out(self) -> None:
        #: Given
        text = '## Example\n\n- ## Nested\n'

        #: When
        document = parse_document(text)

        #: Then
        assert [heading.text for heading in document.headings] == ['Example'], (
            'a heading nested in a list item does not section the document'
        )

    def test_parse_document_with_a_heading_followed_by_a_sibling_marks_it_empty(self) -> None:
        #: Given
        text = '## Empty\n## Full\n\ntext\n'

        #: When
        document = parse_document(text)

        #: Then
        assert [heading.empty for heading in document.headings] == [True, False], (
            'a section closed straight away by a heading of its own level holds nothing'
        )

    def test_parse_document_with_a_heading_followed_by_a_subsection_marks_it_not_empty(self) -> None:
        #: Given
        text = '## Parent\n### Child\n\ntext\n'

        #: When
        document = parse_document(text)

        #: Then
        assert [heading.empty for heading in document.headings] == [False, False], (
            'a subsection is content of the section that holds it'
        )

    def test_parse_document_with_a_heading_on_the_last_line_marks_it_empty(self) -> None:
        #: Given
        text = '## Full\n\ntext\n\n## Last\n'

        #: When
        document = parse_document(text)

        #: Then
        assert document.headings[-1].empty, 'a heading closed by the end of the document holds nothing'

    def test_parse_document_with_crlf_line_endings_returns_each_heading_on_its_document_line(self) -> None:
        #: Given
        text = '# Guide\r\n\r\n## Checklist\r\n'

        #: When
        document = parse_document(text)

        #: Then
        assert [heading.line for heading in document.headings] == [LineNumber(1), LineNumber(3)], (
            'a CRLF line ending counts as one line break'
        )

    def test_parse_document_with_a_leading_blank_line_returns_the_heading_on_line_two(self) -> None:
        #: Given
        text = '\n# Guide\n'

        #: When
        document = parse_document(text)

        #: Then
        assert [heading.line for heading in document.headings] == [LineNumber(2)], (
            'the line break opening the document counts, so the heading after it is on line 2'
        )


@pytest.mark.unit
class TestParseDocumentWords:
    def test_parse_document_with_a_subsection_counts_its_prose_in_the_parent_section(self) -> None:
        #: Given
        text = '## Parent\n\none two\n\n### Child\n\nthree four five\n\n## Next\n\nsix\n'

        #: When
        document = parse_document(text)

        #: Then
        assert [heading.words for heading in document.headings] == [5, 3, 1], (
            'a section runs to the next heading of its level, so its subsections count, but no heading text does'
        )

    def test_parse_document_with_an_empty_section_counts_no_words_for_it(self) -> None:
        #: Given
        text = '## Empty\n## Full\n\none two\n'

        #: When
        document = parse_document(text)

        #: Then
        assert [heading.words for heading in document.headings] == [0, 2], 'a section holding nothing has no words'

    def test_parse_document_with_a_fenced_code_block_leaves_its_lines_out(self) -> None:
        #: Given
        text = '## Example\n\none two\n\n```python\nvalue = compute(a, b)\n```\n'

        #: When
        document = parse_document(text)

        #: Then
        assert document.headings[0].words == 2, 'a fenced code block is not prose'

    def test_parse_document_with_an_indented_code_block_leaves_its_lines_out(self) -> None:
        #: Given
        text = '## Example\n\none two\n\n    value = compute(a, b)\n'

        #: When
        document = parse_document(text)

        #: Then
        assert document.headings[0].words == 2, 'an indented code block is not prose'

    def test_parse_document_with_a_code_block_in_a_list_item_leaves_its_lines_out(self) -> None:
        #: Given
        text = '## Steps\n\n- run it:\n\n  ```bash\n  just check --statistics\n  ```\n\n  then read\n'

        #: When
        document = parse_document(text)

        #: Then
        assert document.headings[0].words == 5, (
            'a code block nested in a list item is not prose, and the item text around it is'
        )

    def test_parse_document_with_a_table_leaves_its_rows_out(self) -> None:
        #: Given
        text = '## Gates\n\none two\n\n| Gate | Recipe |\n|---|---|\n| Lint | just check |\n'

        #: When
        document = parse_document(text)

        #: Then
        assert document.headings[0].words == 2, 'a table row is a reference, not prose'

    def test_parse_document_with_prose_after_a_table_row_in_one_paragraph_counts_the_prose(self) -> None:
        #: Given
        # no blank line separates the row from the prose, so the parser reads both as one paragraph
        text = '## Gates\n\n| Gate | Recipe |\none two three\n'

        #: When
        document = parse_document(text)

        #: Then
        assert document.headings[0].words == 3, 'only the table row is left out; the prose after it still counts'

    def test_parse_document_with_two_code_blocks_in_a_list_item_counts_the_prose_before_each(self) -> None:
        #: Given
        # three words open the item before the first code block, and three more sit between the two blocks
        text = (
            '## Steps\n\n'
            '- first run:\n\n  ```bash\n  just fmt\n  ```\n\n'
            '  then check it:\n\n  ```bash\n  just check\n  ```\n'
        )

        #: When
        document = parse_document(text)

        #: Then
        assert document.headings[0].words == 6, 'the prose before every code block in the item counts, not the last'

    def test_parse_document_with_text_before_the_first_heading_leaves_it_out_of_the_section(self) -> None:
        #: Given
        text = 'one two three\n\n## Section\n\nfour\n'

        #: When
        document = parse_document(text)

        #: Then
        assert document.headings[0].words == 1, 'text before the first heading belongs to no section'

    def test_parse_document_with_frontmatter_leaves_it_out_of_the_title_section(self) -> None:
        #: Given
        text = '---\nname: guide\ndescription: many words in the frontmatter\n---\n# Guide\n\none two\n'

        #: When
        document = parse_document(text)

        #: Then
        assert document.headings[0].words == 2, 'the frontmatter and the heading text are not section prose'


@pytest.mark.unit
class TestParseDocumentLinks:
    def test_parse_document_with_an_inline_link_returns_its_url_and_line(self) -> None:
        #: Given
        text = '# Guide\n\nSee [the rules](docs/rules.md).\n'

        #: When
        document = parse_document(text)

        #: Then
        assert document.links == (Link(url='docs/rules.md', line=LineNumber(3)),), (
            'an inline link carries its destination and the document line it is on'
        )

    def test_parse_document_with_link_syntax_in_the_frontmatter_returns_only_the_body_links(self) -> None:
        #: Given
        text = '---\nname: review\ndescription: See [the guide](/guide.md)\n---\nRead [the rules](rules.md).\n'

        #: When
        document = parse_document(text)

        #: Then
        assert document.links == (Link(url='rules.md', line=LineNumber(5)),), (
            'the frontmatter block is YAML, not Markdown, so link syntax inside it is not a link'
        )

    def test_parse_document_with_an_unused_link_definition_returns_no_links(self) -> None:
        #: Given
        text = 'No link here.\n\n[rules]: /docs/rules.md\n'

        #: When
        document = parse_document(text)

        #: Then
        assert document.links == (), 'a definition no link uses points nowhere, so it is not a link'

    def test_parse_document_with_an_image_returns_its_source_as_a_link(self) -> None:
        #: Given
        text = '![diagram](assets/flow.png)\n'

        #: When
        document = parse_document(text)

        #: Then
        assert document.links == (Link(url='assets/flow.png', line=LineNumber(1)),), (
            'an image points at a file as a link does, so its source is a link'
        )

    def test_parse_document_with_a_reference_style_link_returns_it_at_the_line_it_is_used(self) -> None:
        #: Given
        text = 'See [the rules][rules].\n\n[rules]: docs/rules.md\n'

        #: When
        document = parse_document(text)

        #: Then
        assert document.links == (Link(url='docs/rules.md', line=LineNumber(1)),), (
            'a reference-style link is reported where it is used, with the destination its definition gives'
        )

    def test_parse_document_with_an_autolink_returns_its_url(self) -> None:
        #: Given
        text = 'Read <https://agentskills.io/specification>.\n'

        #: When
        document = parse_document(text)

        #: Then
        assert document.links == (Link(url='https://agentskills.io/specification', line=LineNumber(1)),), (
            'an autolink is a link to its own text'
        )

    def test_parse_document_with_a_link_in_inline_code_returns_no_link(self) -> None:
        #: Given
        text = 'Write `[text](/absolute)` to link.\n'

        #: When
        document = parse_document(text)

        #: Then
        assert document.links == (), 'link syntax inside inline code is code, not a link'

    def test_parse_document_with_a_link_in_a_fenced_code_block_returns_no_link(self) -> None:
        #: Given
        text = '```markdown\n[text](/absolute)\n```\n'

        #: When
        document = parse_document(text)

        #: Then
        assert document.links == (), 'link syntax inside a fenced code block is code, not a link'

    def test_parse_document_with_links_in_nested_blocks_returns_each_in_document_order(self) -> None:
        #: Given
        text = '# Guide\n\n- first [one](a.md)\n\n> quoted [two](b.md)\n'

        #: When
        document = parse_document(text)

        #: Then
        assert document.links == (
            Link(url='a.md', line=LineNumber(3)),
            Link(url='b.md', line=LineNumber(5)),
        ), 'a link in a list item or a blockquote is found, each on its own document line'

    def test_parse_document_with_crlf_line_endings_returns_each_link_on_its_document_line(self) -> None:
        #: Given
        text = '# Guide\r\n\r\n[one](a.md)\r\n\r\n[two](b.md)\r\n'

        #: When
        document = parse_document(text)

        #: Then
        assert [link.line for link in document.links] == [LineNumber(3), LineNumber(5)], (
            'a CRLF line ending counts as one line break'
        )


@pytest.mark.unit
class TestParseDocumentAnchors:
    def test_parse_document_with_a_heading_returns_the_anchor_of_its_text(self) -> None:
        #: Given
        text = '# Getting Started\n'

        #: When
        document = parse_document(text)

        #: Then
        assert document.anchors == frozenset({Anchor('getting-started')}), (
            'a heading gives the anchor GitHub derives from its text'
        )

    def test_parse_document_with_inline_html_in_a_heading_anchors_only_its_text(self) -> None:
        #: Given
        text = '# <kbd>Ctrl</kbd> + C\n'

        #: When
        document = parse_document(text)

        #: Then
        assert document.anchors == frozenset({Anchor('ctrl--c')}), (
            'an inline HTML tag renders as markup, so only the text between the tags reaches the anchor'
        )

    def test_parse_document_with_an_html_comment_in_a_heading_leaves_it_out_of_the_anchor(self) -> None:
        #: Given
        text = '# Setup <!-- draft --> Guide\n'

        #: When
        document = parse_document(text)

        #: Then
        assert document.anchors == frozenset({Anchor('setup--guide')}), (
            'an HTML comment renders as nothing, so its text never reaches the anchor'
        )

    def test_parse_document_with_an_image_in_a_heading_leaves_its_alt_text_out_of_the_anchor(self) -> None:
        #: Given
        text = '# ![logo](logo.png) Title\n'

        #: When
        document = parse_document(text)

        #: Then
        assert document.anchors == frozenset({Anchor('-title')}), (
            'a rendered image holds no text, so its alt text is left out and the space after it stays a hyphen'
        )

    def test_parse_document_with_inline_markup_in_a_heading_anchors_its_plain_text(self) -> None:
        #: Given
        text = '# *Run* `just test` with [the skill](SKILL.md)\n'

        #: When
        document = parse_document(text)

        #: Then
        assert document.anchors == frozenset({Anchor('run-just-test-with-the-skill')}), (
            'emphasis, code and a link contribute their text, never their markup or destination'
        )

    def test_parse_document_with_a_repeated_heading_numbers_each_repeat(self) -> None:
        #: Given
        text = '# Usage\n\n## Usage\n\n### Usage\n'

        #: When
        document = parse_document(text)

        #: Then
        assert document.anchors == frozenset({Anchor('usage'), Anchor('usage-1'), Anchor('usage-2')}), (
            'the first heading keeps the bare anchor, and each repeat gets the next number'
        )

    def test_parse_document_with_a_repeat_colliding_with_a_numbered_heading_skips_the_taken_number(self) -> None:
        #: Given
        text = '# Foo 1\n\n# Foo\n\n# Foo\n'

        #: When
        document = parse_document(text)

        #: Then
        assert document.anchors == frozenset({Anchor('foo-1'), Anchor('foo'), Anchor('foo-2')}), (
            'the repeat of foo skips foo-1, which the first heading already holds'
        )

    def test_parse_document_with_headings_in_a_list_and_a_blockquote_returns_their_anchors(self) -> None:
        #: Given
        text = '# Guide\n\n- ## Listed\n\n> ### Quoted\n'

        #: When
        document = parse_document(text)

        #: Then
        assert document.anchors == frozenset({Anchor('guide'), Anchor('listed'), Anchor('quoted')}), (
            'a heading at any depth of the tree renders with an anchor a link can name'
        )

    def test_parse_document_with_a_setext_heading_returns_its_anchor(self) -> None:
        #: Given
        text = 'Getting Started\n===============\n\nSetup\n-----\n'

        #: When
        document = parse_document(text)

        #: Then
        assert document.anchors == frozenset({Anchor('getting-started'), Anchor('setup')}), (
            'an underlined heading gives an anchor as an ATX heading does'
        )

    def test_parse_document_with_an_html_heading_returns_no_anchor_for_it(self) -> None:
        #: Given
        text = '<h2>Usage</h2>\n'

        #: When
        document = parse_document(text)

        #: Then
        assert document.anchors == frozenset(), (
            'an HTML block heading is raw HTML, not a Markdown heading, so it gives no anchor'
        )

    def test_parse_document_with_a_heading_line_in_a_code_block_returns_no_anchor_for_it(self) -> None:
        #: Given
        text = '# Guide\n\n```markdown\n# Example\n```\n'

        #: When
        document = parse_document(text)

        #: Then
        assert document.anchors == frozenset({Anchor('guide')}), 'a heading line inside a fenced code block is code'

    def test_parse_document_with_frontmatter_returns_no_anchor_for_its_lines(self) -> None:
        #: Given
        text = '---\nname: review\n---\n# Review\n'

        #: When
        document = parse_document(text)

        #: Then
        assert document.anchors == frozenset({Anchor('review')}), (
            'the frontmatter block is YAML, so its closing line underlines no setext heading'
        )
