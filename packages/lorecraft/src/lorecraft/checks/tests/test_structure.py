"""Structure validation over a document's headings.

``validate_structure`` is pure, so every case here is a text literal parsed in memory and an in-memory
structure aspect; no document and no specification file is read.
"""

from typing import Final

import pytest

from lorecraft_project.layout import SPECS_DIR
from lorecraft_project.schemas import AnySections, OutlineEntry, SectionEntry, StructureAspect, TitleRule
from lorecraft_project.syntax import LineNumber, parse_document

from ..structure import validate_structure

# The outline of a rule document: its own sections, then the Checklist, then an optional References.
RULE_OUTLINE: Final[tuple[OutlineEntry, ...]] = (
    AnySections(),
    SectionEntry(name='Checklist', optional=False),
    SectionEntry(name='References', optional=True),
)


def _aspect(
    *,
    title: TitleRule | None = None,
    forbid_empty_sections: bool = False,
    outline: tuple[OutlineEntry, ...] = (),
    forbidden: tuple[str, ...] = (),
    stem: str = 'code',
) -> StructureAspect:
    """A structure aspect at ``docs/__meta__/<stem>.structure.json``, quoting ``<stem>.md`` as its authority."""
    return StructureAspect(
        path=SPECS_DIR / f'{stem}.structure.json',
        title=title,
        forbid_empty_sections=forbid_empty_sections,
        outline=outline,
        forbidden=forbidden,
    )


@pytest.mark.unit
class TestValidateStructure:
    def test_validate_structure_with_a_conforming_document_returns_no_findings(self) -> None:
        #: Given
        text = '# Guide\n\n## Rule\n\ntext\n\n## Checklist\n\n- [ ] item\n'
        document = parse_document(text)
        aspects = (_aspect(title=TitleRule(count=1, first=True), forbid_empty_sections=True, outline=RULE_OUTLINE),)

        #: When
        result = validate_structure(aspects, headings=document.headings)

        #: Then
        assert result.violations == (), 'a document with its title, content and outline in order is clean'

    def test_validate_structure_with_empty_aspects_returns_no_findings(self) -> None:
        #: Given
        text = '## Empty\n'
        document = parse_document(text)
        aspects: tuple[StructureAspect, ...] = ()

        #: When
        result = validate_structure(aspects, headings=document.headings)

        #: Then
        assert result.violations == (), 'an ungoverned document is never checked, whatever its structure'

    def test_validate_structure_with_two_titles_reports_the_title_rule(self) -> None:
        #: Given
        text = '# Guide\n\ntext\n\n# Again\n\ntext\n'
        document = parse_document(text)
        aspects = (_aspect(title=TitleRule(count=1, first=True)),)

        #: When
        result = validate_structure(aspects, headings=document.headings)

        #: Then
        assert [(violation.line, violation.rule) for violation in result.violations] == [
            (LineNumber(1), 'structure.title')
        ], 'one title is expected and two are found'

    def test_validate_structure_with_a_section_before_the_title_reports_the_title_rule(self) -> None:
        #: Given
        text = '## Rule\n\ntext\n\n# Guide\n\ntext\n'
        document = parse_document(text)
        aspects = (_aspect(title=TitleRule(count=1, first=True)),)

        #: When
        result = validate_structure(aspects, headings=document.headings)

        #: Then
        assert [violation.message for violation in result.violations] == [
            'the H1 title comes before any section (per code.md)'
        ], 'the title must open the document when the rule says it comes first'

    def test_validate_structure_with_an_empty_section_reports_it_on_its_line(self) -> None:
        #: Given
        text = '# Guide\n\ntext\n\n## Empty\n## Full\n\ntext\n'
        document = parse_document(text)
        aspects = (_aspect(forbid_empty_sections=True),)

        #: When
        result = validate_structure(aspects, headings=document.headings)

        #: Then
        assert [(violation.line, violation.rule) for violation in result.violations] == [
            (LineNumber(5), 'structure.empty')
        ], 'the empty section is reported on the line of its heading'

    def test_validate_structure_with_a_forbidden_section_reports_it_on_its_line(self) -> None:
        #: Given
        text = '## Rule\n\ntext\n\n## Changelog\n\ntext\n'
        document = parse_document(text)
        aspects = (_aspect(forbidden=('Changelog',)),)

        #: When
        result = validate_structure(aspects, headings=document.headings)

        #: Then
        assert [(violation.line, violation.rule) for violation in result.violations] == [
            (LineNumber(5), 'structure.forbidden')
        ], 'a forbidden section is reported where it is written'

    def test_validate_structure_without_a_required_section_reports_it_missing(self) -> None:
        #: Given
        text = '## Rule\n\ntext\n'
        document = parse_document(text)
        aspects = (_aspect(outline=RULE_OUTLINE),)

        #: When
        result = validate_structure(aspects, headings=document.headings)

        #: Then
        assert [violation.message for violation in result.violations] == [
            'missing required section `Checklist` (per code.md)'
        ], 'a required section the document never reaches is missing, reported on line 1'

    def test_validate_structure_with_an_unnamed_section_where_a_named_one_belongs_reports_what_it_found(
        self,
    ) -> None:
        #: Given
        text = '## Summary\n\ntext\n\n## Rule\n\ntext\n'
        document = parse_document(text)
        aspects = (
            _aspect(
                outline=(
                    SectionEntry(name='Summary', optional=False),
                    SectionEntry(name='Usage', optional=False),
                )
            ),
        )

        #: When
        result = validate_structure(aspects, headings=document.headings)

        #: Then
        assert [(violation.line, violation.message) for violation in result.violations] == [
            (LineNumber(5), 'expected section `Usage`, found `Rule` (per code.md)')
        ], 'the divergence is reported on the section that sits where the required one belongs'

    def test_validate_structure_with_named_sections_swapped_reports_one_outline_finding(self) -> None:
        #: Given
        text = '## Rule\n\ntext\n\n## References\n\ntext\n\n## Checklist\n\ntext\n'
        document = parse_document(text)
        aspects = (_aspect(outline=RULE_OUTLINE),)

        #: When
        result = validate_structure(aspects, headings=document.headings)

        #: Then
        assert [(violation.line, violation.message) for violation in result.violations] == [
            (LineNumber(5), 'expected section `Checklist`, found `References` (per code.md)')
        ], 'only the first divergence is reported, never the cascade after it'

    def test_validate_structure_with_a_named_section_after_the_outline_ends_reports_it_out_of_order(
        self,
    ) -> None:
        #: Given
        text = '## Checklist\n\ntext\n\n## References\n\ntext\n\n## Checklist\n\ntext\n'
        document = parse_document(text)
        aspects = (_aspect(outline=RULE_OUTLINE),)

        #: When
        result = validate_structure(aspects, headings=document.headings)

        #: Then
        assert [(violation.line, violation.message) for violation in result.violations] == [
            (LineNumber(9), 'section `Checklist` is out of order (per code.md)')
        ], 'a named section left over once the outline ends was written out of turn'

    def test_validate_structure_with_an_unnamed_section_after_the_outline_ends_reports_it_unexpected(
        self,
    ) -> None:
        #: Given
        text = '## Checklist\n\ntext\n\n## Appendix\n\ntext\n'
        document = parse_document(text)
        aspects = (_aspect(outline=RULE_OUTLINE),)

        #: When
        result = validate_structure(aspects, headings=document.headings)

        #: Then
        assert [(violation.line, violation.message) for violation in result.violations] == [
            (LineNumber(5), 'unexpected section `Appendix`; the outline ends before it (per code.md)')
        ], 'an unnamed section past the last entry is written past the end of the document'

    def test_validate_structure_with_a_subsection_ignores_it_in_the_outline(self) -> None:
        #: Given
        text = '## Rule\n\n### Detail\n\ntext\n\n## Checklist\n\ntext\n'
        document = parse_document(text)
        aspects = (_aspect(outline=RULE_OUTLINE),)

        #: When
        result = validate_structure(aspects, headings=document.headings)

        #: Then
        assert result.violations == (), 'only H2 headings are sections; an H3 is part of the section above it'

    def test_validate_structure_with_two_layers_applies_each_and_quotes_its_own_authority(self) -> None:
        #: Given
        text = '## Rule\n\ntext\n\n## Checklist\n\ntext\n'
        document = parse_document(text)
        corpus = _aspect(outline=RULE_OUTLINE)
        namespace = _aspect(
            outline=(
                AnySections(),
                SectionEntry(name='References', optional=False),
                AnySections(),
            ),
            stem='code-python',
        )

        #: When
        result = validate_structure((corpus, namespace), headings=document.headings)

        #: Then
        assert [violation.message for violation in result.violations] == [
            'missing required section `References` (per code-python.md)'
        ], 'the namespace layer adds its own requirement, which the corpus layer does not relax'

    def test_validate_structure_with_findings_on_several_lines_orders_them_by_line(self) -> None:
        #: Given
        text = '## Changelog\n\ntext\n\n## Empty\n'
        document = parse_document(text)
        aspects = (_aspect(forbid_empty_sections=True, forbidden=('Changelog',), outline=RULE_OUTLINE),)

        #: When
        result = validate_structure(aspects, headings=document.headings)

        #: Then
        assert [(violation.line.value, violation.rule) for violation in result.violations] == [
            (1, 'structure.forbidden'),
            (1, 'structure.outline'),
            (5, 'structure.empty'),
        ], 'violations are ordered by line, then by rule'
