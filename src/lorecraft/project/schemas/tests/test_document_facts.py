"""What the structure specifications state about a document's title, budget and empty sections, as facts.

Every specification is decoded from its JSON by the real decoder and every document read by the real parser.
"""

from typing import Final

from lorecraft.core.path import PathComponent, RootRelativePath
from lorecraft.project.syntax import parse_document

from ..document_facts import (
    empty_headings,
    empty_section_specs,
    find_document_title,
    title_constraints,
    token_budgets,
)
from ..name import parse_spec_name
from ..spec_file import SpecFileType, StructureSpecFile, spec_filename
from ..structure import StructureSchema, StructureSpec

SPECS_DIR: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__')


def _structure_spec(spec_name: str, text: str) -> StructureSpec:
    """A structure specification decoded from its JSON.

    Args:
        spec_name: The specification's name, such as `code` or `code-python`.
        text: The structure specification's JSON.
    """
    name = parse_spec_name(spec_name)
    file = StructureSpecFile(path=SPECS_DIR / PathComponent.parse(spec_filename(name, SpecFileType.SPEC)), name=name)
    spec = StructureSpec.parse(file, StructureSchema(text))
    assert isinstance(spec, StructureSpec), f'the test states a usable specification, got {spec!r}'
    return spec


class TestFindDocumentTitle:
    def test_find_document_title_measures_the_text_without_its_markup(self) -> None:
        #: Given
        headings = parse_document('# The **Big** Guide\n\nText.\n').headings

        #: When
        title = find_document_title(headings)

        #: Then
        assert title is not None, 'the document has a title'
        assert title.heading.text == 'The Big Guide', 'the heading is the first H1'
        assert (title.chars.value, title.words.value) == (13, 3), 'the counts are of the stripped text'

    def test_find_document_title_with_no_h1_returns_none(self) -> None:
        #: Given
        headings = parse_document('## Section\n\nText.\n').headings

        #: Then
        assert find_document_title(headings) is None, 'a document with no H1 has no title'


class TestSpecificationFacts:
    def test_facts_keep_the_order_of_the_specifications_and_skip_those_that_state_none(self) -> None:
        #: Given
        corpus = _structure_spec('code', '{"tokens": 100, "title": {"chars": 20}, "empty_sections": "forbidden"}')
        silent = _structure_spec('code-silent', '{"outline": [{"section": "Rule"}]}')
        namespace = _structure_spec('code-python', '{"tokens": 50, "title": {"words": 3}}')
        specs = (corpus, silent, namespace)

        #: Then
        assert [c.spec for c in title_constraints(specs)] == [corpus.path, namespace.path], 'title checks, in order'
        assert [(b.spec, b.tokens.value) for b in token_budgets(specs)] == [(corpus.path, 100), (namespace.path, 50)], (
            'one budget per specification that sets one'
        )
        assert empty_section_specs(specs) == (corpus.path,), 'only the specification that forbids empty sections'

    def test_facts_of_no_specification_are_empty(self) -> None:
        #: Then
        assert (title_constraints(()), token_budgets(()), empty_section_specs(())) == ((), (), ()), 'nothing governs'


class TestEmptyHeadings:
    def test_empty_headings_holds_the_empty_title_and_sections_in_document_order(self) -> None:
        #: Given
        headings = parse_document('# Title\n\n## Empty\n\n## Full\n\nText.\n\n## Last\n').headings

        #: Then
        assert [heading.text for heading in empty_headings(headings)] == ['Empty', 'Last'], 'document order'
