"""A document's identity in the workspace model, separate from its content.

The model lists which documents exist; their text stays behind the document repository and is read on
demand. A ``DocumentRef`` is the key that ties the two together, and its ``path`` is the root-relative
location every finding reports.
"""

from dataclasses import dataclass

from lorecraft_project.aspect import AspectFilename
from lorecraft_project.corpus import CorpusName
from lorecraft_project.layout import DOCS_DIR, DOCUMENT_SUFFIX
from lorecraft_vfs import RootRelativePath


@dataclass(frozen=True, slots=True)
class DocumentRef:
    """A document's identity in the workspace model; carries no content.

    Attributes:
        corpus: The corpus directory name under docs/.
        filename: The Markdown filename stem; the frontmatter ``name`` must equal it.
    """

    corpus: CorpusName
    filename: AspectFilename

    @property
    def path(self) -> RootRelativePath:
        """Root-relative ``docs/<corpus>/<filename>.md``; the report path in findings."""
        return DOCS_DIR / str(self.corpus) / f'{self.filename}{DOCUMENT_SUFFIX}'
