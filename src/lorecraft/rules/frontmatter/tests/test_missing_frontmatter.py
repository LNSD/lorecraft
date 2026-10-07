"""`FM001`, `missing-frontmatter`, over a document's or a skill's frontmatter.

Every case is a document or a `SKILL.md` written as text, read through a fake context that parses its frontmatter as
the real parser does; no file is read from disk.
"""

from typing import Final

import pytest

from lorecraft.core.path import RootRelativePath
from lorecraft.project.syntax import LineNumber
from lorecraft.rules.location import Elsewhere, Help, Here, Label, Note
from lorecraft.rules.tests.fake_context import FakeDocumentContext, FakeSkillContext, structure_spec_path

from ..missing_frontmatter import MissingFrontmatter

STRUCTURE: Final[str] = '{"frontmatter": {"type": "object"}}'
"""A corpus structure specification whose frontmatter schema accepts any mapping."""

SPEC: Final[RootRelativePath] = structure_spec_path('guide')
"""Where the corpus structure specification lies."""


@pytest.mark.unit
class TestMissingFrontmatter:
    def test_check_with_a_document_without_a_block_reports_it_on_line_1(self) -> None:
        #: Given
        subject = FakeDocumentContext('# Setup\n', corpus='guide', structure=STRUCTURE)

        #: When
        occurrences = MissingFrontmatter.check(subject)

        #: Then
        assert occurrences == (MissingFrontmatter(spec=SPEC, line=LineNumber.from_int(1), directory_name=None),), (
            "a document with no block is one occurrence, on line 1, under its corpus's specification"
        )

    def test_check_with_a_block_never_closed_reports_it_on_line_1(self) -> None:
        #: Given
        subject = FakeDocumentContext('---\nname: setup\n# Setup\n', corpus='guide', structure=STRUCTURE)

        #: When
        occurrences = MissingFrontmatter.check(subject)

        #: Then
        assert occurrences == (MissingFrontmatter(spec=SPEC, line=LineNumber.from_int(1), directory_name=None),), (
            'a block no second `---` line closes is no block at all'
        )

    def test_check_with_a_skill_without_a_block_reports_it_under_no_specification_file(self) -> None:
        #: Given
        subject = FakeSkillContext('# Review\n', directory_name='review')

        #: When
        occurrences = MissingFrontmatter.check(subject)

        #: Then
        assert occurrences == (MissingFrontmatter(spec=None, line=LineNumber.from_int(1), directory_name='review'),), (
            'the package states the rule for a skill, after the Agent Skills specification'
        )

    def test_check_with_a_block_that_is_not_yaml_reports_nothing(self) -> None:
        #: Given
        subject = FakeDocumentContext('---\nname: [setup\n---\n# Setup\n', corpus='guide', structure=STRUCTURE)

        #: When
        occurrences = MissingFrontmatter.check(subject)

        #: Then
        assert occurrences == (), 'a block that is there but not YAML is invalid-yaml, never missing-frontmatter'

    def test_check_with_a_mapping_reports_nothing(self) -> None:
        #: Given
        subject = FakeDocumentContext('---\nname: setup\n---\n# Setup\n', corpus='guide', structure=STRUCTURE)

        #: When
        occurrences = MissingFrontmatter.check(subject)

        #: Then
        assert occurrences == (), 'a block that decoded to a mapping is there'

    def test_message_with_an_occurrence_names_the_missing_block(self) -> None:
        #: Given
        occurrence = MissingFrontmatter(spec=SPEC, line=LineNumber.from_int(1), directory_name=None)

        #: When
        message = occurrence.message()

        #: Then
        assert message == 'no `---` delimited frontmatter block', 'the message names the block that is missing'

    def test_labels_with_an_occurrence_say_the_file_must_open_with_a_delimiter(self) -> None:
        #: Given
        occurrence = MissingFrontmatter(spec=SPEC, line=LineNumber.from_int(1), directory_name=None)

        #: When
        labels = occurrence.labels()

        #: Then
        assert labels == (Label(Here(LineNumber.from_int(1)), 'a `---` delimited block is expected here'),), (
            'the label is on line 1, where the delimiter is missing'
        )

    def test_children_with_a_document_point_at_its_specification_and_say_how_to_open_the_block(self) -> None:
        #: Given
        occurrence = MissingFrontmatter(spec=SPEC, line=LineNumber.from_int(1), directory_name=None)

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Note('the frontmatter schema is set here', at=Elsewhere(SPEC)),
            Help('open the file with a `---` line, the fields, and a closing `---` line'),
        ), "a document lists none of its fields: the required ones are not this rule's input"

    def test_children_with_a_skill_name_the_agent_skills_specification_and_show_the_skeleton(self) -> None:
        #: Given
        occurrence = MissingFrontmatter(spec=None, line=LineNumber.from_int(1), directory_name='review')

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Note("the Agent Skills specification governs a SKILL.md's frontmatter"),
            Help('open the file with a `---` line, the fields, and a closing `---` line'),
            Note('for example:\n---\nname: review\ndescription: …\n---'),
        ), 'the specification note has no location, since no file holds it, and the skeleton names the directory'
