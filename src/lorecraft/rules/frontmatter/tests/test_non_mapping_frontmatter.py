"""`FM003`, `non-mapping-frontmatter`, over a document's or a skill's frontmatter.

Every case is a document or a `SKILL.md` written as text, read through a fake context that parses its frontmatter as
the real parser does; no file is read from disk.
"""

from typing import Final

import pytest

from lorecraft.core.path import RootRelativePath
from lorecraft.project.syntax import LineNumber
from lorecraft.rules.location import Elsewhere, Help, Note
from lorecraft.rules.tests.fake_context import FakeDocumentContext, FakeSkillContext, structure_spec_path

from ..non_mapping_frontmatter import NonMappingFrontmatter

STRUCTURE: Final[str] = '{"frontmatter": {"type": "object"}}'
"""A corpus structure specification whose frontmatter schema accepts any mapping."""

SPEC: Final[RootRelativePath] = structure_spec_path('guide')
"""Where the corpus structure specification lies."""


@pytest.mark.unit
class TestNonMappingFrontmatter:
    def test_check_with_a_document_whose_block_is_a_list_reports_it_on_line_1(self) -> None:
        #: Given
        subject = FakeDocumentContext('---\n- setup\n---\n# Setup\n', corpus='guide', structure=STRUCTURE)

        #: When
        occurrences = NonMappingFrontmatter.check(subject)

        #: Then
        assert occurrences == (NonMappingFrontmatter(spec=SPEC, line=LineNumber.from_int(1)),), (
            'a block that is not a mapping is one occurrence, on line 1'
        )

    def test_check_with_an_empty_block_reports_it_on_line_1(self) -> None:
        #: Given
        subject = FakeDocumentContext('---\n---\n# Setup\n', corpus='guide', structure=STRUCTURE)

        #: When
        occurrences = NonMappingFrontmatter.check(subject)

        #: Then
        assert occurrences == (NonMappingFrontmatter(spec=SPEC, line=LineNumber.from_int(1)),), (
            'an empty block holds no mapping, so it is not a mapping either'
        )

    def test_check_with_a_skill_whose_block_is_not_a_mapping_reports_it_under_no_specification_file(self) -> None:
        #: Given
        subject = FakeSkillContext('---\n- review\n---\n')

        #: When
        occurrences = NonMappingFrontmatter.check(subject)

        #: Then
        assert occurrences == (NonMappingFrontmatter(spec=None, line=LineNumber.from_int(1)),), (
            'the package states the rule for a skill'
        )

    def test_check_with_a_mapping_reports_nothing(self) -> None:
        #: Given
        subject = FakeDocumentContext('---\nname: setup\n---\n# Setup\n', corpus='guide', structure=STRUCTURE)

        #: When
        occurrences = NonMappingFrontmatter.check(subject)

        #: Then
        assert occurrences == (), 'a mapping is what the rule asks for'

    def test_check_with_no_block_reports_nothing(self) -> None:
        #: Given
        subject = FakeDocumentContext('# Setup\n', corpus='guide', structure=STRUCTURE)

        #: When
        occurrences = NonMappingFrontmatter.check(subject)

        #: Then
        assert occurrences == (), 'a missing block is missing-frontmatter, never non-mapping-frontmatter'

    def test_message_with_an_occurrence_names_what_the_block_is_not(self) -> None:
        #: Given
        occurrence = NonMappingFrontmatter(spec=SPEC, line=LineNumber.from_int(1))

        #: When
        message = occurrence.message()

        #: Then
        assert message == 'frontmatter is not a YAML mapping', 'the message names what the block is not'

    def test_children_with_a_document_point_at_its_specification_and_say_what_a_mapping_is(self) -> None:
        #: Given
        occurrence = NonMappingFrontmatter(spec=SPEC, line=LineNumber.from_int(1))

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Note('the frontmatter schema is set here', at=Elsewhere(SPEC)),
            Help('write the block as `key: value` lines'),
        ), 'a note points at the specification that sets the schema, then a help says what a mapping looks like'

    def test_children_with_a_skill_name_the_agent_skills_specification(self) -> None:
        #: Given
        occurrence = NonMappingFrontmatter(spec=None, line=LineNumber.from_int(1))

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Note("the Agent Skills specification governs a SKILL.md's frontmatter"),
            Help('write the block as `key: value` lines'),
        ), 'a note names the external specification, with no location, then the same help'
