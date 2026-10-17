"""The `empty_section_facts` query of `OUT004`: the specifications forbidding empty sections and the empty headings."""

from typing import Final

import pytest

from lorecraft.core.path import PathComponent, RootRelativePath
from lorecraft.project.schemas import (
    SpecFileType,
    StructurePrimitives,
    StructureSchema,
    StructureSpec,
    StructureSpecFile,
    parse_spec_name,
    spec_filename,
)
from lorecraft.project.syntax import parse_document

from ..empty_section import EmptyTitle, OtherSection, empty_section_facts

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
class TestEmptySectionSpecs:
    def test_empty_section_facts_holds_only_the_specifications_forbidding_them(self) -> None:
        #: Given
        corpus = _structure_spec('code', '{"tokens": 100, "title": {"chars": 20}, "empty_sections": "forbidden"}')
        namespace = _structure_spec('code-python', '{"tokens": 50, "title": {"words": 3}}')

        #: When
        specs = empty_section_facts(StructurePrimitives((corpus, namespace))).specs

        #: Then
        assert specs == (corpus.path,), 'only the specification that forbids empty sections'

    def test_empty_section_facts_of_no_specification_is_empty(self) -> None:
        #: When
        specs = empty_section_facts(StructurePrimitives(())).specs

        #: Then
        assert specs == (), 'nothing governs'


@pytest.mark.unit
class TestEmptyHeadings:
    def test_empty_section_facts_holds_the_empty_sections_in_document_order(self) -> None:
        #: Given
        headings = parse_document('# Title\n\n## Empty\n\n## Full\n\nText.\n\n## Last\n').headings

        #: When
        empty = empty_section_facts(StructurePrimitives((), headings)).empty

        #: Then
        assert [item.heading.text for item in empty] == ['Empty', 'Last'], 'document order'

    def test_empty_section_facts_gives_the_title_its_own_role(self) -> None:
        #: Given
        headings = parse_document('# Title\n').headings

        #: When
        empty = empty_section_facts(StructurePrimitives((), headings)).empty

        #: Then
        assert [item.role for item in empty] == [EmptyTitle()], 'the title'

    def test_empty_section_facts_gives_an_unrequired_section_the_other_role(self) -> None:
        #: Given
        headings = parse_document('# Title\n\nText.\n\n## Empty\n').headings

        #: When
        empty = empty_section_facts(StructurePrimitives((), headings)).empty

        #: Then
        assert [item.role for item in empty] == [OtherSection()], 'no outline requires it'
