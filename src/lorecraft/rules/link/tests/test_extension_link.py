"""`LINK005`, `extension-link`, over the relative links of one document and the filename each leads to.

Every case is a document written as text and parsed by the real parser, through a fake database; what the snapshot
holds at each link's target is a cross-file state, so the test states it by hand, keyed by the link's normalised
relative path. The document is `setup.md`, so its extensions are the files named `setup-<something>.md`.
"""

import pytest

from lib.primitives import StructurePrimitives
from lorecraft.core.mapping import FrozenMapping
from lorecraft.core.num import NonZeroUnsignedInt
from lorecraft.core.path import RootRelativePath
from lorecraft.project.link_target import (
    DirectoryTarget,
    EscapingTarget,
    FileTarget,
    LinkTarget,
    LinkTargetEntry,
    LinkTargetFailure,
    MissingTarget,
)
from lorecraft.project.syntax import LineNumber, NormalisedLinkPath
from lorecraft.rules.location import Help, Note
from lorecraft.rules.tests.fake_database import DEFAULT_DOCUMENT_DIRECTORY, FakeDocumentDatabase, judged

from ..extension_link import ExtensionLink, extension_link_facts
from ..queries import NotExtensionDocument

STRUCTURE = '{"frontmatter": {"type": "object"}}'


def _document(text: str, url: str, entry: LinkTargetEntry) -> FakeDocumentDatabase:
    """A document `setup.md` with the text, whose one link has the snapshot entry.

    Args:
        text: The document's whole file.
        url: The link's normalised relative path, as the key of its entry.
        entry: What the snapshot holds where the link leads.
    """
    return FakeDocumentDatabase(
        text, corpus='guide', structure=STRUCTURE, link_targets=FrozenMapping({NormalisedLinkPath.parse(url): entry})
    )


def _present(url: str, directory: RootRelativePath = DEFAULT_DOCUMENT_DIRECTORY) -> LinkTarget:
    """The entry of a link to a file the snapshot holds, read from the document's directory unless stated.

    Args:
        url: The link's relative path.
        directory: The directory the path is joined to.
    """
    target = directory / RootRelativePath.parse(url)
    return LinkTarget(FileTarget(target))


@pytest.mark.unit
class TestExtensionLink:
    def test_check_with_a_link_to_a_document_continuing_its_name_reports_it_on_its_line(self) -> None:
        #: Given
        subject = _document('# Setup\n\nSee [more](setup-extra.md).\n', 'setup-extra.md', _present('setup-extra.md'))

        #: When
        occurrences = judged(ExtensionLink, subject)

        #: Then
        assert occurrences == (
            ExtensionLink(
                line=LineNumber(NonZeroUnsignedInt(3)),
                url='setup-extra.md',
                extension='setup-extra.md',
                base='setup.md',
            ),
        ), 'a link to a file whose name continues the document name after a hyphen is one occurrence, on its line'

    def test_children_name_the_base_and_say_to_remove_the_link(self) -> None:
        #: Given
        occurrence = ExtensionLink(
            line=LineNumber(NonZeroUnsignedInt(1)), url='setup-extra.md', extension='setup-extra.md', base='setup.md'
        )

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Note('`setup-extra.md` extends `setup.md`: it names `setup.md`, which names no extension'),
            Help('remove the link to `setup-extra.md`'),
        ), 'the note says which way the reference goes and the help says to drop the link'

    def test_check_with_a_link_to_a_name_continued_without_a_hyphen_reports_nothing(self) -> None:
        #: Given
        subject = _document('[x](setupextra.md)\n', 'setupextra.md', _present('setupextra.md'))

        #: When
        occurrences = judged(ExtensionLink, subject)

        #: Then
        assert occurrences == (), 'only a name continued after a hyphen is an extension'

    def test_check_with_a_link_to_a_name_with_the_document_as_a_suffix_reports_nothing(self) -> None:
        #: Given
        subject = _document('[x](other-setup.md)\n', 'other-setup.md', _present('other-setup.md'))

        #: When
        occurrences = judged(ExtensionLink, subject)

        #: Then
        assert occurrences == (), 'a name that only ends in the document name is no extension'

    def test_check_with_a_link_to_a_document_to_itself_reports_nothing(self) -> None:
        #: Given
        subject = _document('[x](setup.md)\n', 'setup.md', _present('setup.md'))

        #: When
        occurrences = judged(ExtensionLink, subject)

        #: Then
        assert occurrences == (), 'a document is not its own extension'

    def test_check_with_a_link_to_a_directory_named_like_an_extension_reports_nothing(self) -> None:
        #: Given
        entry = LinkTarget(
            target=DirectoryTarget(DEFAULT_DOCUMENT_DIRECTORY / RootRelativePath.parse('setup-extra.md')),
        )
        subject = _document('[folder](setup-extra.md/)\n', 'setup-extra.md', entry)

        #: When
        occurrences = judged(ExtensionLink, subject)

        #: Then
        assert occurrences == (), 'a directory is no document, so a link to one is no link to an extension'

    def test_check_with_a_link_to_a_document_of_another_directory_reports_nothing(self) -> None:
        #: Given
        subject = _document(
            '[x](../other/setup-extra.md)\n',
            '../other/setup-extra.md',
            LinkTarget(
                target=FileTarget(RootRelativePath.parse('docs/other/setup-extra.md')),
            ),
        )

        #: When
        occurrences = judged(ExtensionLink, subject)

        #: Then
        assert occurrences == (), 'an extension lies beside its base, so a name in another directory is no extension'

    def test_check_with_a_link_to_a_missing_document_reports_nothing(self) -> None:
        #: Given
        entry = LinkTargetFailure(MissingTarget(DEFAULT_DOCUMENT_DIRECTORY / RootRelativePath.parse('setup-extra.md')))
        subject = _document('[x](setup-extra.md)\n', 'setup-extra.md', entry)

        #: When
        occurrences = judged(ExtensionLink, subject)

        #: Then
        assert occurrences == (), 'a link to nothing is `LINK003`, not this rule'

    def test_check_with_an_escaping_link_reports_nothing(self) -> None:
        #: Given
        subject = _document(
            '[x](../../../setup-extra.md)\n', '../../../setup-extra.md', LinkTargetFailure(EscapingTarget())
        )

        #: When
        occurrences = judged(ExtensionLink, subject)

        #: Then
        assert occurrences == (), 'a link above the repository names no document'

    def test_check_with_a_fragment_link_and_a_url_reports_nothing(self) -> None:
        #: Given
        subject = _document(
            '[a](#top) [b](https://example.com/setup-extra.md)\n', 'setup-extra.md', _present('setup-extra.md')
        )

        #: When
        occurrences = judged(ExtensionLink, subject)

        #: Then
        assert occurrences == (), 'a fragment-only link and a URL spell no relative path'


@pytest.mark.unit
class TestExtensionLinkFacts:
    def test_extension_link_facts_of_an_item_that_is_no_document_holds_no_link(self) -> None:
        #: When
        facts = extension_link_facts(StructurePrimitives(()))

        #: Then
        assert facts == NotExtensionDocument(), 'no name and no link base'
