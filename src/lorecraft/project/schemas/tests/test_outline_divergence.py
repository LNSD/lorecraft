"""Where a document's sections first stop matching the outline each structure specification states.

Every document's headings and line count are read from its text by the real parser and counter, and every outline
decoded from a structure specification's JSON by the real decoder: a document that follows its outline, one for each
way it can first stop following it, and one held to two outlines.
"""

from typing import Final

import pytest

from lorecraft.core.path import RootRelativePath
from lorecraft.project.syntax import Heading, LineNumber, count_lines, parse_document

from ..name import parse_spec_name
from ..outline_divergence import (
    AbsentSection,
    DocumentEnd,
    MisplacedSection,
    OutlineDivergenceSpec,
    UnlistedSection,
    match_outlines,
)
from ..section_name import SectionName
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
"""A document of thirteen lines: a title, then the sections `Rule`, `Aside` and `Checklist`."""


def _structure_spec(spec_name: str, text: str) -> StructureSpec:
    """A structure specification decoded from its JSON.

    Args:
        spec_name: The specification's name, such as `code` or `code-python`.
        text: The structure specification's JSON.
    """
    name = parse_spec_name(spec_name)
    file = StructureSpecFile(path=SPECS_DIR / spec_filename(name, SpecFileType.STRUCTURE), name=name)
    return StructureSpec.parse(file, StructureSchema(text))


def _match_corpus_outline(outline: str, text: str) -> tuple[OutlineDivergenceSpec, ...]:
    """Match a document against the one outline its corpus's structure specification states.

    Args:
        outline: The corpus structure specification's JSON; it states an outline.
        text: The document's text.
    """
    return match_outlines((_structure_spec('code', outline),), parse_document(text).headings, count_lines(text))


def _section(text: str, name: str) -> Heading:
    """The H2 section with this heading text, as the parser reads it from a document's text.

    Args:
        text: The document's text.
        name: The section's heading text.
    """
    for heading in parse_document(text).headings:
        if heading.level == 2 and heading.text == name:
            return heading
    raise AssertionError(f'the document holds a section `{name}`')


@pytest.mark.unit
class TestMatchOutlines:
    def test_match_outlines_with_a_document_following_its_outline_holds_no_divergence(self) -> None:
        #: Given
        outline = '{"outline": [{"section": "Rule"}, {"any": true}, {"section": "Checklist"}]}'

        #: When
        found = _match_corpus_outline(outline, RULE_ASIDE_CHECKLIST)

        #: Then
        assert found == (OutlineDivergenceSpec(spec=CORPUS_SPEC, divergence=None),), (
            'a document whose sections match the outline, an unnamed one inside an `any` run, does not diverge'
        )

    def test_match_outlines_with_a_section_absent_before_another_holds_it_before_that_section(self) -> None:
        #: Given
        outline = (
            '{"outline": [{"section": "Rule"}, {"section": "Example", "description": "A worked case.",'
            ' "examples": ["The first.", "The second."]}, {"any": true}, {"section": "Checklist"}]}'
        )

        #: When
        found = _match_corpus_outline(outline, RULE_ASIDE_CHECKLIST)

        #: Then
        absent = AbsentSection(
            name=SectionName.parse('Example'),
            description='A worked case.',
            example='The first.',
            before=_section(RULE_ASIDE_CHECKLIST, 'Aside'),
        )
        assert found == (OutlineDivergenceSpec(spec=CORPUS_SPEC, divergence=absent),), (
            'a required section held nowhere is absent before the section found in its place, with what its entry '
            'states and only its first example'
        )

    def test_match_outlines_with_a_section_absent_at_the_end_holds_the_last_line(self) -> None:
        #: Given
        outline = '{"outline": [{"section": "Rule"}, {"any": true}, {"section": "Checklist"}, {"section": "See Also"}]}'

        #: When
        found = _match_corpus_outline(outline, RULE_ASIDE_CHECKLIST)

        #: Then
        absent = AbsentSection(
            name=SectionName.parse('See Also'),
            description=None,
            example=None,
            before=DocumentEnd(last_line=LineNumber.from_int(13)),
        )
        assert found == (OutlineDivergenceSpec(spec=CORPUS_SPEC, divergence=absent),), (
            "a required section expected after every section is absent at the end, the document's last line"
        )

    def test_match_outlines_with_a_section_absent_from_an_empty_document_holds_line_1(self) -> None:
        #: Given
        outline = '{"outline": [{"section": "Rule"}]}'

        #: When
        found = _match_corpus_outline(outline, '')

        #: Then
        absent = AbsentSection(
            name=SectionName.parse('Rule'),
            description=None,
            example=None,
            before=DocumentEnd(last_line=LineNumber.from_int(1)),
        )
        assert found == (OutlineDivergenceSpec(spec=CORPUS_SPEC, divergence=absent),), (
            'an empty document has no line, so its end is placed on line 1'
        )

    def test_match_outlines_with_a_named_section_in_place_of_a_later_one_holds_it_misplaced(self) -> None:
        #: Given
        # `Rule` is written, but after `Checklist`, which the outline names and so is out of order where it stands
        text = '# Typing\n\n## Checklist\n\n- [ ] Annotated.\n\n## Rule\n\nAnnotate every signature.\n'
        outline = '{"outline": [{"section": "Rule"}, {"section": "Checklist"}]}'

        #: When
        found = _match_corpus_outline(outline, text)

        #: Then
        misplaced = MisplacedSection(section=_section(text, 'Checklist'), expected=SectionName.parse('Rule'))
        assert found == (OutlineDivergenceSpec(spec=CORPUS_SPEC, divergence=misplaced),), (
            'a named section standing where an expected section held later belongs is out of order'
        )

    def test_match_outlines_with_an_unnamed_section_in_place_of_a_later_one_holds_it_unlisted(self) -> None:
        #: Given
        # `Aside` stands between `Rule` and `Checklist`, where no `any` run allows a section the outline does not name
        outline = '{"outline": [{"section": "Rule"}, {"section": "Checklist"}]}'

        #: When
        found = _match_corpus_outline(outline, RULE_ASIDE_CHECKLIST)

        #: Then
        unlisted = UnlistedSection(
            section=_section(RULE_ASIDE_CHECKLIST, 'Aside'), expected=SectionName.parse('Checklist')
        )
        assert found == (OutlineDivergenceSpec(spec=CORPUS_SPEC, divergence=unlisted),), (
            'an unnamed section standing where an expected section held later belongs is unexpected'
        )

    def test_match_outlines_with_a_named_section_left_over_holds_it_misplaced(self) -> None:
        #: Given
        # the optional `Rule` is skipped where `Checklist` stands, so the `Rule` written after it is left over
        text = '# Typing\n\n## Checklist\n\n- [ ] Annotated.\n\n## Rule\n\nAnnotate every signature.\n'
        outline = '{"outline": [{"section": "Rule", "optional": true}, {"section": "Checklist"}]}'

        #: When
        found = _match_corpus_outline(outline, text)

        #: Then
        misplaced = MisplacedSection(section=_section(text, 'Rule'), expected=None)
        assert found == (OutlineDivergenceSpec(spec=CORPUS_SPEC, divergence=misplaced),), (
            'a named section left over once the outline is used up is out of order, with no section expected there'
        )

    def test_match_outlines_with_an_unnamed_section_left_over_holds_it_unlisted(self) -> None:
        #: Given
        text = '# Typing\n\n## Rule\n\nAnnotate every signature.\n\n## Aside\n\nRead the rationale once.\n'
        outline = '{"outline": [{"section": "Rule"}]}'

        #: When
        found = _match_corpus_outline(outline, text)

        #: Then
        unlisted = UnlistedSection(section=_section(text, 'Aside'), expected=None)
        assert found == (OutlineDivergenceSpec(spec=CORPUS_SPEC, divergence=unlisted),), (
            'an unnamed section left over once the outline is used up is unexpected, past the outline end'
        )

    def test_match_outlines_with_two_outlines_matches_each_on_its_own_in_the_order_given(self) -> None:
        #: Given
        # the corpus outline allows `Aside` in an `any` run, and the namespace outline allows no section past `Rule`
        structure_specs = (
            _structure_spec('code', '{"outline": [{"section": "Rule"}, {"any": true}, {"section": "Checklist"}]}'),
            _structure_spec('code-python', '{"outline": [{"section": "Rule"}]}'),
        )

        #: When
        found = match_outlines(
            structure_specs, parse_document(RULE_ASIDE_CHECKLIST).headings, count_lines(RULE_ASIDE_CHECKLIST)
        )

        #: Then
        unlisted = UnlistedSection(section=_section(RULE_ASIDE_CHECKLIST, 'Aside'), expected=None)
        assert found == (
            OutlineDivergenceSpec(spec=CORPUS_SPEC, divergence=None),
            OutlineDivergenceSpec(spec=NAMESPACE_SPEC, divergence=unlisted),
        ), 'each outline is matched on its own, so the document can follow one and diverge from the other'
