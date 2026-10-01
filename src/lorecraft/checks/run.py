"""Run a check over documents, or over skills, of one database.

A run asks the database for everything it reads: the model decides which aspects govern each document, and
the part of the document the check reads is what the pure check validates — the frontmatter for the frontmatter
check, the parse tree's headings for the structure check, the whole file's token count for the budget check.
Selecting which documents to check is the caller's business: a run checks the refs it is handed, in the order
given, and reads only the governed ones. Every check reports in the same shape, so the `check` commands print
every run the same way.

The skill check runs over skills instead: the refs it is handed are the model's `SkillRef`s, the parts it reads are
the frontmatter, the line count, the links and the heading anchors of each `SKILL.md`, and the links of each of the
skill's resources, and the Agent Skills specification governs every one of them, so a skill is never ungoverned. The
files a skill links in through `metadata` are checked too, against what the snapshot holds at each path listed, and
so is each path inside the skill a link names, against what the snapshot holds there. It reports in a shape of its
own, a `SkillCheckRun` of `SkillReport`s, each locating a violation in the file it was found in: the `SKILL.md`, or
a resource.
"""

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Literal, assert_never

from lorecraft.core.path import RootRelativePath, RootRelativePathError
from lorecraft.project.document import DocumentDecodeError, DocumentRef
from lorecraft.project.schemas import SKILL_FRONTMATTER_SCHEMA, StructureAspect
from lorecraft.project.skill import SkillDecodeError, SkillRef, SkillResourceDecodeError, SkillResourceRef
from lorecraft.project.syntax import (
    Frontmatter,
    FrontmatterNode,
    InvalidYamlFrontmatter,
    LineNumber,
    Link,
    MissingFrontmatter,
    NonMappingFrontmatter,
    ParsedDocument,
)

from .budget import validate_budget
from .database import Database
from .frontmatter import validate_frontmatter
from .reporting import Finding, Violation
from .skill import SkillCheckResult, validate_skill
from .skill_length import validate_skill_length
from .skill_link import LinkTargetState, link_path_in_skill, validate_skill_links, validate_skill_resource_links
from .skill_metadata import (
    ListedFile,
    ListedFiles,
    ListedFileState,
    linked_in_paths,
    listed_by_subkey,
    validate_skill_metadata,
)
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
class SkillResourceReport:
    """The outcome of checking one resource of a selected skill.

    Attributes:
        ref: The resource the report is about; its path, where an agent reaches it, is the report path.
        violations: What the check found in the resource, without its path; empty when the resource conforms.
    """

    ref: SkillResourceRef
    violations: tuple[Violation, ...]

    def findings(self) -> tuple[Finding, ...]:
        """Every violation, located in the resource; empty exactly when the resource is clean."""
        return tuple(Finding.at(self.ref.path, violation) for violation in self.violations)


@dataclass(frozen=True, slots=True)
class SkillReport:
    """The outcome of checking one selected skill.

    Attributes:
        ref: The skill the report is about; its `SKILL.md` path is the report path of `violations`.
        violations: What the check found in the skill's `SKILL.md`, without its path; empty when it conforms.
        resources: One per resource of the skill, in the order the database lists them, by path.
    """

    ref: SkillRef
    violations: tuple[Violation, ...]
    resources: tuple[SkillResourceReport, ...]

    def findings(self) -> tuple[Finding, ...]:
        """Every violation, located in its file; empty exactly when the skill is clean.

        Findings in the `SKILL.md` come first, in the order the check found them, then each resource's, in report
        order.
        """
        findings = [Finding.at(self.ref.path, violation) for violation in self.violations]
        for resource in self.resources:
            findings.extend(resource.findings())
        return tuple(findings)


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
    """Check each skill's frontmatter, its length, its links and the files its `metadata` lists, in the order given.

    Every skill is governed: the Agent Skills specification applies to each one. The violations in a skill's
    `SKILL.md` list the frontmatter's first, then the line budget's, then the links', then, when the frontmatter
    is a mapping, its `metadata`'s; a skill whose `metadata` lists no file has none of those. A skill whose
    `SKILL.md` is not UTF-8 carries there the single violation `skill.undecodable` at line 1: it is never parsed,
    and its lines are not counted.

    Each resource of the skill is checked on its own, whatever its `SKILL.md` holds, and reported in its own
    report: its links' violations, in document order, or, when it is not UTF-8, the single violation
    `skill.undecodable` at line 1, without a parse.

    Which files `metadata` links in is known only when the `SKILL.md`'s frontmatter is a mapping. When it is
    missing, unparseable or not a mapping, or the `SKILL.md` is not UTF-8, any path might be linked in, so no
    link in the `SKILL.md` or in any resource is judged `skill.link-broken`; the other link rules still apply.

    Args:
        database: The snapshot state the refs come from.
        refs: The skills to check; each must be one the database's model lists.

    Raises:
        SkillReadError: If a skill's `SKILL.md` is missing from the snapshot; a decode failure is a finding.
        SkillResourcesListError: If a directory the walk over a skill's resources enters cannot be listed.
        SkillResourcesSymlinkResolveError: If a symlink the walk over a skill's resources meets cannot be resolved.
        SkillResourceReadError: If a resource is missing from the snapshot; a decode failure is a finding.
    """
    reports: list[SkillReport] = []
    for ref in refs:
        frontmatter = _skill_frontmatter(database, ref)
        violations: tuple[Violation, ...]
        # `None` while the `metadata` cannot be read: unknown, not empty.
        linked_in: frozenset[PurePosixPath] | None
        match frontmatter:
            case SkillDecodeError():
                violations = (_undecodable_skill('SKILL.md'),)
                linked_in = None
            case Frontmatter():
                linked_in = linked_in_paths(frontmatter)
                frontmatter_result = validate_skill(
                    SKILL_FRONTMATTER_SCHEMA, frontmatter=frontmatter, directory_name=ref.directory.name
                )
                length_result = _skill_length(database, ref)
                link_result = _skill_links(database, ref, linked_in=linked_in)
                metadata_result = validate_skill_metadata(
                    frontmatter=frontmatter, listed=_listed_files(database, frontmatter)
                )
                violations = (
                    frontmatter_result.violations
                    + length_result.violations
                    + link_result.violations
                    + metadata_result.violations
                )
            case MissingFrontmatter() | InvalidYamlFrontmatter() | NonMappingFrontmatter():
                # No mapping, so no `metadata` to read; the frontmatter check reports the frontmatter itself.
                linked_in = None
                frontmatter_result = validate_skill(
                    SKILL_FRONTMATTER_SCHEMA, frontmatter=frontmatter, directory_name=ref.directory.name
                )
                length_result = _skill_length(database, ref)
                link_result = _skill_links(database, ref, linked_in=linked_in)
                violations = frontmatter_result.violations + length_result.violations + link_result.violations
            case _:
                assert_never(frontmatter)
        resources = _skill_resource_reports(database, ref, linked_in=linked_in)
        reports.append(SkillReport(ref, violations=violations, resources=resources))
    return SkillCheckRun(reports=tuple(reports))


def _skill_length(database: Database, ref: SkillRef) -> SkillCheckResult:
    """The line budget violations of a skill whose frontmatter was already read and decoded. Raises nothing.

    The frontmatter was read and decoded from the same bytes the line count reads, so the count cannot fail on them.

    Args:
        database: Where the lines of the skill's `SKILL.md` are counted.
        ref: The skill whose `SKILL.md` is held to the line budget.
    """
    return validate_skill_length(line_count=database.skill_lines(ref))


def _skill_links(database: Database, ref: SkillRef, *, linked_in: frozenset[PurePosixPath] | None) -> SkillCheckResult:
    """The link violations of a skill whose frontmatter was already read and decoded. Raises nothing.

    The frontmatter was read and decoded from the same bytes the parse reads, so the parse cannot fail on them.

    Args:
        database: Where the skill's parse tree is read from, and each path its links name is looked up.
        ref: The skill whose `SKILL.md` links are checked.
        linked_in: Every path inside the skill the skill's `metadata` links a file in at, or `None` when that
            `metadata` is unknown.
    """
    parsed = database.skill_parse(ref)
    return validate_skill_links(
        links=parsed.links,
        anchors=parsed.anchors,
        targets=_link_targets(database, ref, parsed.links),
        linked_in=linked_in,
    )


def _link_targets(database: Database, ref: SkillRef, links: tuple[Link, ...]) -> dict[PurePosixPath, LinkTargetState]:
    """What the snapshot holds at each path inside the skill the links name, keyed by that path. Raises nothing.

    A link that names no path inside the skill, such as a URL, an absolute, a fragment-only or an escaping link,
    is not looked up.

    Args:
        database: Where each path is looked up in the snapshot.
        ref: The skill the links are read from, from its root, whichever of its files holds them.
        links: The links of one of the skill's files, in document order.
    """
    targets: dict[PurePosixPath, LinkTargetState] = {}
    for link in links:
        path = link_path_in_skill(link)
        if path is not None:
            targets[path] = _link_target_state(database, ref, path)
    return targets


def _link_target_state(database: Database, ref: SkillRef, path: PurePosixPath) -> LinkTargetState:
    """What the snapshot holds at one path inside a skill, read from the skill's root. Raises nothing.

    Args:
        database: Where the path is looked up in the snapshot.
        ref: The skill the path is read from.
        path: A path inside the skill, relative to its root: normalised, with no `..` component, and not absolute.
    """
    # Joined to `ref.directory`, the directory an agent reaches the skill by, never to the real directory it
    # leads to: `find_real_path` then follows every symlink on the way, the skill's own entry and any inside it,
    # as an agent's read of the path would. Only what is left after the lexical normalisation is followed: a `..`
    # the link wrote already cancelled the component before it as spelled, so `guides/../SKILL.md` is
    # `SKILL.md`, whatever directory a `guides` symlink leads to. With no `..` left, the join stays root-relative.
    joined = ref.directory / str(path)
    if database.find_real_path(joined) is None:
        return LinkTargetState.MISSING
    return LinkTargetState.PRESENT


def _skill_resource_reports(
    database: Database, ref: SkillRef, *, linked_in: frozenset[PurePosixPath] | None
) -> tuple[SkillResourceReport, ...]:
    """One report per resource of a skill, in the order the database lists them.

    Args:
        database: Where the skill's resources are listed, each one's parse tree is read from, and each path a
            link names is looked up.
        ref: The skill whose resources are checked.
        linked_in: Every path inside the skill the skill's `metadata` links a file in at, or `None` when that
            `metadata` is unknown.

    Raises:
        SkillResourcesListError: If a directory the walk over the skill's resources enters cannot be listed.
        SkillResourcesSymlinkResolveError: If a symlink the walk over the skill's resources meets cannot be
            resolved.
        SkillResourceReadError: If a resource is missing from the snapshot; a decode failure is a finding.
    """
    reports: list[SkillResourceReport] = []
    for location in database.skill_resources(ref):
        resource = location.ref
        parsed = _skill_resource_parse(database, resource)
        match parsed:
            case SkillResourceDecodeError():
                reports.append(SkillResourceReport(resource, violations=(_undecodable_skill('resource'),)))
            case ParsedDocument():
                result = validate_skill_resource_links(
                    links=parsed.links, targets=_link_targets(database, ref, parsed.links), linked_in=linked_in
                )
                reports.append(SkillResourceReport(resource, violations=result.violations))
            case _:
                assert_never(parsed)
    return tuple(reports)


def _listed_files(database: Database, frontmatter: Frontmatter) -> tuple[ListedFiles, ...]:
    """The files a skill's `metadata` lists, subkey by subkey, each path with what the snapshot holds there.

    A path written twice is located twice, so each of its entries carries its own state. Raises nothing.

    Args:
        database: Where each listed path is looked up in the snapshot.
        frontmatter: The skill's decoded frontmatter, whose `metadata` is read.
    """
    listed: list[ListedFiles] = []
    for subkey, written_paths in listed_by_subkey(frontmatter):
        files: list[ListedFile] = []
        for written in written_paths:
            files.append(ListedFile(written=written, state=_listed_file_state(database, written)))
        listed.append(ListedFiles(subkey=subkey, files=tuple(files)))
    return tuple(listed)


def _listed_file_state(database: Database, written: str) -> ListedFileState:
    """What the snapshot can tell about one path a skill lists under `metadata`, as written there.

    Two questions decide it, kept apart as an IDE keeps them: whether the snapshot holds a file there, and
    whether the path is in the scope the scan declares. The path is parsed here, once: one that is absolute or
    climbs with `..` names nothing under the root the snapshot was taken of, so it is outside the scope. A file
    is present wherever the snapshot holds it, links followed, even in a directory the scope does not cover,
    such as a file a linked `SKILL.md` leads to. Otherwise a path in the scope is missing, whether it names
    nothing, a directory, or a link to no file the snapshot holds, because it dangles, leaves the repository or
    reaches a file the snapshot never read, and whether or not its directory exists; a path outside the scope is
    one the snapshot cannot tell about.

    Args:
        database: Where the path is looked up in the snapshot and asked about the scope.
        written: The path exactly as the skill wrote it, unparsed and unresolved.
    """
    try:
        path = RootRelativePath.parse(written)
    except RootRelativePathError:
        return ListedFileState.OUTSIDE_SCOPE
    if database.find_real_file(path) is not None:
        return ListedFileState.PRESENT
    if database.is_in_scope(path):
        return ListedFileState.MISSING
    return ListedFileState.OUTSIDE_SCOPE


def _budgeted(aspects: tuple[StructureAspect, ...]) -> tuple[StructureAspect, ...]:
    """The structure aspects that set a `tokens` budget, in the order given.

    Args:
        aspects: The structure aspects governing a document; those without a `tokens` budget are dropped.
    """
    budgeted: list[StructureAspect] = []
    for aspect in aspects:
        if aspect.tokens is not None:
            budgeted.append(aspect)
    return tuple(budgeted)


def _frontmatter(database: Database, ref: DocumentRef) -> FrontmatterNode | DocumentDecodeError:
    """The document's frontmatter node, or the decode failure when its bytes are not UTF-8.

    Args:
        database: Where the frontmatter is read and cached.
        ref: Document whose frontmatter is wanted; its bytes are decoded once, by the database.

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

    Args:
        database: Where the parse tree is read and cached.
        ref: Document whose parse tree is wanted; parsed once, by the database.

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

    Args:
        database: Where the token count is computed and cached.
        ref: Document whose whole file is counted, frontmatter and code included.

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
    """The skill's frontmatter node, or the decode failure when its `SKILL.md` is not UTF-8.

    Args:
        database: Where the frontmatter is read and cached.
        ref: The skill whose `SKILL.md` is read.

    Returns:
        The frontmatter node, or the decode failure when the `SKILL.md` is present but not UTF-8: such bytes are
        on the same side of the line as invalid YAML, since the skill is wrong, so the caller reports a finding
        rather than taking the exit-2 path an unreadable file takes.

    Raises:
        SkillReadError: If the skill's `SKILL.md` is missing from the snapshot; a decode failure is not raised.
    """
    try:
        return database.skill_frontmatter(ref)
    except SkillDecodeError as exc:
        return exc


def _skill_resource_parse(database: Database, ref: SkillResourceRef) -> ParsedDocument | SkillResourceDecodeError:
    """The resource's parse tree, or the decode failure when the resource is not UTF-8.

    Args:
        database: Where the parse tree is read and cached.
        ref: The resource whose file is parsed, as the database lists it.

    Returns:
        The parse tree, or the decode failure when the resource is present but not UTF-8: such bytes are on the
        same side of the line as invalid YAML, since the skill is wrong, so the caller reports a finding rather
        than taking the exit-2 path an unreadable file takes.

    Raises:
        SkillResourceReadError: If the resource is missing from the snapshot; a decode failure is not raised.
        SkillResourcesListError: If the skill's resources are not listed yet and a directory the walk enters
            cannot be listed.
        SkillResourcesSymlinkResolveError: If the skill's resources are not listed yet and a symlink the walk meets
            cannot be resolved.
    """
    try:
        return database.skill_resource_parse(ref)
    except SkillResourceDecodeError as exc:
        return exc


def _undecodable(rule_namespace: str) -> Violation:
    """The violation a governed document that is not UTF-8 carries instead of the check's own.

    Args:
        rule_namespace: Prefix of the `undecodable` rule: the document's corpus.
    """
    return Violation(
        line=LineNumber(1),
        rule=f'{rule_namespace}.undecodable',
        message='document is not valid UTF-8',
    )


def _undecodable_skill(file: Literal['SKILL.md', 'resource']) -> Violation:
    """The violation a skill's `SKILL.md` or resource that is not UTF-8 carries instead of the check's own.

    A resource shares `skill.undecodable` with the `SKILL.md` deliberately: the rule is the same, a file of the
    skill that is not UTF-8, and the finding's path already tells which file it is.

    Args:
        file: What the file is to the skill, as the message names it.
    """
    return Violation(
        line=LineNumber(1),
        rule='skill.undecodable',
        message=f'{file} is not valid UTF-8',
    )
