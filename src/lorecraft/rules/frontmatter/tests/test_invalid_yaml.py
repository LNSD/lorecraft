"""`FM002`, `invalid-yaml`, over a document's or a skill's frontmatter.

Every case is a document or a `SKILL.md` written as text, read through a fake context that parses its frontmatter as
the real parser does; no file is read from disk.
"""

import sys
from typing import Final

import pytest

from lorecraft.core.path import RootRelativePath
from lorecraft.project.syntax import LineNumber
from lorecraft.rules.location import Elsewhere, Note
from lorecraft.rules.tests.fake_context import FakeDocumentContext, FakeSkillContext, structure_spec_path

from ..invalid_yaml import InvalidYaml

STRUCTURE: Final[str] = '{"frontmatter": {"type": "object"}}'
"""A corpus structure specification whose frontmatter schema accepts any mapping."""

SPEC: Final[RootRelativePath] = structure_spec_path('guide')
"""Where the corpus structure specification lies."""


@pytest.mark.unit
class TestInvalidYaml:
    def test_check_with_a_block_that_is_not_yaml_reports_it_at_the_line_the_parser_names(self) -> None:
        #: Given
        text = '---\nname: setup\ndescription: Setup: install the toolkit\n---\n# Setup\n'
        subject = FakeDocumentContext(text, corpus='guide', structure=STRUCTURE)

        #: When
        occurrences = InvalidYaml.check(subject)

        #: Then
        assert occurrences == (
            InvalidYaml(spec=SPEC, line=LineNumber.from_int(3), problem='mapping values are not allowed here'),
        ), 'the occurrence is on the line the YAML parser stopped on, with its words'

    def test_check_with_no_line_known_reports_it_on_line_1(self) -> None:
        #: Given
        # reading spends at least one frame per level, so as many levels as the recursion limit always exhaust the
        # stack, and the parser can name no line
        depth = sys.getrecursionlimit()
        block = 'name: review\n' + ''.join(f'{" " * level}nested:\n' for level in range(depth)) + f'{" " * depth}a: b\n'
        subject = FakeSkillContext(f'---\n{block}---\n')

        #: When
        occurrences = InvalidYaml.check(subject)

        #: Then
        assert occurrences == (
            InvalidYaml(spec=None, line=LineNumber.from_int(1), problem='found collections nested too deeply to parse'),
        ), 'a problem at no known line is reported on line 1; a skill under no specification file'

    def test_check_with_a_mapping_reports_nothing(self) -> None:
        #: Given
        subject = FakeDocumentContext('---\nname: setup\n---\n# Setup\n', corpus='guide', structure=STRUCTURE)

        #: When
        occurrences = InvalidYaml.check(subject)

        #: Then
        assert occurrences == (), 'a block that reads as YAML is not invalid-yaml'

    def test_check_with_no_block_reports_nothing(self) -> None:
        #: Given
        subject = FakeSkillContext('# Review\n')

        #: When
        occurrences = InvalidYaml.check(subject)

        #: Then
        assert occurrences == (), 'a missing block is missing-frontmatter, never invalid-yaml'

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
