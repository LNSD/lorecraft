"""Run the header check over documents of one database.

The run asks the database for everything it reads: the model decides which schemas govern each document, and
the parse tree is what the pure check validates. Selecting which documents to check is the caller's business:
the run checks the refs it is handed, in the order given, and parses only the governed ones.
"""

from dataclasses import dataclass

from lorecraft_project.document import DocumentDecodeError, DocumentRef
from lorecraft_project.schemas import HeaderAspect
from lorecraft_project.syntax import LineNumber

from .database import Database
from .header import HeaderCheckResult, validate_header
from .reporting import Finding


@dataclass(frozen=True, slots=True)
class HeaderReport:
    """The outcome of checking one selected document.

    Attributes:
        ref: The document the report is about; its path is the report path.
        aspects: The header schemas governing the document; ``()`` means ungoverned, and the document was
            never parsed.
        result: The check's findings; empty for an ungoverned document.
    """

    ref: DocumentRef
    aspects: tuple[HeaderAspect, ...]
    result: HeaderCheckResult


@dataclass(frozen=True, slots=True)
class HeaderRun:
    """One pass over the selected documents: what the text and JSON printers consume.

    Attributes:
        reports: One per selected document, in the order the refs were given.
    """

    reports: tuple[HeaderReport, ...]

    def findings(self) -> tuple[Finding, ...]:
        """Every finding of every report, in report order; empty exactly when the run is clean."""
        findings: list[Finding] = []
        for report in self.reports:
            findings.extend(report.result.findings)
        return tuple(findings)


def run_header(database: Database, refs: tuple[DocumentRef, ...]) -> HeaderRun:
    """Check each ref against the header schemas that govern it, in the order given.

    Args:
        database: The snapshot state the refs come from; its model decides which schemas govern each document.
        refs: The documents to check; each must be one the database's model lists.

    Raises:
        GetDocumentError: If a governed document is missing from the snapshot; a decode failure is a finding.
        ListSpecsError: If the model is not loaded yet and the specification directory cannot be listed.
        ListCorpusDirectoriesError: If the model is not loaded yet and docs/ cannot be listed.
        ListDocumentsError: If the model is not loaded yet and a corpus directory cannot be listed.
        GetHeaderSchemaError: If the model is not loaded yet and a header schema cannot be read or decoded.
        InvalidHeaderSchemaError: If the model is not loaded yet and a header schema is malformed.
    """
    reports: list[HeaderReport] = []
    for ref in refs:
        reports.append(_check_document(database, ref))
    return HeaderRun(reports=tuple(reports))


def _check_document(database: Database, ref: DocumentRef) -> HeaderReport:
    """Select the document's header schemas, parse it if any govern it, and run the check.

    Returns:
        The report. An ungoverned document is never parsed and carries no findings. A governed document that
        is not UTF-8 carries the single finding ``frontmatter.undecodable`` at line 1 instead of the check's.

    Raises:
        GetDocumentError: If a governed document is missing from the snapshot; a decode failure is not raised.
    """
    aspects = database.model().governance(ref).header_schemas()
    if not aspects:
        return HeaderReport(ref, aspects, HeaderCheckResult(findings=()))
    try:
        document = database.parse(ref)
    except DocumentDecodeError as exc:
        # Bytes that are present but not UTF-8 are on the same side of the line as invalid YAML: the
        # document is wrong, so the outcome is a finding (the degraded return documented above) rather
        # than the exit-2 path an unreadable file takes.
        finding = Finding(
            path=exc.ref.path, line=LineNumber(1), rule='frontmatter.undecodable', message='document is not valid UTF-8'
        )
        return HeaderReport(ref, aspects, HeaderCheckResult(findings=(finding,)))
    return HeaderReport(ref, aspects, validate_header(document, ref, aspects))
