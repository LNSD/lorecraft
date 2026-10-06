"""`FM001`, `missing-frontmatter`, over a document's or a skill's frontmatter block.

The rule is pure, so every case here is a frontmatter block written as a literal; no file is read.
"""

from typing import Final

import pytest

from lorecraft.core.path import RootRelativePath
from lorecraft.project.aspect import AspectFilename
from lorecraft.project.context import DocumentFrontmatterOwner, SkillFrontmatterOwner
from lorecraft.project.syntax import InvalidYamlFrontmatter, LineNumber
from lorecraft.project.syntax import MissingFrontmatter as MissingBlock
from lorecraft.rules.inputs import FrontmatterBlockInput, FrontmatterFields, NameField
from lorecraft.rules.location import Elsewhere, Note

from ..missing_frontmatter import MissingFrontmatter

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
class TestMissingFrontmatter:
    def test_check_with_a_document_without_a_block_reports_it_on_line_1(self) -> None:
        #: Given
        subject = FrontmatterBlockInput(frontmatter=MissingBlock(), owner=DOCUMENT)

        #: When
        occurrences = MissingFrontmatter.check(subject)

        #: Then
        assert occurrences == (MissingFrontmatter(spec=SPEC, line=LineNumber.from_int(1)),), (
            "a document with no block is one occurrence, on line 1, under its corpus's specification"
        )

    def test_check_with_a_skill_without_a_block_reports_it_under_no_specification_file(self) -> None:
        #: Given
        subject = FrontmatterBlockInput(frontmatter=MissingBlock(), owner=SKILL)

        #: When
        occurrences = MissingFrontmatter.check(subject)

        #: Then
        assert occurrences == (MissingFrontmatter(spec=None, line=LineNumber.from_int(1)),), (
            'the package states the rule for a skill, after the Agent Skills specification'
        )

    def test_check_with_a_block_that_is_not_yaml_reports_nothing(self) -> None:
        #: Given
        frontmatter = InvalidYamlFrontmatter(problem='unexpected end of stream', line=LineNumber.from_int(3))
        subject = FrontmatterBlockInput(frontmatter=frontmatter, owner=DOCUMENT)

        #: When
        occurrences = MissingFrontmatter.check(subject)

        #: Then
        assert occurrences == (), 'a block that is there but not YAML is invalid-yaml, never missing-frontmatter'

    def test_check_with_a_mapping_reports_nothing(self) -> None:
        #: Given
        subject = FrontmatterBlockInput(frontmatter=NAMED_SETUP, owner=DOCUMENT)

        #: When
        occurrences = MissingFrontmatter.check(subject)

        #: Then
        assert occurrences == (), 'a block that decoded to a mapping is there'

    def test_message_with_an_occurrence_names_the_missing_block(self) -> None:
        #: Given
        occurrence = MissingFrontmatter(spec=SPEC, line=LineNumber.from_int(1))

        #: When
        message = occurrence.message()

        #: Then
        assert message == 'no `---` delimited frontmatter block', 'the message names the block that is missing'

    def test_children_with_a_document_point_at_its_specification(self) -> None:
        #: Given
        occurrence = MissingFrontmatter(spec=SPEC, line=LineNumber.from_int(1))

        #: When
        children = occurrence.children()

        #: Then
        assert children == (Note('the frontmatter schema is set here', at=Elsewhere(SPEC)),), (
            'a note points at the specification that sets the schema'
        )

    def test_children_with_a_skill_name_the_agent_skills_specification(self) -> None:
        #: Given
        occurrence = MissingFrontmatter(spec=None, line=LineNumber.from_int(1))

        #: When
        children = occurrence.children()

        #: Then
        assert children == (Note("the Agent Skills specification governs a SKILL.md's frontmatter"),), (
            'a note names the external specification, with no location, since no file in the repository holds it'
        )
