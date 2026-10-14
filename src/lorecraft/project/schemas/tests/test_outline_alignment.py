"""Which outline entry each of a document's sections falls in, for each structure specification that governs it.

Every document's headings are read from its text by the real parser, and every outline decoded from a structure
specification's JSON by the real decoder: a document that follows its outline, one that writes its sections out of
order, one with a section no entry names and no `any` run covers, and one held to two specifications.
"""

from typing import Final, assert_never

import pytest

from lorecraft.core.path import PathComponent, RootRelativePath
from lorecraft.project.syntax import parse_document, section_headings

from ..name import parse_spec_name
from ..outline_alignment import (
    AlignedSection,
    AnyRunAlignment,
    NamedAlignment,
    UnalignedSection,
    align_outlines,
)
from ..spec_file import SpecFileType, StructureSpecFile, spec_filename
from ..structure import StructureSchema, StructureSpec

SPECS_DIR: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__')

CORPUS_SPEC: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/code.structure.json')
"""The corpus structure specification."""

NAMESPACE_SPEC: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/code-python.structure.json')
"""The `python` namespace structure specification."""

RULE_ASIDE_CHECKLIST: Final[str] = (
    '# Typing\n'
    '\n'
    '## Rule\n'
    '\n'
    'Annotate every signature.\n'
    '\n'
    '## Aside\n'
    '\n'
    'Read the rationale once.\n'
    '\n'
    '## Checklist\n'
    '\n'
    '- [ ] Annotated.\n'
)
"""A document with a title, then the sections `Rule`, `Aside` and `Checklist`."""


def _structure_spec(spec_name: str, text: str) -> StructureSpec:
    """A structure specification decoded from its JSON.

    Args:
        spec_name: The specification's name, such as `code` or `code-python`.
        text: The structure specification's JSON.
    """
    name = parse_spec_name(spec_name)
    file = StructureSpecFile(
        path=SPECS_DIR / PathComponent.parse(spec_filename(name, SpecFileType.LEGACY_STRUCTURE)), name=name
    )
    spec = StructureSpec.parse(file, StructureSchema(text))
    assert isinstance(spec, StructureSpec), f'the test states a usable specification, got {spec!r}'
    return spec


def _align_corpus(spec_json: str, text: str) -> tuple[AlignedSection, ...]:
    """The sections of a document aligned to the one structure specification its corpus states.

    Args:
        spec_json: The corpus structure specification's JSON.
        text: The document's text.
    """
    alignments = align_outlines((_structure_spec('code', spec_json),), parse_document(text).headings)
    assert len(alignments) == 1, 'one specification is aligned to'
    return alignments[0].sections


def _entry_summary(aligned: tuple[AlignedSection, ...]) -> list[str]:
    """What each aligned section falls in, as `name`, `any` or `-` for nothing, in document order.

    Args:
        aligned: The aligned sections.
    """
    summary: list[str] = []
    for section in aligned:
        match section:
            case NamedAlignment():
                summary.append(section.entry.name.value)
            case AnyRunAlignment():
                summary.append('any')
            case UnalignedSection():
                summary.append('-')
            case _:
                assert_never(section)
    return summary


def _forbidden_flags(aligned: tuple[AlignedSection, ...]) -> list[bool]:
    """Whether each aligned section is forbidden, in document order; a named section never is.

    Args:
        aligned: The aligned sections.
    """
    flags: list[bool] = []
    for section in aligned:
        match section:
            case NamedAlignment():
                flags.append(False)
            case AnyRunAlignment() | UnalignedSection():
                flags.append(section.forbidden)
            case _:
                assert_never(section)
    return flags


def _word_caps(aligned: tuple[AlignedSection, ...]) -> list[int | None]:
    """The word cap of the entry each aligned section falls in, in document order; `None` where it has none.

    Args:
        aligned: The aligned sections.
    """
    caps: list[int | None] = []
    for section in aligned:
        match section:
            case NamedAlignment():
                cap = section.entry.words
            case AnyRunAlignment():
                cap = section.run.words
            case UnalignedSection():
                cap = None
            case _:
                assert_never(section)
        caps.append(cap.value if cap is not None else None)
    return caps


@pytest.mark.unit
class TestAlignOutlines:
    def test_align_outlines_with_a_document_following_its_outline_aligns_each_section_to_its_entry(self) -> None:
        #: Given
        spec_json = '{"outline": [{"section": "Rule"}, {"any": true}, {"section": "Checklist"}]}'

        #: When
        aligned = _align_corpus(spec_json, RULE_ASIDE_CHECKLIST)

        #: Then
        assert _entry_summary(aligned) == ['Rule', 'any', 'Checklist'], (
            'a named section falls in the entry naming it, and an unnamed one in the `any` run between its neighbours'
        )

    def test_align_outlines_with_sections_written_out_of_order_aligns_each_to_the_entry_naming_it(self) -> None:
        #: Given
        spec_json = '{"outline": [{"section": "Checklist"}, {"any": true}, {"section": "Rule"}]}'

        #: When
        aligned = _align_corpus(spec_json, RULE_ASIDE_CHECKLIST)

        #: Then
        assert _entry_summary(aligned) == ['Rule', '-', 'Checklist'], (
            'a named section falls in the entry naming it, in or out of its turn; `Aside` follows `Rule`, which '
            'the outline places last, so no `any` run follows to cover it'
        )

    def test_align_outlines_with_an_unnamed_section_after_every_any_run_aligns_it_to_nothing(self) -> None:
        #: Given
        spec_json = '{"outline": [{"any": true}, {"section": "Rule"}, {"section": "Checklist"}]}'

        #: When
        aligned = _align_corpus(spec_json, RULE_ASIDE_CHECKLIST)

        #: Then
        assert _entry_summary(aligned) == ['Rule', '-', 'Checklist'], (
            'the `any` run precedes `Rule`, so `Aside` after it is covered by no `any` run and falls in no entry'
        )

    def test_align_outlines_with_an_unnamed_section_before_a_later_any_run_aligns_it_to_that_any_run(self) -> None:
        #: Given
        text = '# Typing\n\n## Aside\n\nRead the rationale once.\n\n## Rule\n\nAnnotate every signature.\n'
        spec_json = '{"outline": [{"section": "Rule"}, {"any": true}]}'

        #: When
        aligned = _align_corpus(spec_json, text)

        #: Then
        assert _entry_summary(aligned) == ['any', 'Rule'], (
            'a section before every named one falls in the first `any` run of the outline, whatever its place'
        )

    def test_align_outlines_with_an_any_run_holding_a_cap_aligns_the_section_to_that_any_run(self) -> None:
        #: Given
        spec_json = '{"outline": [{"section": "Rule", "words": 30}, {"any": true, "words": 5}]}'

        #: When
        aligned = _align_corpus(spec_json, RULE_ASIDE_CHECKLIST)

        #: Then
        assert _word_caps(aligned) == [30, 5, 5], (
            'the section carries the entry itself, so its cap is the one of the entry it falls in'
        )

    def test_align_outlines_with_a_forbidden_section_marks_it_forbidden(self) -> None:
        #: Given
        spec_json = '{"outline": [{"section": "Rule"}, {"any": true}], "forbidden": ["Aside"]}'

        #: When
        aligned = _align_corpus(spec_json, RULE_ASIDE_CHECKLIST)

        #: Then
        assert _forbidden_flags(aligned) == [False, True, False], 'only `Aside` is forbidden'
        assert _entry_summary(aligned) == ['Rule', 'any', 'any'], (
            'a forbidden section is no named one, so the `any` run covers it as it covers any unnamed section'
        )

    def test_align_outlines_with_a_specification_stating_no_outline_aligns_each_section_to_nothing(self) -> None:
        #: Given
        spec_json = '{"forbidden": ["Aside"]}'

        #: When
        aligned = _align_corpus(spec_json, RULE_ASIDE_CHECKLIST)

        #: Then
        assert _entry_summary(aligned) == ['-', '-', '-'], 'with no outline there is no entry to fall in'
        assert _forbidden_flags(aligned) == [False, True, False], 'the forbidden names still apply'

    def test_align_outlines_with_a_subsection_aligns_only_the_h2_sections(self) -> None:
        #: Given
        text = '# Typing\n\n## Rule\n\n### Detail\n\nAnnotate every signature.\n\n## Checklist\n\n- [ ] Annotated.\n'
        spec_json = '{"outline": [{"section": "Rule"}, {"any": true}, {"section": "Checklist"}]}'

        #: When
        aligned = _align_corpus(spec_json, text)

        #: Then
        assert [section.section.text for section in aligned] == ['Rule', 'Checklist'], (
            'only an H2 is a section; the H3 is part of the section above it'
        )

    def test_align_outlines_with_two_specifications_aligns_the_sections_to_each_on_its_own(self) -> None:
        #: Given
        corpus = _structure_spec('code', '{"outline": [{"section": "Rule"}, {"any": true}]}')
        namespace = _structure_spec('code-python', '{"outline": [{"section": "Checklist"}]}')
        headings = parse_document(RULE_ASIDE_CHECKLIST).headings

        #: When
        alignments = align_outlines((corpus, namespace), headings)

        #: Then
        specs = [alignment.spec for alignment in alignments]
        assert specs == [CORPUS_SPEC, NAMESPACE_SPEC], 'one entry per specification, in the order given'
        assert _entry_summary(alignments[0].sections) == ['Rule', 'any', 'any'], (
            'the corpus outline names `Rule`, then an `any` run covers the rest'
        )
        assert _entry_summary(alignments[1].sections) == ['-', '-', 'Checklist'], (
            'the namespace outline names only `Checklist`, so the sections before it fall in no `any` run of it'
        )

    def test_align_outlines_with_named_and_unnamed_sections_pairs_each_named_section_with_the_entry_naming_it(
        self,
    ) -> None:
        #: Given
        text = RULE_ASIDE_CHECKLIST + '\n### Detail\n\nMore.\n\n## Appendix\n\nExtra.\n'
        spec_json = '{"outline": [{"section": "Checklist"}, {"any": true}, {"section": "Rule"}]}'

        #: When
        aligned = _align_corpus(spec_json, text)

        #: Then
        assert [section.section.text for section in aligned if isinstance(section, NamedAlignment)] == [
            'Rule',
            'Checklist',
        ], 'two sections are named'
        assert all(
            section.entry.names(section.section) for section in aligned if isinstance(section, NamedAlignment)
        ), 'a named alignment holds the entry that names its section, whichever sections surround it'


@pytest.mark.unit
class TestOutlineAlignmentSpecAlignedSection:
    def test_aligned_section_with_a_section_of_the_document_returns_its_aligned_section(self) -> None:
        #: Given
        document = parse_document(RULE_ASIDE_CHECKLIST)
        structure_spec = _structure_spec('code', '{"outline": [{"section": "Rule"}, {"any": true}]}')
        alignment = align_outlines((structure_spec,), document.headings)[0]
        aside = next(section for section in section_headings(document.headings) if section.text == 'Aside')

        #: When
        aligned = alignment.aligned_section(aside)

        #: Then
        assert aligned.section.line == aside.line, 'the aligned section holds the heading it was found by'

    def test_aligned_section_with_a_section_of_another_document_raises(self) -> None:
        #: Given
        document = parse_document(RULE_ASIDE_CHECKLIST)
        structure_spec = _structure_spec('code', '{"outline": [{"section": "Rule"}, {"any": true}]}')
        alignment = align_outlines((structure_spec,), document.headings)[0]
        stray = section_headings(parse_document('\n' * 99 + '## Stray\n').headings)[0]

        #: When / Then
        with pytest.raises(ValueError, match='no section of the aligned document'):
            alignment.aligned_section(stray)
