"""`FM002`, `invalid-yaml`, over a document's or a skill's frontmatter block.

The rule is pure, so every case here is a frontmatter block written as a literal; no file is read.
"""

from typing import Final

import pytest

from lorecraft.core.path import RootRelativePath
from lorecraft.project.aspect import AspectFilename
from lorecraft.project.context import DocumentFrontmatterOwner, SkillFrontmatterOwner
from lorecraft.project.syntax import InvalidYamlFrontmatter, LineNumber
from lorecraft.rules.inputs import FrontmatterBlockInput, FrontmatterFields, NameField
from lorecraft.rules.location import Elsewhere, Note

from ..invalid_yaml import InvalidYaml

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
class TestInvalidYaml:
    def test_check_with_a_block_that_is_not_yaml_reports_it_at_the_line_the_parser_names(self) -> None:
        #: Given
        frontmatter = InvalidYamlFrontmatter(problem='mapping values are not allowed here', line=LineNumber.from_int(3))
        subject = FrontmatterBlockInput(frontmatter=frontmatter, owner=DOCUMENT)

        #: When
        occurrences = InvalidYaml.check(subject)

        #: Then
        assert occurrences == (
            InvalidYaml(spec=SPEC, line=LineNumber.from_int(3), problem='mapping values are not allowed here'),
        ), 'the occurrence is on the line the YAML parser stopped on, with its words'

    def test_check_with_no_line_known_reports_it_on_line_1(self) -> None:
        #: Given
        frontmatter = InvalidYamlFrontmatter(problem='collections nested too deeply', line=None)
        subject = FrontmatterBlockInput(frontmatter=frontmatter, owner=SKILL)

        #: When
        occurrences = InvalidYaml.check(subject)

        #: Then
        assert occurrences == (
            InvalidYaml(spec=None, line=LineNumber.from_int(1), problem='collections nested too deeply'),
        ), 'a problem at no known line is reported on line 1; a skill under no specification file'

    def test_check_with_a_mapping_reports_nothing(self) -> None:
        #: Given
        subject = FrontmatterBlockInput(frontmatter=NAMED_SETUP, owner=DOCUMENT)

        #: When
        occurrences = InvalidYaml.check(subject)

        #: Then
        assert occurrences == (), 'a block that reads as YAML is not invalid-yaml'

    def test_message_with_an_occurrence_names_the_parser_problem(self) -> None:
        #: Given
        occurrence = InvalidYaml(spec=SPEC, line=LineNumber.from_int(3), problem='mapping values are not allowed here')

        #: When
        message = occurrence.message()

        #: Then
        assert message == 'frontmatter is not valid YAML (mapping values are not allowed here)', (
            "the message carries the parser's words in parentheses"
        )

    def test_children_with_a_document_point_at_its_specification(self) -> None:
        #: Given
        occurrence = InvalidYaml(spec=SPEC, line=LineNumber.from_int(3), problem='mapping values are not allowed here')

        #: When
        children = occurrence.children()

        #: Then
        assert children == (Note('the frontmatter schema is set here', at=Elsewhere(SPEC)),), (
            'a note points at the specification that sets the schema'
        )

    def test_children_with_a_skill_name_the_agent_skills_specification(self) -> None:
        #: Given
        occurrence = InvalidYaml(spec=None, line=LineNumber.from_int(3), problem='mapping values are not allowed here')

        #: When
        children = occurrence.children()

        #: Then
        assert children == (Note("the Agent Skills specification governs a SKILL.md's frontmatter"),), (
            'a note names the external specification, with no location'
        )
