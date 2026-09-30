"""Run a check over documents of one database.

A run asks the database for everything it reads: the model decides which aspects govern each document, and
the part of the document the check reads is what the pure check validates — the frontmatter for the frontmatter
check, the parse tree's headings for the structure check, the whole file's token count for the budget check.
Selecting which documents to check is the caller's business: a run checks the refs it is handed, in the order
given, and reads only the governed ones. Every check reports in the same shape, so the ``check`` commands print
every run the same way.
"""

from dataclasses import dataclass

from lorecraft.project.document import DocumentDecodeError, DocumentRef
from lorecraft.project.schemas import StructureAspect
from lorecraft.project.syntax import FrontmatterNode, LineNumber, ParsedDocument

from .budget import validate_budget
from .database import Database
from .frontmatter import validate_frontmatter
from .reporting import Finding, Violation
from .structure import validate_structure


@dataclass(frozen=True, slots=True)
class DocumentReport:
    """The outcome of checking one selected document.

    Attributes:
        ref: The document the report is about; its path is the report path.
        governed: False when no specification governs the document for the check's aspect; the document was
            then never parsed.
        violations: What the check found, without the document's path; empty for an ungoverned document.
    """

    ref: DocumentRef
    governed: bool
    violations: tuple[Violation, ...]

    def findings(self) -> tuple[Finding, ...]:
        """Every violation, located in the report's document; empty exactly when the document is clean."""
        return tuple(Finding.at(self.ref.path, violation) for violation in self.violations)


@dataclass(frozen=True, slots=True)
class CheckRun:
    """One pass of one check over the selected documents: what the text and JSON printers consume.

    Attributes:
        reports: One per selected document, in the order the refs were given.
    """

    reports: tuple[DocumentReport, ...]

    def findings(self) -> tuple[Finding, ...]:
        """Every finding of every report, in report order; empty exactly when the run is clean."""
        findings: list[Finding] = []
        for report in self.reports:
            findings.extend(report.findings())
        return tuple(findings)


def run_frontmatter(database: Database, refs: tuple[DocumentRef, ...]) -> CheckRun:
    """Check each ref's frontmatter against the frontmatter schemas that govern it, in the order given.

    A document is governed when the structure specification of its corpus spec states a ``frontmatter`` schema;
    one whose corpus spec states none is ungoverned, and its text is never read. A governed document that is not
    UTF-8 carries the single violation ``frontmatter.undecodable`` at line 1.

    Args:
        database: The snapshot state the refs come from; its model decides which schemas govern each document.
        refs: The documents to check; each must be one the database's model lists.

    Raises:
        GetDocumentError: If a governed document is missing from the snapshot; a decode failure is a finding.
        ListSpecsError: If the model is not loaded yet and the specification directory cannot be listed.
        ListCorpusDirectoriesError: If the model is not loaded yet and docs/ cannot be listed.
        ListDocumentsError: If the model is not loaded yet and a corpus directory cannot be listed.
        GetStructureSchemaError: If the model is not loaded yet and a structure specification cannot be read.
        InvalidStructureSchemaError: If the model is not loaded yet and a structure specification is malformed.
    """
    reports: list[DocumentReport] = []
    for ref in refs:
        schemas = database.model().governance(ref).frontmatter_schemas()
        if not schemas:
            reports.append(DocumentReport(ref, governed=False, violations=()))
            continue
        frontmatter = _frontmatter(database, ref)
        if frontmatter is None:
            reports.append(DocumentReport(ref, governed=True, violations=(_undecodable('frontmatter'),)))
            continue
        result = validate_frontmatter(schemas, frontmatter=frontmatter, filename=ref.filename, corpus=ref.corpus)
        reports.append(DocumentReport(ref, governed=True, violations=result.violations))
    return CheckRun(reports=tuple(reports))


def run_structure(database: Database, refs: tuple[DocumentRef, ...]) -> CheckRun:
    """Check each ref against the structure specifications that govern it, in the order given.

    A governed document that is not UTF-8 carries the single violation ``structure.undecodable`` at line 1.

    Args:
        database: The snapshot state the refs come from; its model decides which specifications govern each
            document.
        refs: The documents to check; each must be one the database's model lists.

    Raises:
        GetDocumentError: If a governed document is missing from the snapshot; a decode failure is a finding.
        ListSpecsError: If the model is not loaded yet and the specification directory cannot be listed.
        ListCorpusDirectoriesError: If the model is not loaded yet and docs/ cannot be listed.
        ListDocumentsError: If the model is not loaded yet and a corpus directory cannot be listed.
        GetStructureSchemaError: If the model is not loaded yet and a structure specification cannot be read.
        InvalidStructureSchemaError: If the model is not loaded yet and a structure specification is malformed.
    """
    reports: list[DocumentReport] = []
    for ref in refs:
        aspects = database.model().governance(ref).structure_specs()
        if not aspects:
            reports.append(DocumentReport(ref, governed=False, violations=()))
            continue
        document = _parse(database, ref)
        if document is None:
            reports.append(DocumentReport(ref, governed=True, violations=(_undecodable('structure'),)))
            continue
        result = validate_structure(aspects, headings=document.headings)
        reports.append(DocumentReport(ref, governed=True, violations=result.violations))
    return CheckRun(reports=tuple(reports))


def run_budget(database: Database, refs: tuple[DocumentRef, ...]) -> CheckRun:
    """Check each ref's whole-file token count against the budgets that govern it, in the order given.

    A document is governed when at least one of its structure specifications sets a ``tokens`` budget; one whose
    specifications set none is ungoverned, and its text is never read. A governed document that is not UTF-8
    carries the single violation ``budget.undecodable`` at line 1.

    Args:
        database: The snapshot state the refs come from; its model decides which specifications govern each
            document.
        refs: The documents to check; each must be one the database's model lists.

    Raises:
        GetDocumentError: If a governed document is missing from the snapshot; a decode failure is a finding.
        ListSpecsError: If the model is not loaded yet and the specification directory cannot be listed.
        ListCorpusDirectoriesError: If the model is not loaded yet and docs/ cannot be listed.
        ListDocumentsError: If the model is not loaded yet and a corpus directory cannot be listed.
        GetStructureSchemaError: If the model is not loaded yet and a structure specification cannot be read.
        InvalidStructureSchemaError: If the model is not loaded yet and a structure specification is malformed.
    """
    reports: list[DocumentReport] = []
    for ref in refs:
        aspects = _budgeted(database.model().governance(ref).structure_specs())
        if not aspects:
            reports.append(DocumentReport(ref, governed=False, violations=()))
            continue
        token_count = _tokens(database, ref)
        if token_count is None:
            reports.append(DocumentReport(ref, governed=True, violations=(_undecodable('budget'),)))
            continue
        result = validate_budget(aspects, token_count=token_count)
        reports.append(DocumentReport(ref, governed=True, violations=result.violations))
    return CheckRun(reports=tuple(reports))


def _budgeted(aspects: tuple[StructureAspect, ...]) -> tuple[StructureAspect, ...]:
    """The structure aspects that set a ``tokens`` budget, in the order given."""
    budgeted: list[StructureAspect] = []
    for aspect in aspects:
        if aspect.tokens is not None:
            budgeted.append(aspect)
    return tuple(budgeted)


def _frontmatter(database: Database, ref: DocumentRef) -> FrontmatterNode | None:
    """The document's frontmatter node, or ``None`` when its bytes are not UTF-8.

    Returns:
        The frontmatter node. ``None`` is the degraded return ``_parse`` documents, for the same reason.

    Raises:
        GetDocumentError: If the document is missing from the snapshot; a decode failure is not raised.
    """
    try:
        return database.frontmatter(ref)
    except DocumentDecodeError:
        return None


def _parse(database: Database, ref: DocumentRef) -> ParsedDocument | None:
    """The document's parse tree, or ``None`` when its bytes are not UTF-8.

    Returns:
        The parse tree. ``None`` is the degraded return for bytes that are present but not UTF-8: those are on
        the same side of the line as invalid YAML, since the document is wrong, so the caller reports a finding
        rather than taking the exit-2 path an unreadable file takes.

    Raises:
        GetDocumentError: If the document is missing from the snapshot; a decode failure is not raised.
    """
    try:
        return database.parse(ref)
    except DocumentDecodeError:
        return None


def _tokens(database: Database, ref: DocumentRef) -> int | None:
    """The tokens in the document's whole file, or ``None`` when its bytes are not UTF-8.

    Returns:
        The token count. ``None`` is the degraded return ``_parse`` documents, for the same reason.

    Raises:
        GetDocumentError: If the document is missing from the snapshot; a decode failure is not raised.
    """
    try:
        return database.tokens(ref)
    except DocumentDecodeError:
        return None


def _undecodable(rule_namespace: str) -> Violation:
    """The violation a governed document that is not UTF-8 carries instead of the check's own."""
    return Violation(
        line=LineNumber(1),
        rule=f'{rule_namespace}.undecodable',
        message='document is not valid UTF-8',
    )
