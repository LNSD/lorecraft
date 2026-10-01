"""Structure validation over a document's headings, with each section's prose words, and a missing section's notes.

``validate_structure`` is pure, so every case here is a text literal parsed in memory and an in-memory
structure aspect; no document and no specification file is read.
"""

from typing import Final

import pytest

from lorecraft.project.layout import SPECS_DIR
from lorecraft.project.schemas import AnySections, OutlineEntry, SectionEntry, StructureAspect, TitleRule
from lorecraft.project.syntax import LineNumber, parse_document

from ..reporting import Note, NoteKind
from ..structure import validate_structure

# The outline of a rule document: its own sections, then the Checklist, then an optional References.
RULE_OUTLINE: Final[tuple[OutlineEntry, ...]] = (
    AnySections(),
    SectionEntry(name='Checklist'),
    SectionEntry(name='References', optional=True),
)

# What a rule document's Checklist holds, as the outline entry naming it states it.
CHECKLIST_DESCRIPTION: Final[str] = (
    'The items a reviewer verifies before committing a change the rule document governs.'
)

# The body of the Checklist of docs/code/logging.md, trimmed: an example of a rule document's Checklist.
LOGGING_CHECKLIST: Final[str] = (
    'Before committing code, verify:\n'
    '\n'
    '- [ ] Every module that logs has exactly one `logger = logging.getLogger(__name__)` after its imports\n'
    '- [ ] No logger is stored as `self.logger` or any other instance or class attribute\n'
    '- [ ] No log call sits in a per-line loop, whatever its level'
)

# The body of the Checklist of docs/code/python-docstrings.md, trimmed: a second example of the same section.
DOCSTRINGS_CHECKLIST: Final[str] = (
    'Before committing code, verify:\n'
    '\n'
    '- [ ] Every new class and public function has a docstring whose first line is a one-line summary\n'
    '- [ ] No `Returns:` section restates the return annotation\n'
    '- [ ] A generator documents `Yields:`, never `Returns:`'
)

# What a feature document's Usage holds, as the outline entry naming it states it.
USAGE_DESCRIPTION: Final[str] = 'How to run the feature, each invocation commented with what it does.'

# The body of the Usage of docs/feat/cli-check-budget.md, trimmed: an example of a feature document's Usage.
BUDGET_USAGE: Final[str] = (
    '```bash\n'
    '# Check the token budget of every document\n'
    'lorecraft check budget\n'
    '\n'
    '# Check one document just written\n'
    'lorecraft check budget docs/feat/cli-check-budget.md\n'
    '```'
)


def _aspect(
    *,
    title: TitleRule | None = None,
    forbid_empty_sections: bool = False,
    outline: tuple[OutlineEntry, ...] = (),
    forbidden: tuple[str, ...] = (),
    stem: str = 'code',
) -> StructureAspect:
    """A structure aspect at `docs/__meta__/<stem>.structure.json`, quoting `<stem>.md` as its authority.

    Args:
        title: The H1 title rule; `None` states none.
        forbid_empty_sections: Whether a heading with an empty section is a violation.
        outline: The sections the document must follow, in order; empty states no outline.
        forbidden: Section names the document may not have.
        stem: File stem of the specification the aspect is written in.
    """
    return StructureAspect(
        path=SPECS_DIR / f'{stem}.structure.json',
        title=title,
        forbid_empty_sections=forbid_empty_sections,
        outline=outline,
        forbidden=forbidden,
        tokens=None,
        frontmatter=None,
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
        assert [(violation.line, violation.rule, violation.message) for violation in result.violations] == [
            (LineNumber(1), 'structure.title', 'expected 1 H1 title, found 2 (per code.md)')
        ], 'one title is expected and two are found'

    def test_validate_structure_with_a_section_before_the_title_reports_the_title_rule(self) -> None:
        #: Given
        text = '## Rule\n\ntext\n\n# Guide\n\ntext\n'
        document = parse_document(text)
        aspects = (_aspect(title=TitleRule(count=1, first=True)),)

        #: When
        result = validate_structure(aspects, headings=document.headings)

        #: Then
        assert [(violation.line, violation.rule, violation.message) for violation in result.violations] == [
            (LineNumber(1), 'structure.title', 'the H1 title comes before any section (per code.md)')
        ], 'the title must open the document when the rule says it comes first'

    def test_validate_structure_with_an_empty_section_reports_it_on_its_line(self) -> None:
        #: Given
        text = '# Guide\n\ntext\n\n## Empty\n## Full\n\ntext\n'
        document = parse_document(text)
        aspects = (_aspect(forbid_empty_sections=True),)

        #: When
        result = validate_structure(aspects, headings=document.headings)

        #: Then
        assert [(violation.line, violation.rule, violation.message) for violation in result.violations] == [
            (
                LineNumber(5),
                'structure.empty',
                'section `Empty` is empty; omit it rather than leaving it empty (per code.md)',
            )
        ], 'the empty section is reported on the line of its heading'

    def test_validate_structure_with_a_forbidden_section_reports_it_on_its_line(self) -> None:
        #: Given
        text = '## Rule\n\ntext\n\n## Changelog\n\ntext\n'
        document = parse_document(text)
        aspects = (_aspect(forbidden=('Changelog',)),)

        #: When
        result = validate_structure(aspects, headings=document.headings)

        #: Then
        assert [(violation.line, violation.rule, violation.message) for violation in result.violations] == [
            (LineNumber(5), 'structure.forbidden', 'section `Changelog` is forbidden here (per code.md)')
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
                    SectionEntry(name='Summary'),
                    SectionEntry(name='Usage'),
                )
            ),
        )

        #: When
        result = validate_structure(aspects, headings=document.headings)

        #: Then
        assert [(violation.line, violation.rule, violation.message) for violation in result.violations] == [
            (LineNumber(5), 'structure.outline', 'expected section `Usage`, found `Rule` (per code.md)')
        ], 'the divergence is reported on the section that sits where the required one belongs'

    def test_validate_structure_with_an_optional_section_left_out_matches_the_entries_after_it(self) -> None:
        #: Given
        text = '## Summary\n\ntext\n\n## Checklist\n\ntext\n'
        document = parse_document(text)
        aspects = (
            _aspect(
                outline=(
                    SectionEntry(name='Summary'),
                    SectionEntry(name='Usage', optional=True),
                    SectionEntry(name='Checklist'),
                )
            ),
        )

        #: When
        result = validate_structure(aspects, headings=document.headings)

        #: Then
        assert result.violations == (), 'an absent optional section is skipped, and the next entry still matches'

    def test_validate_structure_with_named_sections_swapped_reports_one_outline_finding(self) -> None:
        #: Given
        text = '## Rule\n\ntext\n\n## References\n\ntext\n\n## Checklist\n\ntext\n'
        document = parse_document(text)
        aspects = (_aspect(outline=RULE_OUTLINE),)

        #: When
        result = validate_structure(aspects, headings=document.headings)

        #: Then
        assert [(violation.line, violation.rule, violation.message) for violation in result.violations] == [
            (LineNumber(5), 'structure.outline', 'expected section `Checklist`, found `References` (per code.md)')
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
                SectionEntry(name='References'),
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

    def test_validate_structure_with_a_named_section_over_its_cap_reports_it_on_its_line(self) -> None:
        #: Given
        text = '## Rule\n\ntext\n\n## Checklist\n\none two three\n'
        document = parse_document(text)
        outline = (AnySections(), SectionEntry(name='Checklist', words=2))
        aspects = (_aspect(outline=outline),)

        #: When
        result = validate_structure(aspects, headings=document.headings)

        #: Then
        assert [(violation.line, violation.rule, violation.message) for violation in result.violations] == [
            (
                LineNumber(5),
                'structure.words.section',
                'section `Checklist` is 3 prose words; the cap is 2 (per code.md)',
            )
        ], 'a named section takes the cap of the entry naming it'

    def test_validate_structure_with_an_unnamed_section_over_the_any_cap_reports_it(self) -> None:
        #: Given
        text = '## Rule\n\none two three\n\n## Checklist\n\ntext\n'
        document = parse_document(text)
        outline = (AnySections(words=2), SectionEntry(name='Checklist'))
        aspects = (_aspect(outline=outline),)

        #: When
        result = validate_structure(aspects, headings=document.headings)

        #: Then
        assert [(violation.line, violation.message) for violation in result.violations] == [
            (LineNumber(1), 'section `Rule` is 3 prose words; the cap is 2 (per code.md)')
        ], 'a section the outline does not name takes the cap of the `any` run it falls in'

    def test_validate_structure_with_an_uncapped_named_entry_does_not_apply_the_any_cap(self) -> None:
        #: Given
        text = '## Rule\n\none\n\n## Checklist\n\none two three\n'
        document = parse_document(text)
        outline = (AnySections(words=1), SectionEntry(name='Checklist'))
        aspects = (_aspect(outline=outline),)

        #: When
        result = validate_structure(aspects, headings=document.headings)

        #: Then
        assert result.violations == (), 'a named entry without a cap leaves its section uncapped'

    def test_validate_structure_with_two_any_runs_applies_each_run_its_own_cap(self) -> None:
        #: Given
        text = '## Intro\n\none\n\n## Middle\n\ntext\n\n## Detail\n\none two three\n'
        document = parse_document(text)
        outline = (
            AnySections(words=1),
            SectionEntry(name='Middle'),
            AnySections(words=5),
        )
        aspects = (_aspect(outline=outline),)

        #: When
        result = validate_structure(aspects, headings=document.headings)

        #: Then
        assert result.violations == (), 'a section after `Middle` falls in the second run, capped at 5, not 1'

    def test_validate_structure_with_a_subsection_counts_its_words_into_its_section(self) -> None:
        #: Given
        text = '## Rule\n\none two\n\n### Detail\n\nthree four\n\n## Checklist\n\ntext\n'
        document = parse_document(text)
        outline = (AnySections(words=3), SectionEntry(name='Checklist'))
        aspects = (_aspect(outline=outline),)

        #: When
        result = validate_structure(aspects, headings=document.headings)

        #: Then
        assert [(violation.line, violation.message) for violation in result.violations] == [
            (LineNumber(1), 'section `Rule` is 4 prose words; the cap is 3 (per code.md)')
        ], 'an H3 is part of the section above it, so its words count against that section'

    def test_validate_structure_with_two_layers_applies_each_layer_its_own_caps(self) -> None:
        #: Given
        text = '## Rule\n\none two three\n\n## Checklist\n\ntext\n'
        document = parse_document(text)
        corpus = _aspect(outline=(AnySections(words=5), SectionEntry(name='Checklist')))
        namespace = _aspect(outline=(AnySections(words=2),), stem='code-python')

        #: When
        result = validate_structure((corpus, namespace), headings=document.headings)

        #: Then
        assert [violation.message for violation in result.violations] == [
            'section `Rule` is 3 prose words; the cap is 2 (per code-python.md)',
        ], 'the namespace layer tightens the corpus cap, and the violation quotes the layer that set it'


@pytest.mark.unit
class TestValidateStructureOutlineNotes:
    def test_validate_structure_without_a_described_section_reports_its_description_and_example(self) -> None:
        #: Given
        text = '## Rule\n\ntext\n'
        document = parse_document(text)
        checklist = SectionEntry(name='Checklist', description=CHECKLIST_DESCRIPTION, examples=(LOGGING_CHECKLIST,))
        aspects = (_aspect(outline=(AnySections(), checklist)),)

        #: When
        result = validate_structure(aspects, headings=document.headings)

        #: Then
        assert [violation.notes for violation in result.violations] == [
            (
                Note(NoteKind.HELP, CHECKLIST_DESCRIPTION),
                Note(NoteKind.NOTE, f'for example:\n## Checklist\n\n{LOGGING_CHECKLIST}'),
            )
        ], 'a missing section carries its description as help, then its example under its heading as a note'

    def test_validate_structure_without_a_section_stating_several_examples_reports_only_the_first(self) -> None:
        #: Given
        text = '## Rule\n\ntext\n'
        document = parse_document(text)
        checklist = SectionEntry(name='Checklist', examples=(LOGGING_CHECKLIST, DOCSTRINGS_CHECKLIST))
        aspects = (_aspect(outline=(AnySections(), checklist)),)

        #: When
        result = validate_structure(aspects, headings=document.headings)

        #: Then
        assert [violation.notes for violation in result.violations] == [
            (Note(NoteKind.NOTE, f'for example:\n## Checklist\n\n{LOGGING_CHECKLIST}'),)
        ], 'only the first example is reported; the rest are for a reader of the specification'

    def test_validate_structure_with_another_section_where_a_described_one_belongs_reports_its_notes(
        self,
    ) -> None:
        #: Given
        text = '## Summary\n\ntext\n\n## Rule\n\ntext\n'
        document = parse_document(text)
        usage = SectionEntry(name='Usage', description=USAGE_DESCRIPTION, examples=(BUDGET_USAGE,))
        aspects = (_aspect(outline=(SectionEntry(name='Summary'), usage)),)

        #: When
        result = validate_structure(aspects, headings=document.headings)

        #: Then
        assert [(violation.message, violation.notes) for violation in result.violations] == [
            (
                'expected section `Usage`, found `Rule` (per code.md)',
                (
                    Note(NoteKind.HELP, USAGE_DESCRIPTION),
                    Note(NoteKind.NOTE, f'for example:\n## Usage\n\n{BUDGET_USAGE}'),
                ),
            )
        ], 'a section found where the described one belongs carries the same notes as a missing one'

    def test_validate_structure_without_a_section_stating_only_a_description_reports_only_help(self) -> None:
        #: Given
        text = '## Rule\n\ntext\n'
        document = parse_document(text)
        checklist = SectionEntry(name='Checklist', description=CHECKLIST_DESCRIPTION)
        aspects = (_aspect(outline=(AnySections(), checklist)),)

        #: When
        result = validate_structure(aspects, headings=document.headings)

        #: Then
        assert [violation.notes for violation in result.violations] == [
            (Note(NoteKind.HELP, CHECKLIST_DESCRIPTION),)
        ], 'an entry without an example adds no example note'

    def test_validate_structure_without_a_section_stating_only_an_example_reports_only_the_example(self) -> None:
        #: Given
        text = '## Rule\n\ntext\n'
        document = parse_document(text)
        checklist = SectionEntry(name='Checklist', examples=(LOGGING_CHECKLIST,))
        aspects = (_aspect(outline=(AnySections(), checklist)),)

        #: When
        result = validate_structure(aspects, headings=document.headings)

        #: Then
        assert [violation.notes for violation in result.violations] == [
            (Note(NoteKind.NOTE, f'for example:\n## Checklist\n\n{LOGGING_CHECKLIST}'),)
        ], 'an entry without a description adds no help'

    def test_validate_structure_without_a_section_stating_neither_reports_no_notes(self) -> None:
        #: Given
        text = '## Rule\n\ntext\n'
        document = parse_document(text)
        aspects = (_aspect(outline=RULE_OUTLINE),)

        #: When
        result = validate_structure(aspects, headings=document.headings)

        #: Then
        assert [violation.notes for violation in result.violations] == [()], (
            'an entry stating neither key reports the bare finding, as before'
        )
