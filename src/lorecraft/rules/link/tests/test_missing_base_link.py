"""`LINK006`, `missing-base-link`, over the References section of one document and the base its name chain gives it.

Every case is a document written as text and parsed by the real parser, through a fake database that states the other
documents of its corpus. What the snapshot holds at each link's target is stated by hand, keyed by the link's
normalised relative path. The document is `setup-extra.md`, so its base is `setup.md` when `setup` is a sibling.
"""

import pytest

from lorecraft.core.mapping import FrozenMapping
from lorecraft.core.num import NonZeroUnsignedInt
from lorecraft.core.path import RootRelativePath
from lorecraft.project.link_target import LinkTarget, LinkTargetEntry, PathLookup
from lorecraft.project.syntax import LineNumber, NormalisedLinkPath
from lorecraft.rules.location import Help, Note
from lorecraft.rules.tests.fake_database import DEFAULT_DOCUMENT_DIRECTORY, FakeDocumentDatabase, judged

from ..missing_base_link import MissingBaseLink

STRUCTURE = '{"frontmatter": {"type": "object"}}'


def _document(
    text: str, *, siblings: tuple[str, ...] = ('setup',), targets: dict[str, str] | None = None
) -> FakeDocumentDatabase:
    """The document `setup-extra.md` with the text, beside the siblings, each link leading to a file the snapshot holds.

    Args:
        text: The document's whole file.
        siblings: The other documents of the corpus.
        targets: For each link's normalised path, the root-relative path of the file it leads to.
    """
    entries: dict[NormalisedLinkPath, LinkTargetEntry] = {
        NormalisedLinkPath.parse(url): LinkTarget(path=RootRelativePath.parse(path), lookup=PathLookup.FILE)
        for url, path in (targets or {}).items()
    }
    return FakeDocumentDatabase(
        text,
        corpus='guide',
        structure=STRUCTURE,
        filename='setup-extra',
        siblings=siblings,
        link_targets=FrozenMapping(entries),
    )


def _base_target() -> dict[str, str]:
    """The target of a link to `setup.md`, read from the document's directory."""
    return {'setup.md': f'{DEFAULT_DOCUMENT_DIRECTORY}/setup.md'}


def _occurrence(line: int) -> MissingBaseLink:
    """The finding for `setup-extra.md` missing its base `setup.md`, on the line."""
    return MissingBaseLink(line=LineNumber(NonZeroUnsignedInt(line)), base='setup.md', extension='setup-extra.md')


@pytest.mark.unit
class TestMissingBaseLink:
    def test_check_with_references_not_linking_the_base_reports_it_on_the_references_heading(self) -> None:
        #: Given
        subject = _document('# Setup extra\n\n## References\n\n- [o](other.md) - Related: x\n')

        #: When
        occurrences = judged(MissingBaseLink, subject)

        #: Then
        assert occurrences == (_occurrence(3),), 'a base absent from References is one occurrence, on its heading'

    def test_check_with_no_references_section_reports_it_on_the_title(self) -> None:
        #: Given
        subject = _document('# Setup extra\n\nText.\n')

        #: When
        occurrences = judged(MissingBaseLink, subject)

        #: Then
        assert occurrences == (_occurrence(1),), 'a document without References names no base, so the title is reported'

    def test_check_with_the_base_linked_under_references_reports_nothing(self) -> None:
        #: Given
        subject = _document(
            '# Setup extra\n\n## References\n\n- [setup](setup.md) - Extends: x\n', targets=_base_target()
        )

        #: When
        occurrences = judged(MissingBaseLink, subject)

        #: Then
        assert occurrences == (), 'a link to the base file inside References names the base'

    def test_check_with_the_base_linked_only_in_the_text_reports_it(self) -> None:
        #: Given
        subject = _document(
            '# Setup extra\n\nSee [setup](setup.md).\n\n## References\n\n- [o](other.md) - Related: x\n',
            targets=_base_target(),
        )

        #: When
        occurrences = judged(MissingBaseLink, subject)

        #: Then
        assert occurrences == (_occurrence(5),), 'a link outside the References section does not count'

    def test_check_with_the_base_linked_under_external_references_reports_it(self) -> None:
        #: Given
        subject = _document(
            '# Setup extra\n\n## References\n\n## External References\n\n- [setup](setup.md)\n', targets=_base_target()
        )

        #: When
        occurrences = judged(MissingBaseLink, subject)

        #: Then
        assert occurrences == (_occurrence(3),), (
            'External References is a section of its own, past where References ends'
        )

    def test_check_with_a_document_without_a_base_reports_nothing(self) -> None:
        #: Given
        subject = _document('# Setup extra\n\n## References\n', siblings=())

        #: When
        occurrences = judged(MissingBaseLink, subject)

        #: Then
        assert occurrences == (), 'a document no name continues into has no base to name'

    def test_children_name_the_name_chain_and_say_to_link_the_base(self) -> None:
        #: Given
        occurrence = _occurrence(1)

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Note('`setup-extra.md` continues the name of `setup.md`, so it extends it'),
            Help('link `setup.md` first under References'),
        ), 'the note gives the reason for the base and the help says where to link it'
