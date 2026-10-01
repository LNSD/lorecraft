"""Run a check over documents, or over skills, of one database.

A run asks the database for everything it reads: the model decides which aspects govern each document, and
the part of the document the check reads is what the pure check validates — the frontmatter for the frontmatter
check, the parse tree's headings for the structure check, the whole file's token count for the budget check.
Selecting which documents to check is the caller's business: a run checks the refs it is handed, in the order
given, and reads only the governed ones. Every check reports in the same shape, so the ``check`` commands print
every run the same way.

The skill check runs over skills instead: the refs it is handed are the model's ``SkillRef``s, the parts it reads
are the frontmatter, the links and the heading anchors of each ``SKILL.md``, and the Agent Skills specification
governs every one of them, so a skill is never ungoverned. The files a skill links in through ``metadata`` are
checked too, against what the snapshot holds at each path listed. It reports in a shape of its own, a
``SkillCheckRun`` of ``SkillReport``s.
"""

from dataclasses import dataclass
from typing import assert_never

from lorecraft.core.path import RootRelativePath, RootRelativePathError
from lorecraft.project.document import DocumentDecodeError, DocumentRef
from lorecraft.project.schemas import SKILL_FRONTMATTER_SCHEMA, StructureAspect
from lorecraft.project.skill import SkillDecodeError, SkillRef
from lorecraft.project.syntax import (
    Frontmatter,
    FrontmatterNode,
    InvalidYamlFrontmatter,
    LineNumber,
    MissingFrontmatter,
    NonMappingFrontmatter,
    ParsedDocument,
)

from .budget import validate_budget
from .database import Database
from .frontmatter import validate_frontmatter
from .reporting import Finding, Violation
from .skill import SkillCheckResult, validate_skill
from .skill_link import validate_skill_links
from .skill_metadata import ListedFile, ListedFiles, ListedFileState, listed_by_subkey, validate_skill_metadata
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


@dataclass(frozen=True, slots=True)
class SkillReport:
    """The outcome of checking one selected skill.

    Attributes:
        ref: The skill the report is about; its ``SKILL.md`` path is the report path.
        violations: What the check found, without the skill's path; empty when the skill conforms.
    """

    ref: SkillRef
    violations: tuple[Violation, ...]

    def findings(self) -> tuple[Finding, ...]:
        """Every violation, located in the skill's ``SKILL.md``; empty exactly when the skill is clean."""
        return tuple(Finding.at(self.ref.path, violation) for violation in self.violations)


@dataclass(frozen=True, slots=True)
class SkillCheckRun:
    """One pass of the skill check over the selected skills: what the text and JSON printers consume.

    Attributes:
        reports: One per selected skill, in the order the refs were given.
    """

    reports: tuple[SkillReport, ...]

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
        DocumentReadError: If a governed document is missing from the snapshot; a decode failure is a finding.
        DirListError: If the model is not loaded yet and the specification directory or docs/ cannot be listed.
        CorpusListError: If the model is not loaded yet and a corpus directory cannot be listed.
        StructureSchemaReadError: If the model is not loaded yet and a structure specification cannot be read.
        StructureSpecDecodeError: If the model is not loaded yet and a structure specification is not JSON in the
            dialect's shape.
        StructureSpecFilenameError: If the model is not loaded yet and a structure specification is not at a
            specification filename.
        EmptyStructureSpecError: If the model is not loaded yet and a structure specification states no rule.
        InvalidTitleCountError: If the model is not loaded yet and a title count is below 1.
        InvalidTokenBudgetError: If the model is not loaded yet and a token budget is below 1.
        InvalidWordCapError: If the model is not loaded yet and an outline word cap is below 1.
        RepeatedOutlineSectionError: If the model is not loaded yet and an outline names a section twice.
        ForbiddenOutlineSectionError: If the model is not loaded yet and a specification forbids a section its
            outline names.
        AdjacentAnyRunsError: If the model is not loaded yet and an outline places two ``any`` runs side by side.
        InvalidFrontmatterSchemaError: If the model is not loaded yet and a frontmatter schema is rejected by the
            meta-schema.
        FrontmatterSchemaIdError: If the model is not loaded yet and a schema in a frontmatter schema carries
            ``$id``.
        ForeignFrontmatterDialectError: If the model is not loaded yet and a schema in a frontmatter schema names
            another dialect.
        UntypedFrontmatterSchemaError: If the model is not loaded yet and a frontmatter schema's root does not state
            an object.
        DirResolveError: If the model is not loaded yet and a skills directory cannot be resolved.
        SkillsDirListError: If the model is not loaded yet and a skills directory cannot be listed.
        SkillEntryResolveError: If the model is not loaded yet and a symlinked skill entry cannot be resolved.
        SkillDirListError: If the model is not loaded yet and a skill directory cannot be listed.
        SkillFileResolveError: If the model is not loaded yet and a symlinked SKILL.md cannot be resolved.
    """
    reports: list[DocumentReport] = []
    for ref in refs:
        schemas = database.model().governance(ref).frontmatter_schemas()
        if not schemas:
            reports.append(DocumentReport(ref, governed=False, violations=()))
            continue
        frontmatter = _frontmatter(database, ref)
        match frontmatter:
            case DocumentDecodeError():
                reports.append(DocumentReport(ref, governed=True, violations=(_undecodable('frontmatter'),)))
            case Frontmatter() | MissingFrontmatter() | InvalidYamlFrontmatter() | NonMappingFrontmatter():
                result = validate_frontmatter(
                    schemas, frontmatter=frontmatter, filename=ref.filename, corpus=ref.corpus
                )
                reports.append(DocumentReport(ref, governed=True, violations=result.violations))
            case _:
                assert_never(frontmatter)
    return CheckRun(reports=tuple(reports))


def run_structure(database: Database, refs: tuple[DocumentRef, ...]) -> CheckRun:
    """Check each ref against the structure specifications that govern it, in the order given.

    A governed document that is not UTF-8 carries the single violation ``structure.undecodable`` at line 1.

    Args:
        database: The snapshot state the refs come from; its model decides which specifications govern each
            document.
        refs: The documents to check; each must be one the database's model lists.

    Raises:
        DocumentReadError: If a governed document is missing from the snapshot; a decode failure is a finding.
        DirListError: If the model is not loaded yet and the specification directory or docs/ cannot be listed.
        CorpusListError: If the model is not loaded yet and a corpus directory cannot be listed.
        StructureSchemaReadError: If the model is not loaded yet and a structure specification cannot be read.
        StructureSpecDecodeError: If the model is not loaded yet and a structure specification is not JSON in the
            dialect's shape.
        StructureSpecFilenameError: If the model is not loaded yet and a structure specification is not at a
            specification filename.
        EmptyStructureSpecError: If the model is not loaded yet and a structure specification states no rule.
        InvalidTitleCountError: If the model is not loaded yet and a title count is below 1.
        InvalidTokenBudgetError: If the model is not loaded yet and a token budget is below 1.
        InvalidWordCapError: If the model is not loaded yet and an outline word cap is below 1.
        RepeatedOutlineSectionError: If the model is not loaded yet and an outline names a section twice.
        ForbiddenOutlineSectionError: If the model is not loaded yet and a specification forbids a section its
            outline names.
        AdjacentAnyRunsError: If the model is not loaded yet and an outline places two ``any`` runs side by side.
        InvalidFrontmatterSchemaError: If the model is not loaded yet and a frontmatter schema is rejected by the
            meta-schema.
        FrontmatterSchemaIdError: If the model is not loaded yet and a schema in a frontmatter schema carries
            ``$id``.
        ForeignFrontmatterDialectError: If the model is not loaded yet and a schema in a frontmatter schema names
            another dialect.
        UntypedFrontmatterSchemaError: If the model is not loaded yet and a frontmatter schema's root does not state
            an object.
        DirResolveError: If the model is not loaded yet and a skills directory cannot be resolved.
        SkillsDirListError: If the model is not loaded yet and a skills directory cannot be listed.
        SkillEntryResolveError: If the model is not loaded yet and a symlinked skill entry cannot be resolved.
        SkillDirListError: If the model is not loaded yet and a skill directory cannot be listed.
        SkillFileResolveError: If the model is not loaded yet and a symlinked SKILL.md cannot be resolved.
    """
    reports: list[DocumentReport] = []
    for ref in refs:
        aspects = database.model().governance(ref).structure_specs()
        if not aspects:
            reports.append(DocumentReport(ref, governed=False, violations=()))
            continue
        document = _parse(database, ref)
        match document:
            case DocumentDecodeError():
                reports.append(DocumentReport(ref, governed=True, violations=(_undecodable('structure'),)))
            case ParsedDocument():
                result = validate_structure(aspects, headings=document.headings)
                reports.append(DocumentReport(ref, governed=True, violations=result.violations))
            case _:
                assert_never(document)
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
        DocumentReadError: If a governed document is missing from the snapshot; a decode failure is a finding.
        DirListError: If the model is not loaded yet and the specification directory or docs/ cannot be listed.
        CorpusListError: If the model is not loaded yet and a corpus directory cannot be listed.
        StructureSchemaReadError: If the model is not loaded yet and a structure specification cannot be read.
        StructureSpecDecodeError: If the model is not loaded yet and a structure specification is not JSON in the
            dialect's shape.
        StructureSpecFilenameError: If the model is not loaded yet and a structure specification is not at a
            specification filename.
        EmptyStructureSpecError: If the model is not loaded yet and a structure specification states no rule.
        InvalidTitleCountError: If the model is not loaded yet and a title count is below 1.
        InvalidTokenBudgetError: If the model is not loaded yet and a token budget is below 1.
        InvalidWordCapError: If the model is not loaded yet and an outline word cap is below 1.
        RepeatedOutlineSectionError: If the model is not loaded yet and an outline names a section twice.
        ForbiddenOutlineSectionError: If the model is not loaded yet and a specification forbids a section its
            outline names.
        AdjacentAnyRunsError: If the model is not loaded yet and an outline places two ``any`` runs side by side.
        InvalidFrontmatterSchemaError: If the model is not loaded yet and a frontmatter schema is rejected by the
            meta-schema.
        FrontmatterSchemaIdError: If the model is not loaded yet and a schema in a frontmatter schema carries
            ``$id``.
        ForeignFrontmatterDialectError: If the model is not loaded yet and a schema in a frontmatter schema names
            another dialect.
        UntypedFrontmatterSchemaError: If the model is not loaded yet and a frontmatter schema's root does not state
            an object.
        DirResolveError: If the model is not loaded yet and a skills directory cannot be resolved.
        SkillsDirListError: If the model is not loaded yet and a skills directory cannot be listed.
        SkillEntryResolveError: If the model is not loaded yet and a symlinked skill entry cannot be resolved.
        SkillDirListError: If the model is not loaded yet and a skill directory cannot be listed.
        SkillFileResolveError: If the model is not loaded yet and a symlinked SKILL.md cannot be resolved.
    """
    reports: list[DocumentReport] = []
    for ref in refs:
        aspects = _budgeted(database.model().governance(ref).structure_specs())
        if not aspects:
            reports.append(DocumentReport(ref, governed=False, violations=()))
            continue
        token_count = _tokens(database, ref)
        match token_count:
            case DocumentDecodeError():
                reports.append(DocumentReport(ref, governed=True, violations=(_undecodable('budget'),)))
            case int():
                result = validate_budget(aspects, token_count=token_count)
                reports.append(DocumentReport(ref, governed=True, violations=result.violations))
            case _:
                assert_never(token_count)
    return CheckRun(reports=tuple(reports))


def run_skills(database: Database, refs: tuple[SkillRef, ...]) -> SkillCheckRun:
    """Check each skill's frontmatter, its links and the files its ``metadata`` lists, in the order given.

    Every skill is governed: the Agent Skills specification applies to each one. A skill's violations list the
    frontmatter's first, then the links', then, when the frontmatter is a mapping, its ``metadata``'s; a skill
    whose ``metadata`` lists no file has none of those. A skill whose ``SKILL.md`` is not UTF-8 carries the single
    violation ``skill.undecodable`` at line 1, and is never parsed.

    Args:
        database: The snapshot state the refs come from.
        refs: The skills to check; each must be one the database's model lists.

    Raises:
        SkillReadError: If a skill's ``SKILL.md`` is missing from the snapshot; a decode failure is a finding.
    """
    reports: list[SkillReport] = []
    for ref in refs:
        frontmatter = _skill_frontmatter(database, ref)
        match frontmatter:
            case SkillDecodeError():
                reports.append(SkillReport(ref, violations=(_undecodable_skill(),)))
            case Frontmatter():
                frontmatter_result = validate_skill(
                    SKILL_FRONTMATTER_SCHEMA, frontmatter=frontmatter, directory_name=ref.directory.name
                )
                link_result = _skill_links(database, ref)
                metadata_result = validate_skill_metadata(
                    frontmatter=frontmatter, listed=_listed_files(database, frontmatter)
                )
                violations = frontmatter_result.violations + link_result.violations + metadata_result.violations
                reports.append(SkillReport(ref, violations=violations))
            case MissingFrontmatter() | InvalidYamlFrontmatter() | NonMappingFrontmatter():
                # No mapping, so no `metadata` to read; the frontmatter check reports the frontmatter itself.
                frontmatter_result = validate_skill(
                    SKILL_FRONTMATTER_SCHEMA, frontmatter=frontmatter, directory_name=ref.directory.name
                )
                link_result = _skill_links(database, ref)
                violations = frontmatter_result.violations + link_result.violations
                reports.append(SkillReport(ref, violations=violations))
            case _:
                assert_never(frontmatter)
    return SkillCheckRun(reports=tuple(reports))


def _skill_links(database: Database, ref: SkillRef) -> SkillCheckResult:
    """The link violations of a skill whose frontmatter was already read and decoded. Raises nothing.

    The frontmatter was read and decoded from the same bytes the parse reads, so the parse cannot fail on them.
    """
    parsed = database.skill_parse(ref)
    return validate_skill_links(links=parsed.links, anchors=parsed.anchors)


def _listed_files(database: Database, frontmatter: Frontmatter) -> tuple[ListedFiles, ...]:
    """The files a skill's ``metadata`` lists, subkey by subkey, each path with what the snapshot holds there.

    A path written twice is located twice, so each of its entries carries its own state. Raises nothing.
    """
    listed: list[ListedFiles] = []
    for subkey, written_paths in listed_by_subkey(frontmatter):
        files: list[ListedFile] = []
        for written in written_paths:
            files.append(ListedFile(written=written, state=_listed_file_state(database, written)))
        listed.append(ListedFiles(subkey=subkey, files=tuple(files)))
    return tuple(listed)


def _listed_file_state(database: Database, written: str) -> ListedFileState:
    """What the snapshot can tell about one path a skill lists under ``metadata``, as written there.

    The path is parsed here, once: one that is absolute or climbs with ``..`` names nothing under the root the
    snapshot was taken of, so it is outside the scope like any other path the snapshot never read. A file is in
    the scope wherever the snapshot holds it, links followed, even in a directory it did not list, such as a file a
    linked ``SKILL.md`` leads to. Otherwise the path's directory decides: listed, the path is in the scope; not,
    the snapshot cannot tell, and the path is outside it.
    """
    try:
        path = RootRelativePath.parse(written)
    except RootRelativePathError:
        return ListedFileState.OUTSIDE_SCOPE
    if database.resolve_file(path) is not None:
        return ListedFileState.IN_SCOPE
    if database.is_listed(path.parent):
        return ListedFileState.IN_SCOPE
    return ListedFileState.OUTSIDE_SCOPE


def _budgeted(aspects: tuple[StructureAspect, ...]) -> tuple[StructureAspect, ...]:
    """The structure aspects that set a ``tokens`` budget, in the order given."""
    budgeted: list[StructureAspect] = []
    for aspect in aspects:
        if aspect.tokens is not None:
            budgeted.append(aspect)
    return tuple(budgeted)


def _frontmatter(database: Database, ref: DocumentRef) -> FrontmatterNode | DocumentDecodeError:
    """The document's frontmatter node, or the decode failure when its bytes are not UTF-8.

    Returns:
        The frontmatter node, or the decode failure when the document is present but not UTF-8: such bytes are on
        the same side of the line as invalid YAML, since the document is wrong, so the caller reports a finding
        rather than taking the exit-2 path an unreadable file takes.

    Raises:
        DocumentReadError: If the document is missing from the snapshot; a decode failure is not raised.
    """
    try:
        return database.frontmatter(ref)
    except DocumentDecodeError as exc:
        return exc


def _parse(database: Database, ref: DocumentRef) -> ParsedDocument | DocumentDecodeError:
    """The document's parse tree, or the decode failure when its bytes are not UTF-8.

    Returns:
        The parse tree, or the decode failure when the document is present but not UTF-8: such bytes are on the same
        side of the line as invalid YAML, since the document is wrong, so the caller reports a finding rather than
        taking the exit-2 path an unreadable file takes.

    Raises:
        DocumentReadError: If the document is missing from the snapshot; a decode failure is not raised.
    """
    try:
        return database.parse(ref)
    except DocumentDecodeError as exc:
        return exc


def _tokens(database: Database, ref: DocumentRef) -> int | DocumentDecodeError:
    """The tokens in the document's whole file, or the decode failure when its bytes are not UTF-8.

    Returns:
        The token count, or the decode failure when the document is present but not UTF-8: such bytes are on the same
        side of the line as invalid YAML, since the document is wrong, so the caller reports a finding rather than
        taking the exit-2 path an unreadable file takes.

    Raises:
        DocumentReadError: If the document is missing from the snapshot; a decode failure is not raised.
    """
    try:
        return database.tokens(ref)
    except DocumentDecodeError as exc:
        return exc


def _skill_frontmatter(database: Database, ref: SkillRef) -> FrontmatterNode | SkillDecodeError:
    """The skill's frontmatter node, or the decode failure when its ``SKILL.md`` is not UTF-8.

    Returns:
        The frontmatter node, or the decode failure when the ``SKILL.md`` is present but not UTF-8: such bytes are
        on the same side of the line as invalid YAML, since the skill is wrong, so the caller reports a finding
        rather than taking the exit-2 path an unreadable file takes.

    Raises:
        SkillReadError: If the skill's ``SKILL.md`` is missing from the snapshot; a decode failure is not raised.
    """
    try:
        return database.skill_frontmatter(ref)
    except SkillDecodeError as exc:
        return exc


def _undecodable(rule_namespace: str) -> Violation:
    """The violation a governed document that is not UTF-8 carries instead of the check's own."""
    return Violation(
        line=LineNumber(1),
        rule=f'{rule_namespace}.undecodable',
        message='document is not valid UTF-8',
    )


def _undecodable_skill() -> Violation:
    """The violation a skill whose ``SKILL.md`` is not UTF-8 carries instead of the check's own."""
    return Violation(
        line=LineNumber(1),
        rule='skill.undecodable',
        message='SKILL.md is not valid UTF-8',
    )
