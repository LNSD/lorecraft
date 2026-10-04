"""`FM004`, `name-mismatch`, over a document's or a skill's frontmatter block.

The rule is pure, so every case here is a frontmatter block written as a literal; no file is read.
"""

from typing import Final

import pytest

from lorecraft.core.path import ROOT, RootRelativePath
from lorecraft.project.aspect import AspectFilename
from lorecraft.project.syntax import LineNumber, NonMappingFrontmatter
from lorecraft.rules.inputs import (
    DocumentFrontmatterOwner,
    FrontmatterBlockInput,
    FrontmatterFields,
    NameField,
    SkillFrontmatterOwner,
)
from lorecraft.rules.location import Elsewhere, Help, Note
from lorecraft.vfs import ResolvedPath

from ..name_mismatch import DirectoryNameExpected, FilenameExpected, NameMismatch

SPEC: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/guide.structure.json')
"""The structure specification whose frontmatter schema governs the document."""

DOCUMENT: Final[DocumentFrontmatterOwner] = DocumentFrontmatterOwner(filename=AspectFilename.parse('setup'), spec=SPEC)
"""A document `setup` the schema in `SPEC` governs."""

SKILL: Final[SkillFrontmatterOwner] = SkillFrontmatterOwner(directory_name='review', link_target=None)
"""A skill listed as `review`, not through a link."""

SHIPPED: Final[ResolvedPath] = ResolvedPath(RootRelativePath.parse('skills/code-review'))
"""The directory a linked skill directory leads to, named otherwise than the listed one."""


def _named(value: object, line: int) -> FrontmatterFields:
    """A mapping that writes `name` once, with this value, on this line, and repeats no key.

    Args:
        value: The `name` as YAML decoded it.
        line: The line the `name` key is written on.
    """
    return FrontmatterFields(name=NameField(value=value, line=LineNumber.from_int(line)), repeated_keys=())


@pytest.mark.unit
class TestNameMismatch:
    def test_check_with_a_document_named_otherwise_reports_it_on_the_name_line(self) -> None:
        #: Given
        subject = FrontmatterBlockInput(frontmatter=_named('installation', 3), owner=DOCUMENT)

        #: When
        occurrences = NameMismatch.check(subject)

        #: Then
        assert occurrences == (
            NameMismatch(
                spec=SPEC, line=LineNumber.from_int(3), name='installation', expectation=FilenameExpected('setup')
            ),
        ), 'a name other than the filename is one occurrence, on the line the input locates `name` at'

    def test_check_with_a_document_named_for_its_filename_reports_nothing(self) -> None:
        #: Given
        subject = FrontmatterBlockInput(frontmatter=_named('setup', 2), owner=DOCUMENT)

        #: When
        occurrences = NameMismatch.check(subject)

        #: Then
        assert occurrences == (), 'a name equal to the filename holds to the rule'

    def test_check_with_a_document_without_a_name_reports_nothing(self) -> None:
        #: Given
        subject = FrontmatterBlockInput(frontmatter=FrontmatterFields(name=None, repeated_keys=()), owner=DOCUMENT)

        #: When
        occurrences = NameMismatch.check(subject)

        #: Then
        assert occurrences == (), "a missing `name` is the schema's to report, never this rule's"

    def test_check_with_a_name_that_is_not_a_string_reports_nothing(self) -> None:
        #: Given
        subject = FrontmatterBlockInput(frontmatter=_named(42, 2), owner=SKILL)

        #: When
        occurrences = NameMismatch.check(subject)

        #: Then
        assert occurrences == (), "a `name` of another type is the schema's to report, never this rule's"

    def test_check_with_a_block_that_is_not_a_mapping_reports_nothing(self) -> None:
        #: Given
        subject = FrontmatterBlockInput(frontmatter=NonMappingFrontmatter(), owner=DOCUMENT)

        #: When
        occurrences = NameMismatch.check(subject)

        #: Then
        assert occurrences == (), 'a block that is not a mapping has no `name` to compare'

    def test_check_with_a_skill_named_otherwise_reports_it_with_its_link_target(self) -> None:
        #: Given
        owner = SkillFrontmatterOwner(directory_name='review', link_target=SHIPPED)
        subject = FrontmatterBlockInput(frontmatter=_named('code-review', 2), owner=owner)

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
