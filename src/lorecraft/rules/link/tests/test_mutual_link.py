"""`LC507`, `mutual-link`, over the links of one document to other documents and whether each links back.

Every case is a document of corpus `guide` written as text, through a fake database that states the links the database
would find to other documents, each with its corpus and whether that document links back.
"""

import pytest

from lorecraft.core.num import NonZeroUnsignedInt
from lorecraft.project.aspect import AspectFilename
from lorecraft.project.corpus import CorpusName
from lorecraft.project.link_target import DocumentLink
from lorecraft.project.syntax import LineNumber
from lorecraft.rules.location import Help, Note
from lorecraft.rules.tests.fake_database import FakeDocumentDatabase, judged

from ..mutual_link import MutualLink

STRUCTURE = '{"frontmatter": {"type": "object"}}'


def _link(corpus: str, *, has_back_link: bool, line: int = 3) -> DocumentLink:
    """A link of the document to the document `a` of a corpus.

    Args:
        corpus: The corpus of the document the link leads to.
        has_back_link: Whether that document links back.
        line: The line the link is on.
    """
    return DocumentLink(
        line=LineNumber(NonZeroUnsignedInt(line)),
        url=f'../{corpus}/a.md',
        corpus=CorpusName.parse(corpus),
        filename=AspectFilename.parse('a'),
        has_back_link=has_back_link,
    )


def _document(*links: DocumentLink) -> FakeDocumentDatabase:
    """A document of corpus `guide` holding the links.

    Args:
        links: The links to other documents the database would find.
    """
    return FakeDocumentDatabase('# Setup\n', corpus='guide', structure=STRUCTURE, document_links=links)


@pytest.mark.unit
class TestMutualLink:
    def test_check_with_a_link_to_another_corpus_that_links_back_reports_it_on_its_line(self) -> None:
        #: Given
        subject = _document(_link('feat', has_back_link=True))
        expected = MutualLink(
            line=LineNumber(NonZeroUnsignedInt(3)), url='../feat/a.md', corpus='feat', filename='a.md'
        )

        #: When
        occurrences = judged(MutualLink, subject)

        #: Then
        assert occurrences == (expected,), 'a mutual link across corpora is one occurrence, on the link'

    def test_check_with_a_link_to_another_corpus_that_does_not_link_back_reports_nothing(self) -> None:
        #: Given
        subject = _document(_link('feat', has_back_link=False))

        #: When
        occurrences = judged(MutualLink, subject)

        #: Then
        assert occurrences == (), 'a link one way is the direction the rule asks for'

    def test_check_with_a_mutual_link_inside_the_corpus_reports_nothing(self) -> None:
        #: Given
        subject = _document(_link('guide', has_back_link=True))

        #: When
        occurrences = judged(MutualLink, subject)

        #: Then
        assert occurrences == (), 'two documents of one corpus may link each other, which this rule leaves alone'

    def test_check_with_two_mutual_links_reports_each_in_document_order(self) -> None:
        #: Given
        subject = _document(_link('feat', has_back_link=True, line=3), _link('code', has_back_link=True, line=5))
        expected = (
            MutualLink(line=LineNumber(NonZeroUnsignedInt(3)), url='../feat/a.md', corpus='feat', filename='a.md'),
            MutualLink(line=LineNumber(NonZeroUnsignedInt(5)), url='../code/a.md', corpus='code', filename='a.md'),
        )

        #: When
        occurrences = judged(MutualLink, subject)

        #: Then
        assert occurrences == expected, 'each mutual link is reported whole, in the order of the document'

    def test_children_lead_with_the_fix_then_state_the_direction(self) -> None:
        #: Given
        occurrence = MutualLink(
            line=LineNumber(NonZeroUnsignedInt(1)), url='../feat/a.md', corpus='feat', filename='a.md'
        )

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Help('keep the link in the document that builds on the other, and remove it from `a.md` or here'),
            Note('documents of two corpora link one way: the one that builds on the other links it'),
        ), 'the fix leads, as no spec does, and the note states the direction after it'
