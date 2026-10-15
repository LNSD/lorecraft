"""Reading a document's Markdown into the values its parse tree is derived from.

Which top-level blocks the parser finds and what each holds, the text every heading renders as, the links, and
the frontmatter block. `parse_markdown` and `parse_markdown_frontmatter` are pure, so every case is a text literal;
what is counted or numbered from these values is pinned in `test_document`.
"""

import pytest

from ..markdown import (
    ContentBlock,
    HeadingBlock,
    MarkdownLine,
    MarkdownLink,
    MarkdownTree,
    parse_markdown,
    parse_markdown_frontmatter,
)


@pytest.mark.unit
class TestParseMarkdown:
    @pytest.mark.parametrize(
        ('text', 'expected'),
        [
            ('# `code` and *em* and **strong** [link](a.md) ~~del~~\n', 'code and em and strong link ~~del~~'),
            ('# a [ref][lbl] b\n\n[lbl]: x.md\n', 'a ref b'),
        ],
    )
    def test_parse_markdown_with_inline_markup_in_a_heading_returns_its_plain_text(
        self, text: str, expected: str
    ) -> None:
        #: When
        tree = parse_markdown(text)

        #: Then
        heading = tree.blocks[0]
        assert isinstance(heading, HeadingBlock)
        assert heading.text == expected, 'inline markup is stripped while its text is preserved'

    def test_parse_markdown_with_a_heading_and_a_paragraph_returns_both_as_blocks(self) -> None:
        #: Given
        text = '# Guide\n\nSome prose.\n'

        #: When
        tree = parse_markdown(text)

        #: Then
        assert tree == MarkdownTree(
            blocks=(
                HeadingBlock(level=1, text='Guide', line=MarkdownLine(1)),
                ContentBlock(source_outside_code=('Some prose.\n',)),
            ),
            heading_texts=('Guide',),
            links=(),
        ), 'a heading is a block with its level, text and line, and a paragraph a block of its source'

    def test_parse_markdown_with_a_setext_heading_returns_a_heading_block(self) -> None:
        #: Given
        text = 'Title\n=====\n'

        #: When
        tree = parse_markdown(text)

        #: Then
        assert tree.blocks == (HeadingBlock(level=1, text='Title', line=MarkdownLine(1)),), (
            'an underlined title is a heading as much as a `#` one'
        )

    def test_parse_markdown_with_a_fenced_code_block_returns_no_source_for_it(self) -> None:
        #: Given
        text = 'Intro\n\n```\n# not a heading\n```\n'

        #: When
        tree = parse_markdown(text)

        #: Then
        assert tree.blocks == (
            ContentBlock(source_outside_code=('Intro\n',)),
            ContentBlock(source_outside_code=('', '')),
        ), 'a code block is a block whose source outside code is empty on both sides, and a `#` in it no heading'

    def test_parse_markdown_with_code_nested_in_a_list_item_returns_the_source_around_it(self) -> None:
        #: Given
        text = '- one\n\n  ```\n  code\n  ```\n\n- two\n'

        #: When
        tree = parse_markdown(text)

        #: Then
        assert tree.blocks == (ContentBlock(source_outside_code=('- one\n\n  ', '\n- two\n')),), (
            'the list is one block, cut where its nested code block sits'
        )

    def test_parse_markdown_with_a_heading_in_a_blockquote_returns_it_inside_the_quote_block(self) -> None:
        #: Given
        text = '> # Quoted\n\n## Real\n'

        #: When
        tree = parse_markdown(text)

        #: Then
        assert tree.blocks == (
            ContentBlock(source_outside_code=('> # Quoted\n',)),
            HeadingBlock(level=2, text='Real', line=MarkdownLine(3)),
        ), 'a quoted heading is part of the blockquote, not a block of its own'

    def test_parse_markdown_with_a_heading_in_a_blockquote_returns_its_text_among_the_heading_texts(self) -> None:
        #: Given
        text = '> # Quoted\n\n## Real\n'

        #: When
        tree = parse_markdown(text)

        #: Then
        assert tree.heading_texts == ('Quoted', 'Real'), 'every heading at any depth has its text, in document order'

    def test_parse_markdown_with_html_and_an_image_in_a_heading_keeps_both_in_the_block_text(self) -> None:
        #: Given
        text = '# Hi <b>x</b> ![alt](a.png)\n'

        #: When
        tree = parse_markdown(text)

        #: Then
        assert tree.blocks == (HeadingBlock(level=1, text='Hi \n<b>\nx\n</b>\n alt', line=MarkdownLine(1)),), (
            "the heading block's plain text keeps inline HTML and an image's alt text"
        )

    def test_parse_markdown_with_html_and_an_image_in_a_heading_drops_both_from_the_rendered_text(self) -> None:
        #: Given
        text = '# Hi <b>x</b> ![alt](a.png)\n'

        #: When
        tree = parse_markdown(text)

        #: Then
        assert tree.heading_texts == ('Hi x ',), 'the rendered text drops inline HTML and an image, as GitHub does'

    def test_parse_markdown_with_links_at_any_depth_returns_each_on_its_line_in_document_order(self) -> None:
        #: Given
        text = 'See [a](a.md).\n\n- [![i](i.png)](b.md)\n'

        #: When
        tree = parse_markdown(text)

        #: Then
        assert tree.links == (
            MarkdownLink(url='a.md', line=MarkdownLine(1)),
            MarkdownLink(url='b.md', line=MarkdownLine(3)),
            MarkdownLink(url='i.png', line=MarkdownLine(3)),
        ), 'a link in a list item is found too, and an image inside a link comes after that link'

    def test_parse_markdown_with_crlf_line_endings_returns_each_heading_on_its_document_line(self) -> None:
        #: Given
        text = '# Guide\r\n\r\n## Usage\r\n'

        #: When
        tree = parse_markdown(text)

        #: Then
        assert tree.blocks == (
            HeadingBlock(level=1, text='Guide', line=MarkdownLine(1)),
            HeadingBlock(level=2, text='Usage', line=MarkdownLine(3)),
        ), 'a CRLF line ending counts as one line break'

    def test_parse_markdown_with_crlf_line_endings_returns_each_link_and_later_heading_on_its_document_line(
        self,
    ) -> None:
        #: Given
        text = '---\r\nname: guide\r\n---\r\n# Guide\r\n\r\nSee [a](a.md).\r\n\r\n- [b](b.md)\r\n\r\n## Usage\r\n'

        #: When
        tree = parse_markdown(text)

        #: Then
        assert tree.links == (
            MarkdownLink(url='a.md', line=MarkdownLine(6)),
            MarkdownLink(url='b.md', line=MarkdownLine(8)),
        ), 'each link after a frontmatter block and CRLF line endings is on its document line'
        assert tree.blocks[-1] == HeadingBlock(level=2, text='Usage', line=MarkdownLine(10)), (
            'a heading past several CRLF line endings is on its document line'
        )

    def test_parse_markdown_with_a_delimited_block_returns_no_block_for_it(self) -> None:
        #: Given
        text = '---\nname: guide\n---\n# Guide\n'

        #: When
        tree = parse_markdown(text)

        #: Then
        assert tree.blocks == (HeadingBlock(level=1, text='Guide', line=MarkdownLine(4)),), (
            'the frontmatter block is no Markdown block, and the heading after it keeps its document line'
        )


@pytest.mark.unit
class TestParseMarkdownFrontmatter:
    def test_parse_markdown_frontmatter_with_a_delimited_block_returns_its_frontmatter(self) -> None:
        #: Given
        text = '---\nname: guide\n---\n# Guide\n'

        #: When
        frontmatter = parse_markdown_frontmatter(text)

        #: Then
        assert frontmatter == 'name: guide\n', 'the raw block between delimiters retains its line ending'

    def test_parse_markdown_frontmatter_without_an_opening_delimiter_returns_missing(self) -> None:
        #: Given
        text = '# Guide\n\nname: guide\n'

        #: When
        frontmatter = parse_markdown_frontmatter(text)

        #: Then
        assert frontmatter is None, 'a document not opening with `---` has no frontmatter'
