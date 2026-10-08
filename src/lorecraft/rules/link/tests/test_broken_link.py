"""`LINK003`, `broken-link`, over the relative links of one Markdown file and what the snapshot holds at each target.

Every case is a Markdown file written as text and parsed by the real parser, through a fake context: a skill's
resource, whose links are read from the skill root, or a document, whose links are read from its own directory. What
the snapshot holds at each link's target is a cross-file state, so the test states it by hand, keyed by the link's
normalised relative path; where each link leads is `find_link_targets`'s, tested beside it.
"""

from pathlib import PurePosixPath

import pytest

from lorecraft.core.mapping import FrozenMapping
from lorecraft.core.path import RootRelativePath
from lorecraft.project.link_target import DocumentDirectory, LinkTarget, PathLookup, SkillRoot
from lorecraft.project.syntax import LineNumber
from lorecraft.rules.location import Help, Note
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


def _targets(
    base: SkillRoot | DocumentDirectory, path: str, lookup: PathLookup
) -> FrozenMapping[PurePosixPath, LinkTarget]:
    """The link targets of a file with one relative path, holding what the snapshot holds where it leads.

    Args:
        base: Where the file's relative links are read from, which the path is joined to.
        path: The link's normalised relative path, as the key of its entry.
        lookup: What the snapshot holds at the link's target.
    """
    return FrozenMapping({PurePosixPath(path): LinkTarget(path=base.directory / path, lookup=lookup)})


@pytest.mark.unit
class TestBrokenLinkInASkill:
    def test_check_with_a_link_whose_target_is_missing_reports_it_on_its_line(self) -> None:
        #: Given
        subject = FakeSkillResourceContext(
            '# Guide\n\nSee [a](references/a.md).\n',
            link_targets=_targets(SKILL_ROOT, 'references/a.md', PathLookup.MISSING),
        )

        #: When
        occurrences = BrokenLink.check(subject)

        #: Then
        assert occurrences == (
            BrokenLink(
                line=LineNumber.from_int(3),
                url='references/a.md',
                base=SKILL_ROOT,
                target=RootRelativePath.parse('.agents/skills/review/references/a.md'),
            ),
        ), 'a link whose target holds nothing is one occurrence, on the line the link is on'

    def test_check_with_a_link_whose_target_is_present_reports_nothing(self) -> None:
        #: Given
        subject = FakeSkillResourceContext(
            '# Guide\n\nSee [a](references/a.md).\n',
            link_targets=_targets(SKILL_ROOT, 'references/a.md', PathLookup.PRESENT),
        )

        #: When
        occurrences = BrokenLink.check(subject)

        #: Then
        assert occurrences == (), 'a link to a file or a directory the snapshot holds goes somewhere'

    def test_check_with_a_link_whose_target_is_outside_the_scope_reports_nothing(self) -> None:
        #: Given
        subject = FakeSkillResourceContext(
            '# Guide\n\nSee [x](shared/x.md).\n',
            link_targets=_targets(SKILL_ROOT, 'shared/x.md', PathLookup.OUTSIDE_SCOPE),
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
            '# Guide\n\nSee [a](references/./a.md).\n',
            link_targets=_targets(SKILL_ROOT, 'references/a.md', PathLookup.MISSING),
        )

        #: When
        occurrences = BrokenLink.check(subject)

        #: Then
        assert occurrences == (
            BrokenLink(
                line=LineNumber.from_int(3),
                url='references/./a.md',
                base=SKILL_ROOT,
                target=RootRelativePath.parse('.agents/skills/review/references/a.md'),
            ),
        ), 'the entry is keyed by the normalised path, and the occurrence keeps the destination as written'

    def test_check_with_a_query_after_a_missing_path_reports_the_whole_destination(self) -> None:
        #: Given
        subject = FakeSkillResourceContext(
            '# Guide\n\nSee [b](b.md?raw=1).\n', link_targets=_targets(SKILL_ROOT, 'b.md', PathLookup.MISSING)
        )

        #: When
        occurrences = BrokenLink.check(subject)

        #: Then
        assert occurrences == (
            BrokenLink(
                line=LineNumber.from_int(3),
                url='b.md?raw=1',
                base=SKILL_ROOT,
                target=RootRelativePath.parse('.agents/skills/review/b.md'),
            ),
        ), 'the query is no part of the path, and the occurrence keeps the destination as written'


@pytest.mark.unit
class TestBrokenLinkInADocument:
    def test_check_with_a_link_whose_target_is_missing_reports_it_on_its_line(self) -> None:
        #: Given
        subject = FakeDocumentMarkdownContext(
            '# Setup\n\nRun [install](install.md) first.\n',
            link_targets=_targets(DOCUMENT_DIRECTORY, 'install.md', PathLookup.MISSING),
        )

        #: When
        occurrences = BrokenLink.check(subject)

        #: Then
        assert occurrences == (
            BrokenLink(
                line=LineNumber.from_int(3),
                url='install.md',
                base=DOCUMENT_DIRECTORY,
                target=RootRelativePath.parse('docs/guide/install.md'),
            ),
        ), "a document's link whose target holds nothing is one occurrence, read from the document's directory"

    def test_check_with_a_link_whose_target_is_present_reports_nothing(self) -> None:
        #: Given
        subject = FakeDocumentMarkdownContext(
            '# Setup\n\nRun [install](install.md) first.\n',
            link_targets=_targets(DOCUMENT_DIRECTORY, 'install.md', PathLookup.PRESENT),
        )

        #: When
        occurrences = BrokenLink.check(subject)

        #: Then
        assert occurrences == (), 'a link to a file the snapshot holds goes somewhere'


@pytest.mark.unit
class TestBrokenLinkDiagnostic:
    def test_message_with_a_percent_encoded_destination_shows_it_decoded(self) -> None:
        #: Given
        occurrence = BrokenLink(
            line=LineNumber.from_int(3),
            url='a%20b.md',
            base=SKILL_ROOT,
            target=RootRelativePath.parse('.agents/skills/review/a b.md'),
        )

        #: When
        message = occurrence.message()

        #: Then
        assert message == '`a b.md` names nothing', 'the destination shows percent-decoded'

    def test_message_with_a_link_in_a_document_is_the_same_template(self) -> None:
        #: Given
        occurrence = BrokenLink(
            line=LineNumber.from_int(3),
            url='install.md',
            base=DOCUMENT_DIRECTORY,
            target=RootRelativePath.parse('docs/guide/install.md'),
        )

        #: When
        message = occurrence.message()

        #: Then
        assert message == '`install.md` names nothing', 'where the link was read from is the note, not the message'

    def test_children_with_a_link_in_a_skill_say_where_it_was_read_from_and_what_it_names(self) -> None:
        #: Given
        occurrence = BrokenLink(
            line=LineNumber.from_int(3),
            url='a.md',
            base=SKILL_ROOT,
            target=RootRelativePath.parse('.agents/skills/review/a.md'),
        )

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Note("the Agent Skills specification reads a skill's relative links from the skill root"),
            Help('link a file or a directory the skill holds, relative to the skill root'),
            Note('read from the skill root, it names `.agents/skills/review/a.md`'),
        ), 'the specification note comes first, then the help, then where the link really leads'

    def test_children_with_a_link_in_a_document_say_where_it_was_read_from_and_what_it_names(self) -> None:
        #: Given
        occurrence = BrokenLink(
            line=LineNumber.from_int(3),
            url='../code/gone.md',
            base=DOCUMENT_DIRECTORY,
            target=RootRelativePath.parse('docs/code/gone.md'),
        )

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Help('link a file or a directory the repository holds, relative to this file'),
            Note('read from `docs/guide`, it names `docs/code/gone.md`'),
        ), 'a document names no specification; the note shows where the written path really leads'
