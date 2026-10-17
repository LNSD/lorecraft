"""What the structure specifications state about a document's title, budget and empty sections, as facts.

Every specification is decoded from its JSON by the real decoder and every document read by the real parser.
"""

from typing import Final

import pytest

from lorecraft.core.path import PathComponent, RootRelativePath
from lorecraft.project.query import StructurePrimitives
from lorecraft.project.syntax import parse_document

from ..document_facts import (
    find_document_title,
    title_facts,
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


@pytest.mark.unit
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

        #: When
        title = find_document_title(headings)

        #: Then
        assert title is None, 'a document with no H1 has no title'


@pytest.mark.unit
class TestTitleConstraints:
    def test_title_facts_keeps_the_order_and_skips_specifications_stating_none(self) -> None:
        #: Given
        corpus = _structure_spec('code', '{"tokens": 100, "title": {"chars": 20}, "empty_sections": "forbidden"}')
        silent = _structure_spec('code-silent', '{"outline": [{"section": "Rule"}]}')
        namespace = _structure_spec('code-python', '{"tokens": 50, "title": {"words": 3}}')

        #: When
        constraints = title_facts(StructurePrimitives((corpus, silent, namespace))).constraints

        #: Then
        assert [c.spec for c in constraints] == [corpus.path, namespace.path], 'title checks, in order'

    def test_title_facts_of_no_specification_is_empty(self) -> None:
        #: When
        constraints = title_facts(StructurePrimitives(())).constraints

        #: Then
        assert constraints == (), 'nothing governs'
