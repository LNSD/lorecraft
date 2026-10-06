"""`FM004`, `name-mismatch`, over a document's or a skill's frontmatter.

Every case is a document or a `SKILL.md` written as text, read through a fake context that parses its frontmatter as
the real parser does; no file is read from disk. The name a document is held to is the fake's filename, `setup`, and
the name a skill is held to the directory the fake lists it under, `review`.
"""

from typing import Final

import pytest

from lorecraft.core.path import ROOT, RootRelativePath
from lorecraft.project.syntax import LineNumber
from lorecraft.rules.location import Elsewhere, Help, Note
from lorecraft.rules.tests.fake_context import FakeDocumentContext, FakeSkillContext, structure_spec_path
from lorecraft.vfs import ResolvedPath

from ..name_mismatch import DirectoryNameExpected, FilenameExpected, NameMismatch

STRUCTURE: Final[str] = '{"frontmatter": {"type": "object"}}'
"""A corpus structure specification whose frontmatter schema accepts any mapping."""

SPEC: Final[RootRelativePath] = structure_spec_path('guide')
"""Where the corpus structure specification lies."""

SHIPPED: Final[ResolvedPath] = ResolvedPath(RootRelativePath.parse('skills/code-review'))
"""The directory a linked skill directory leads to, named otherwise than the listed one."""


@pytest.mark.unit
class TestNameMismatch:
    def test_check_with_a_document_named_otherwise_reports_it_on_the_name_line(self) -> None:
        #: Given
        text = '---\ndescription: Install the toolkit.\nname: installation\n---\n# Setup\n'
        subject = FakeDocumentContext(text, corpus='guide', structure=STRUCTURE)

        #: When
        occurrences = NameMismatch.check(subject)

        #: Then
        assert occurrences == (
            NameMismatch(
                spec=SPEC, line=LineNumber.from_int(3), name='installation', expectation=FilenameExpected('setup')
            ),
        ), 'a name other than the filename is one occurrence, on the line the `name` key is written on'

    def test_check_with_a_name_written_twice_reports_the_last_value_on_its_line(self) -> None:
        #: Given
        text = '---\nname: setup\nmetadata:\n  name: inner\nname: installation\n---\n# Setup\n'
        subject = FakeDocumentContext(text, corpus='guide', structure=STRUCTURE)

        #: When
        occurrences = NameMismatch.check(subject)

        #: Then
        assert occurrences == (
            NameMismatch(
                spec=SPEC, line=LineNumber.from_int(5), name='installation', expectation=FilenameExpected('setup')
            ),
        ), 'YAML keeps the last value of a repeated key, so that value is compared, on its line; a nested key is not it'

    def test_check_with_a_document_named_for_its_filename_reports_nothing(self) -> None:
        #: Given
        subject = FakeDocumentContext('---\nname: setup\n---\n# Setup\n', corpus='guide', structure=STRUCTURE)

        #: When
        occurrences = NameMismatch.check(subject)

        #: Then
        assert occurrences == (), 'a name equal to the filename holds to the rule'

    def test_check_with_a_document_without_a_name_reports_nothing(self) -> None:
        #: Given
        subject = FakeDocumentContext('---\ntitle: Setup\n---\n# Setup\n', corpus='guide', structure=STRUCTURE)

        #: When
        occurrences = NameMismatch.check(subject)

        #: Then
        assert occurrences == (), "a missing `name` is the schema's to report, never this rule's"

    def test_check_with_a_name_that_is_not_a_string_reports_nothing(self) -> None:
        #: Given
        subject = FakeSkillContext('---\nname: 42\n---\n')

        #: When
        occurrences = NameMismatch.check(subject)

        #: Then
        assert occurrences == (), "a `name` of another type is the schema's to report, never this rule's"

    def test_check_with_a_block_that_is_not_a_mapping_reports_nothing(self) -> None:
        #: Given
        subject = FakeDocumentContext('---\n- installation\n---\n# Setup\n', corpus='guide', structure=STRUCTURE)

        #: When
        occurrences = NameMismatch.check(subject)

        #: Then
        assert occurrences == (), 'a block that is not a mapping has no `name` to compare'

    def test_check_with_a_skill_named_for_its_directory_reports_nothing(self) -> None:
        #: Given
        subject = FakeSkillContext('---\nname: review\n---\n')

        #: When
        occurrences = NameMismatch.check(subject)

        #: Then
        assert occurrences == (), 'a name equal to the listed directory name holds to the rule'

    def test_check_with_a_skill_named_otherwise_reports_it_with_its_link_target(self) -> None:
        #: Given
        subject = FakeSkillContext('---\nname: code-review\n---\n', link_target=SHIPPED)

        #: When
        occurrences = NameMismatch.check(subject)

        #: Then
        assert occurrences == (
            NameMismatch(
                spec=None,
                line=LineNumber.from_int(2),
                name='code-review',
                expectation=DirectoryNameExpected(directory_name='review', link_target=SHIPPED),
            ),
        ), 'a skill is held to the name it is listed under, never to the name of the directory a link leads to'

    def test_message_with_an_occurrence_names_the_name_against_the_expected_one(self) -> None:
        #: Given
        occurrence = NameMismatch(
            spec=SPEC, line=LineNumber.from_int(2), name='installation', expectation=FilenameExpected('setup')
        )

        #: When
        message = occurrence.message()

        #: Then
        assert message == "`name` is 'installation', expected 'setup'", (
            'the message sets the name against the one expected'
        )

    def test_children_with_a_document_name_the_filename_and_the_specification(self) -> None:
        #: Given
        occurrence = NameMismatch(
            spec=SPEC, line=LineNumber.from_int(2), name='installation', expectation=FilenameExpected('setup')
        )

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Note("a document's `name` must be its filename"),
            Note('the frontmatter schema is set here', at=Elsewhere(SPEC)),
            Help("set `name` to 'setup'"),
        ), 'notes say which name is expected and where the schema is set, a help gives the name to write'

    def test_children_with_a_skill_reached_through_a_link_name_where_it_leads(self) -> None:
        #: Given
        expectation = DirectoryNameExpected(directory_name='review', link_target=SHIPPED)
        occurrence = NameMismatch(spec=None, line=LineNumber.from_int(2), name='code-review', expectation=expectation)

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Note('the Agent Skills specification requires `name` to match the skill directory name'),
            Note("'review' is a link to 'skills/code-review'"),
            Help("set `name` to 'review'"),
        ), 'a skill whose listed directory links to one named otherwise carries a note naming where it leads'

    def test_children_with_a_skill_linked_to_a_directory_of_the_same_name_carry_no_link_note(self) -> None:
        #: Given
        same_name = ResolvedPath(RootRelativePath.parse('skills/review'))
        expectation = DirectoryNameExpected(directory_name='review', link_target=same_name)
        occurrence = NameMismatch(spec=None, line=LineNumber.from_int(2), name='code-review', expectation=expectation)

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Note('the Agent Skills specification requires `name` to match the skill directory name'),
            Help("set `name` to 'review'"),
        ), 'a link to a directory of the listed name explains nothing, so no note names it'

    def test_children_with_a_skill_linked_to_the_root_name_the_repository_root(self) -> None:
        #: Given
        expectation = DirectoryNameExpected(directory_name='review', link_target=ResolvedPath(ROOT))
        occurrence = NameMismatch(spec=None, line=LineNumber.from_int(2), name='code-review', expectation=expectation)

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Note('the Agent Skills specification requires `name` to match the skill directory name'),
            Note("'review' is a link to the repository root"),
            Help("set `name` to 'review'"),
        ), 'the root, whose own name is empty, is named as such'
