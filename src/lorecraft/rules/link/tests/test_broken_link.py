"""`LINK003`, `broken-link`, over the relative links of one Markdown file and what the snapshot holds at each target.

Every case is a Markdown file written as text and parsed by the real parser, through a fake context: a skill's
resource, whose links are read from the skill root, or a document, whose links are read from its own directory. What
the snapshot holds at each link's target is a cross-file state, so the test states it by hand, keyed by the link's
normalised relative path; where each link leads is `find_link_targets`'s, tested beside it.
"""

from pathlib import PurePosixPath

import pytest

from lorecraft.core.mapping import FrozenMapping
from lorecraft.project.link_target import DocumentDirectory, PathLookup, SkillRoot
from lorecraft.project.syntax import LineNumber
from lorecraft.rules.location import Help
from lorecraft.rules.tests.fake_context import (
    DEFAULT_DOCUMENT_DIRECTORY,
    DEFAULT_SKILL_DIRECTORY,
    FakeDocumentMarkdownContext,
    FakeSkillResourceContext,
)

from ..broken_link import BrokenLink

SKILL_ROOT: SkillRoot = SkillRoot(DEFAULT_SKILL_DIRECTORY)
"""Where a fake resource's relative links are read from."""

DOCUMENT_DIRECTORY: DocumentDirectory = DocumentDirectory(DEFAULT_DOCUMENT_DIRECTORY)
"""Where a fake document's relative links are read from."""


def _targets(path: str, lookup: PathLookup) -> FrozenMapping[PurePosixPath, PathLookup]:
    """The link targets of a file with one relative path, holding what the snapshot holds there.

    Args:
        path: The link's normalised relative path, as the key of its entry.
        lookup: What the snapshot holds at the link's target.
    """
    return FrozenMapping({PurePosixPath(path): lookup})


@pytest.mark.unit
class TestBrokenLinkInASkill:
    def test_check_with_a_link_whose_target_is_missing_reports_it_on_its_line(self) -> None:
        #: Given
        subject = FakeSkillResourceContext(
            '# Guide\n\nSee [a](references/a.md).\n', link_targets=_targets('references/a.md', PathLookup.MISSING)
        )

        #: When
        occurrences = BrokenLink.check(subject)

        #: Then
        assert occurrences == (BrokenLink(line=LineNumber.from_int(3), url='references/a.md', base=SKILL_ROOT),), (
            'a link whose target holds nothing is one occurrence, on the line the link is on'
        )

    def test_check_with_a_link_whose_target_is_present_reports_nothing(self) -> None:
        #: Given
        subject = FakeSkillResourceContext(
            '# Guide\n\nSee [a](references/a.md).\n', link_targets=_targets('references/a.md', PathLookup.PRESENT)
        )

        #: When
        occurrences = BrokenLink.check(subject)

        #: Then
        assert occurrences == (), 'a link to a file or a directory the snapshot holds goes somewhere'

    def test_check_with_a_link_whose_target_is_outside_the_scope_reports_nothing(self) -> None:
        #: Given
        subject = FakeSkillResourceContext(
            '# Guide\n\nSee [x](shared/x.md).\n', link_targets=_targets('shared/x.md', PathLookup.OUTSIDE_SCOPE)
        )

        #: When
        occurrences = BrokenLink.check(subject)

        #: Then
        assert occurrences == (), 'whether a target the scan never read holds anything cannot be told'

    def test_check_with_a_link_having_no_target_entry_reports_nothing(self) -> None:
        #: Given
        # A link climbing above the skill root has no entry.
        subject = FakeSkillResourceContext('# Guide\n\nSee [up](../SKILL.md).\n')

        #: When
        occurrences = BrokenLink.check(subject)

        #: Then
        assert occurrences == (), (
            'a link with no target entry, such as one climbing above the skill root, is not judged'
        )

    def test_check_with_links_spelling_no_relative_path_reports_nothing(self) -> None:
        #: Given
        subject = FakeSkillResourceContext(
            '# Guide\n\nSee [site](https://example.com/a.md), [abs](/a.md) and [top](#guide).\n'
        )

        #: When
        occurrences = BrokenLink.check(subject)

        #: Then
        assert occurrences == (), 'a URL, an absolute link and a fragment-only link name no target'

    def test_check_with_a_link_spelled_unnormalised_finds_its_entry_by_the_normalised_path(self) -> None:
        #: Given
        subject = FakeSkillResourceContext(
            '# Guide\n\nSee [a](references/./a.md).\n', link_targets=_targets('references/a.md', PathLookup.MISSING)
        )

        #: When
        occurrences = BrokenLink.check(subject)

        #: Then
        assert occurrences == (BrokenLink(line=LineNumber.from_int(3), url='references/./a.md', base=SKILL_ROOT),), (
            'the entry is keyed by the normalised path, and the occurrence keeps the destination as written'
        )

    def test_check_with_a_query_after_a_missing_path_reports_the_whole_destination(self) -> None:
        #: Given
        subject = FakeSkillResourceContext(
            '# Guide\n\nSee [b](b.md?raw=1).\n', link_targets=_targets('b.md', PathLookup.MISSING)
        )

        #: When
        occurrences = BrokenLink.check(subject)

        #: Then
        assert occurrences == (BrokenLink(line=LineNumber.from_int(3), url='b.md?raw=1', base=SKILL_ROOT),), (
            'the query is no part of the path, and the occurrence keeps the destination as written'
        )


@pytest.mark.unit
class TestBrokenLinkInADocument:
    def test_check_with_a_link_whose_target_is_missing_reports_it_on_its_line(self) -> None:
        #: Given
        subject = FakeDocumentMarkdownContext(
            '# Setup\n\nRun [install](install.md) first.\n', link_targets=_targets('install.md', PathLookup.MISSING)
        )

        #: When
        occurrences = BrokenLink.check(subject)

        #: Then
        assert occurrences == (BrokenLink(line=LineNumber.from_int(3), url='install.md', base=DOCUMENT_DIRECTORY),), (
            "a document's link whose target holds nothing is one occurrence, read from the document's directory"
        )

    def test_check_with_a_link_whose_target_is_present_reports_nothing(self) -> None:
        #: Given
        subject = FakeDocumentMarkdownContext(
            '# Setup\n\nRun [install](install.md) first.\n', link_targets=_targets('install.md', PathLookup.PRESENT)
        )

        #: When
        occurrences = BrokenLink.check(subject)

        #: Then
        assert occurrences == (), 'a link to a file the snapshot holds goes somewhere'


@pytest.mark.unit
class TestBrokenLinkDiagnostic:
    def test_message_with_a_link_in_a_skill_names_the_decoded_destination_and_the_skill(self) -> None:
        #: Given
        occurrence = BrokenLink(line=LineNumber.from_int(3), url='a%20b.md', base=SKILL_ROOT)

        #: When
        message = occurrence.message()

        #: Then
        assert message == '`a b.md` names nothing in the skill', 'the destination shows percent-decoded'

    def test_message_with_a_link_in_a_document_names_the_repository(self) -> None:
        #: Given
        occurrence = BrokenLink(line=LineNumber.from_int(3), url='install.md', base=DOCUMENT_DIRECTORY)

        #: When
        message = occurrence.message()

        #: Then
        assert message == '`install.md` names nothing in the repository', (
            'a document names files of the repository, not of a skill'
        )

    def test_children_with_a_link_in_a_skill_say_to_link_relative_to_the_skill_root(self) -> None:
        #: Given
        occurrence = BrokenLink(line=LineNumber.from_int(3), url='a.md', base=SKILL_ROOT)

        #: When
        children = occurrence.children()

        #: Then
        assert children == (Help('link a file or a directory the skill holds, relative to the skill root'),), (
            'a help says what a link in a skill may name, and where it is read from'
        )

    def test_children_with_a_link_in_a_document_say_to_link_relative_to_the_file(self) -> None:
        #: Given
        occurrence = BrokenLink(line=LineNumber.from_int(3), url='install.md', base=DOCUMENT_DIRECTORY)

        #: When
        children = occurrence.children()

        #: Then
        assert children == (Help('link a file or a directory the repository holds, relative to this file'),), (
            'a help says what a link in a document may name, and where it is read from'
        )
