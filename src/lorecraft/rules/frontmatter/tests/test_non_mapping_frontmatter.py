"""`FM003`, `non-mapping-frontmatter`, over a document's or a skill's frontmatter block.

The rule is pure, so every case here is a frontmatter block written as a literal; no file is read.
"""

from typing import Final

import pytest

from lorecraft.core.path import RootRelativePath
from lorecraft.project.aspect import AspectFilename
from lorecraft.project.syntax import LineNumber, MissingFrontmatter
from lorecraft.project.syntax import NonMappingFrontmatter as NonMappingBlock
from lorecraft.rules.inputs import (
    DocumentFrontmatterOwner,
    FrontmatterBlockInput,
    FrontmatterFields,
    NameField,
    SkillFrontmatterOwner,
)
from lorecraft.rules.location import Elsewhere, Note

from ..non_mapping_frontmatter import NonMappingFrontmatter

SPEC: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/guide.structure.json')
"""The structure specification whose frontmatter schema governs the document."""

DOCUMENT: Final[DocumentFrontmatterOwner] = DocumentFrontmatterOwner(filename=AspectFilename.parse('setup'), spec=SPEC)
"""A document `setup` the schema in `SPEC` governs."""

SKILL: Final[SkillFrontmatterOwner] = SkillFrontmatterOwner(directory_name='review', link_target=None)
"""A skill listed as `review`, not through a link."""

NAMED_SETUP: Final[FrontmatterFields] = FrontmatterFields(
    name=NameField(value='setup', line=LineNumber.from_int(2)), repeated_keys=()
)
"""A mapping whose `name` is `setup`, on line 2, and that repeats no key."""


@pytest.mark.unit
class TestNonMappingFrontmatter:
    def test_check_with_a_document_whose_block_is_not_a_mapping_reports_it_on_line_1(self) -> None:
        #: Given
        subject = FrontmatterBlockInput(frontmatter=NonMappingBlock(), owner=DOCUMENT)

        #: When
        occurrences = NonMappingFrontmatter.check(subject)

        #: Then
        assert occurrences == (NonMappingFrontmatter(spec=SPEC, line=LineNumber.from_int(1)),), (
            'a block that is not a mapping is one occurrence, on line 1'
        )

    def test_check_with_a_skill_whose_block_is_not_a_mapping_reports_it_under_no_specification_file(self) -> None:
        #: Given
        subject = FrontmatterBlockInput(frontmatter=NonMappingBlock(), owner=SKILL)

        #: When
        occurrences = NonMappingFrontmatter.check(subject)

        #: Then
        assert occurrences == (NonMappingFrontmatter(spec=None, line=LineNumber.from_int(1)),), (
            'the package states the rule for a skill'
        )

    def test_check_with_a_mapping_reports_nothing(self) -> None:
        #: Given
        subject = FrontmatterBlockInput(frontmatter=NAMED_SETUP, owner=DOCUMENT)

        #: When
        occurrences = NonMappingFrontmatter.check(subject)

        #: Then
        assert occurrences == (), 'a mapping is what the rule asks for'

    def test_check_with_no_block_reports_nothing(self) -> None:
        #: Given
        subject = FrontmatterBlockInput(frontmatter=MissingFrontmatter(), owner=DOCUMENT)

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

    def test_children_with_a_document_point_at_its_specification(self) -> None:
        #: Given
        occurrence = NonMappingFrontmatter(spec=SPEC, line=LineNumber.from_int(1))

        #: When
        children = occurrence.children()

        #: Then
        assert children == (Note('the frontmatter schema is set here', at=Elsewhere(SPEC)),), (
            'a note points at the specification that sets the schema'
        )

    def test_children_with_a_skill_name_the_agent_skills_specification(self) -> None:
        #: Given
        occurrence = NonMappingFrontmatter(spec=None, line=LineNumber.from_int(1))

        #: When
        children = occurrence.children()

        #: Then
        assert children == (Note("the Agent Skills specification governs a SKILL.md's frontmatter"),), (
            'a note names the external specification, with no location'
        )
