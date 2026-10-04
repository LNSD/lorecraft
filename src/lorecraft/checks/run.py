"""Run a check over documents, or over skills, of one database.

A run asks the database for everything it reads: the model decides which specifications govern each document, and
the part of the document the check reads is what the pure check validates — the frontmatter for the frontmatter
check, the parse tree's headings for the structure check, the whole file's token count for the budget check.
Selecting which documents to check is the caller's business: a run checks the refs it is handed, in the order
given, and reads only the governed ones. Every check reports in the same shape, so the `check` commands print
every run the same way.

The skill check runs over skills instead: it is handed a `SkillSelection` per skill, the `SkillLocation` the model
hands out for it and how much of the skill to check, the whole skill or its `SKILL.md` alone. The parts it reads
are the frontmatter and the line count of each `SKILL.md`, and the links and the heading anchors of the `SKILL.md`
and, for a whole skill, of each of the skill's resources, and the Agent Skills specification governs every one of
them, so a skill is never ungoverned. The files a skill links in through `metadata` are checked too, against what
the snapshot holds at each path listed, and so is each path inside the skill a link names, against what the
snapshot holds there. It reports in a shape of its own, a `SkillCheckRun` of `SkillReport`s, each locating a
violation in the file it was found in: the `SKILL.md`, or a resource. A symlink of the skill layout whose chain
leaves the repository is reported at the path an agent reaches it by, in a `SymlinkReport`: under its skill's report
when it is inside a skill, and in the run's own layout reports when it is a skills directory, an entry or an entry's
`SKILL.md`, none of which is a skill.
"""

from dataclasses import dataclass
from enum import Enum
from pathlib import PurePosixPath
from typing import Literal, assert_never

from lorecraft.core.path import RootRelativePath, RootRelativePathError
from lorecraft.project.document import DocumentRef
from lorecraft.project.schemas import SKILL_FRONTMATTER_SCHEMA, StructureSpec
from lorecraft.project.skill import OutsideSymlink, SkillLocation, SkillRef, SkillResourceRef
from lorecraft.project.syntax import (
    Frontmatter,
    InvalidYamlFrontmatter,
    LineNumber,
    Link,
    MissingFrontmatter,
    NonMappingFrontmatter,
)

from .budget import validate_budget
from .database import Database
from .frontmatter import validate_frontmatter
from .reporting import Finding, Violation
from .skill import SkillCheckResult, validate_skill
from .skill_length import validate_skill_length
from .skill_link import LinkTargetState, link_path_in_skill, validate_skill_links
from .skill_metadata import (
    ListedFile,
    ListedFiles,
    ListedFileState,
    linked_in_paths,
    listed_by_subkey,
    validate_skill_metadata,
)
from .skill_symlink import validate_outside_symlink
from .structure import validate_structure
from .text import DocumentText, SkillResourceText, SkillText, Undecodable


@dataclass(frozen=True, slots=True)
class GovernedDocumentReport:
    """The outcome of checking one selected document that a specification governs with rules the check applies.

    Attributes:
        ref: The document the report is about; its path is the report path.
        violations: What the check found, without the document's path; empty when the document conforms.
    """

    ref: DocumentRef
    violations: tuple[Violation, ...]

    def findings(self) -> tuple[Finding, ...]:
        """Every violation, located in the report's document; empty exactly when the document is clean."""
        return tuple(Finding.at(self.ref.path, violation) for violation in self.violations)


@dataclass(frozen=True, slots=True)
class UngovernedDocumentReport:
    """The outcome of selecting a document no specification governs with rules the check applies.

    The document was never parsed, so there is nothing it could violate.

    Attributes:
        ref: The document the report is about; its path is the report path.
    """

    ref: DocumentRef


type DocumentReport = GovernedDocumentReport | UngovernedDocumentReport
"""The outcome of checking one selected document: governed and checked, or ungoverned and never read."""


@dataclass(frozen=True, slots=True)
class CheckRun:
    """One pass of one check over the selected documents: what the text and JSON printers consume.

    Attributes:
        reports: One per selected document, in the order the refs were given.
    """

    reports: tuple[DocumentReport, ...]

    def findings(self) -> tuple[Finding, ...]:
        """Every finding of every governed report, in report order; empty exactly when the run is clean."""
        findings: list[Finding] = []
        for report in self.reports:
            match report:
                case GovernedDocumentReport():
                    findings.extend(report.findings())
                case UngovernedDocumentReport():
                    pass
                case _:
                    assert_never(report)
        return tuple(findings)


class SkillScope(Enum):
    """How much of a skill a run checks."""

    WHOLE_SKILL = 'whole-skill'
    """The `SKILL.md` and every resource of the skill."""
    SKILL_FILE = 'skill-file'
    """The `SKILL.md` alone: no resource is read or reported."""


@dataclass(frozen=True, slots=True)
class SkillSelection:
    """One skill a run is handed, and how much of it to check.

    Attributes:
        location: The skill and where its files live, as the database's model hands it out; the run walks the
            skill's resources from it and reads where its directory leads from it.
        scope: How much of the skill the run checks. A link in the `SKILL.md` is judged against every file of the
            skill either way, so a link to a resource is not broken when the resource itself goes unchecked.
    """

    location: SkillLocation
    scope: SkillScope

    @property
    def ref(self) -> SkillRef:
        """The skill selected."""
        return self.location.ref


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
class SymlinkReport:
    """The outcome of checking one symlink of the skill layout whose chain leaves the repository.

    Attributes:
        path: Where an agent reaches the symlink, the report path: a skills directory as declared, an entry in a
            skills directory, an entry's `SKILL.md`, or a path inside a skill.
        violations: What the check found at the symlink, without its path.
    """

    path: RootRelativePath
    violations: tuple[Violation, ...]

    def findings(self) -> tuple[Finding, ...]:
        """Every violation, located at the symlink."""
        return tuple(Finding.at(self.path, violation) for violation in self.violations)


@dataclass(frozen=True, slots=True)
class SkillReport:
    """The outcome of checking one selected skill.

    Attributes:
        ref: The skill the report is about; its `SKILL.md` path is the report path of `violations`.
        violations: What the check found in the skill's `SKILL.md`, without its path; empty when it conforms.
        resources: One per resource of the skill, in the order the database lists them, by path; empty when the
            selection named the `SKILL.md` alone.
        symlinks: One per symlink inside the skill whose chain leaves the repository, by path; empty when the
            selection named the `SKILL.md` alone.
    """

    ref: SkillRef
    violations: tuple[Violation, ...]
    resources: tuple[SkillResourceReport, ...]
    symlinks: tuple[SymlinkReport, ...]

    def findings(self) -> tuple[Finding, ...]:
        """Every violation, located in its file; empty exactly when the skill is clean.

        Findings in the `SKILL.md` come first, in the order the check found them, then each resource's, in report
        order, then each symlink's.
        """
        findings = [Finding.at(self.ref.path, violation) for violation in self.violations]
        for resource in self.resources:
            findings.extend(resource.findings())
        for symlink in self.symlinks:
            findings.extend(symlink.findings())
        return tuple(findings)


@dataclass(frozen=True, slots=True)
class SkillCheckRun:
    """One pass of the skill check over the selected skills: what the text and JSON printers consume.

    Attributes:
        layout: One per skills directory, skill entry or entry's `SKILL.md` whose symlink chain leaves the
            repository, by path. None of them is a skill, so none is among `reports`, and none is counted as one.
        reports: One per selected skill, in the order the selections were given.
    """

    layout: tuple[SymlinkReport, ...]
    reports: tuple[SkillReport, ...]

    def findings(self) -> tuple[Finding, ...]:
        """Every finding of the layout, then of every report, in report order; empty exactly when the run is clean."""
        findings: list[Finding] = []
        for symlink in self.layout:
            findings.extend(symlink.findings())
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
        refs: The documents to check; one in no corpus the database's model holds is ungoverned.

    Raises:
        DocumentReadError: If a governed document is missing from the snapshot; a decode failure is a finding.
        DirListError: If the model is not loaded yet and the specification directory or docs/ cannot be listed.
        CorpusListError: If the model is not loaded yet and a corpus directory cannot be listed.
        StructureSchemaReadError: If the model is not loaded yet and a structure specification cannot be read.
        StructureSpecDecodeError: If the model is not loaded yet and a structure specification is not JSON in the
            dialect's shape.
        EmptyStructureSpecError: If the model is not loaded yet and a structure specification states no rule.
        RepeatedOutlineSectionError: If the model is not loaded yet and an outline names a section twice.
        RepeatedForbiddenSectionError: If the model is not loaded yet and a specification forbids a section twice.
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
        EntryInspectError: If the model is not loaded yet and an entry on the way to a skills directory cannot be
            inspected, or a link's target read, while looking for where it leaves the repository.
        SkillsDirListError: If the model is not loaded yet and a skills directory cannot be listed.
        SkillEntryResolveError: If the model is not loaded yet and a symlinked skill entry cannot be resolved.
        SkillDirListError: If the model is not loaded yet and a skill directory cannot be listed.
        SkillFileResolveError: If the model is not loaded yet and a symlinked SKILL.md cannot be resolved.
    """
    reports: list[DocumentReport] = []
    for ref in refs:
        governance = database.model().find_governance(ref)
        if governance is None:
            reports.append(UngovernedDocumentReport(ref))
            continue
        schemas = governance.frontmatter_schemas()
        if not schemas:
            reports.append(UngovernedDocumentReport(ref))
            continue
        source = database.text(ref)
        match source:
            case Undecodable():
                reports.append(GovernedDocumentReport(ref, violations=(_undecodable('frontmatter'),)))
            case DocumentText():
                result = validate_frontmatter(
                    schemas, frontmatter=database.frontmatter(source), filename=ref.filename, corpus=ref.corpus
                )
                reports.append(GovernedDocumentReport(ref, violations=result.violations))
            case _:
                assert_never(source)
    return CheckRun(reports=tuple(reports))


def run_structure(database: Database, refs: tuple[DocumentRef, ...]) -> CheckRun:
    """Check each ref against the structure specifications that govern it, in the order given.

    A governed document that is not UTF-8 carries the single violation ``structure.undecodable`` at line 1.

    Args:
        database: The snapshot state the refs come from; its model decides which specifications govern each
            document.
        refs: The documents to check; one in no corpus the database's model holds is ungoverned.

    Raises:
        DocumentReadError: If a governed document is missing from the snapshot; a decode failure is a finding.
        DirListError: If the model is not loaded yet and the specification directory or docs/ cannot be listed.
        CorpusListError: If the model is not loaded yet and a corpus directory cannot be listed.
        StructureSchemaReadError: If the model is not loaded yet and a structure specification cannot be read.
        StructureSpecDecodeError: If the model is not loaded yet and a structure specification is not JSON in the
            dialect's shape.
        EmptyStructureSpecError: If the model is not loaded yet and a structure specification states no rule.
        RepeatedOutlineSectionError: If the model is not loaded yet and an outline names a section twice.
        RepeatedForbiddenSectionError: If the model is not loaded yet and a specification forbids a section twice.
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
        EntryInspectError: If the model is not loaded yet and an entry on the way to a skills directory cannot be
            inspected, or a link's target read, while looking for where it leaves the repository.
        SkillsDirListError: If the model is not loaded yet and a skills directory cannot be listed.
        SkillEntryResolveError: If the model is not loaded yet and a symlinked skill entry cannot be resolved.
        SkillDirListError: If the model is not loaded yet and a skill directory cannot be listed.
        SkillFileResolveError: If the model is not loaded yet and a symlinked SKILL.md cannot be resolved.
    """
    reports: list[DocumentReport] = []
    for ref in refs:
        governance = database.model().find_governance(ref)
        if governance is None:
            reports.append(UngovernedDocumentReport(ref))
            continue
        structure_specs = governance.structure_specs()
        if not structure_specs:
            reports.append(UngovernedDocumentReport(ref))
            continue
        source = database.text(ref)
        match source:
            case Undecodable():
                reports.append(GovernedDocumentReport(ref, violations=(_undecodable('structure'),)))
            case DocumentText():
                result = validate_structure(structure_specs, headings=database.parse(source).headings)
                reports.append(GovernedDocumentReport(ref, violations=result.violations))
            case _:
                assert_never(source)
    return CheckRun(reports=tuple(reports))


def run_budget(database: Database, refs: tuple[DocumentRef, ...]) -> CheckRun:
    """Check each ref's whole-file token count against the budgets that govern it, in the order given.

    A document is governed when at least one of its structure specifications sets a ``tokens`` budget; one whose
    specifications set none is ungoverned, and its text is never read. A governed document that is not UTF-8
    carries the single violation ``budget.undecodable`` at line 1.

    Args:
        database: The snapshot state the refs come from; its model decides which specifications govern each
            document.
        refs: The documents to check; one in no corpus the database's model holds is ungoverned.

    Raises:
        DocumentReadError: If a governed document is missing from the snapshot; a decode failure is a finding.
        DirListError: If the model is not loaded yet and the specification directory or docs/ cannot be listed.
        CorpusListError: If the model is not loaded yet and a corpus directory cannot be listed.
        StructureSchemaReadError: If the model is not loaded yet and a structure specification cannot be read.
        StructureSpecDecodeError: If the model is not loaded yet and a structure specification is not JSON in the
            dialect's shape.
        EmptyStructureSpecError: If the model is not loaded yet and a structure specification states no rule.
        RepeatedOutlineSectionError: If the model is not loaded yet and an outline names a section twice.
        RepeatedForbiddenSectionError: If the model is not loaded yet and a specification forbids a section twice.
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
        EntryInspectError: If the model is not loaded yet and an entry on the way to a skills directory cannot be
            inspected, or a link's target read, while looking for where it leaves the repository.
        SkillsDirListError: If the model is not loaded yet and a skills directory cannot be listed.
        SkillEntryResolveError: If the model is not loaded yet and a symlinked skill entry cannot be resolved.
        SkillDirListError: If the model is not loaded yet and a skill directory cannot be listed.
        SkillFileResolveError: If the model is not loaded yet and a symlinked SKILL.md cannot be resolved.
    """
    reports: list[DocumentReport] = []
    for ref in refs:
        governance = database.model().find_governance(ref)
        if governance is None:
            reports.append(UngovernedDocumentReport(ref))
            continue
        structure_specs = _budgeted(governance.structure_specs())
        if not structure_specs:
            reports.append(UngovernedDocumentReport(ref))
            continue
        source = database.text(ref)
        match source:
            case Undecodable():
                reports.append(GovernedDocumentReport(ref, violations=(_undecodable('budget'),)))
            case DocumentText():
                result = validate_budget(structure_specs, token_count=database.tokens(source))
                reports.append(GovernedDocumentReport(ref, violations=result.violations))
            case _:
                assert_never(source)
    return CheckRun(reports=tuple(reports))


def run_skills(database: Database, selections: tuple[SkillSelection, ...]) -> SkillCheckRun:
    """Check each skill's frontmatter, its length, its links and the files its `metadata` lists, in the order given.

    Every skill is governed: the Agent Skills specification applies to each one. The violations in a skill's
    `SKILL.md` list the frontmatter's first, then the line budget's, then the links', then, when the frontmatter
    is a mapping, its `metadata`'s; a skill whose `metadata` lists no file has none of those. A skill whose
    `SKILL.md` is not UTF-8 carries there the single violation `skill.undecodable` at line 1: it is never parsed,
    and its lines are not counted.

    When the selection covers the whole skill, each resource of the skill is checked on its own, whatever its
    `SKILL.md` holds, and reported in its own report: its links' violations, in document order, or, when it is not
    UTF-8, the single violation `skill.undecodable` at line 1, without a parse. When it covers the `SKILL.md`
    alone, no resource is read and the report holds none; a link in the `SKILL.md` is still judged against every
    file the snapshot holds in the skill, so a link to a resource is not broken.

    A symlink inside a skill whose chain leaves the repository is `skill.symlink-outside`, in the skill's report,
    when the selection covers the whole skill: like a resource, it is not looked at for the `SKILL.md` alone. So is
    each skills directory, skill entry and entry's `SKILL.md` whose chain leaves it, in the run's layout
    reports, whichever skills are selected: an agent lists the same skills directories to load any one skill.

    Which files `metadata` links in is known only when the `SKILL.md`'s frontmatter is a mapping. When it is
    missing, unparseable or not a mapping, or the `SKILL.md` is not UTF-8, any path might be linked in, so no
    link in the `SKILL.md` or in any resource is judged `skill.link-broken`; the other link rules still apply.

    Args:
        database: The snapshot state the refs come from.
        selections: The skills to check, each located as the database's model hands it out, with how much of it to
            check.

    Raises:
        SkillReadError: If a skill's `SKILL.md` is missing from the snapshot; a decode failure is a finding.
        SkillResourcesListError: If a directory the walk over a whole skill's resources enters cannot be listed.
        SkillResourcesSymlinkResolveError: If a symlink the walk over a whole skill's resources meets cannot be
            resolved.
        SkillResourceReadError: If a resource of a whole skill is missing from the snapshot; a decode failure is a
            finding.
    """
    reports: list[SkillReport] = []
    for selection in selections:
        ref = selection.ref
        source = database.skill_text(ref)
        violations: tuple[Violation, ...]
        # `None` while the `metadata` cannot be read: unknown, not empty.
        linked_in: frozenset[PurePosixPath] | None
        match source:
            case Undecodable():
                violations = (_undecodable_skill('SKILL.md'),)
                linked_in = None
            case SkillText():
                link_target = _link_target(selection.location)
                violations, linked_in = _skill_file_violations(database, source, link_target=link_target)
            case _:
                assert_never(source)
        resources: tuple[SkillResourceReport, ...] = ()
        symlinks: tuple[SymlinkReport, ...] = ()
        if selection.scope is SkillScope.WHOLE_SKILL:
            resources = _skill_resource_reports(database, selection.location, linked_in=linked_in)
            symlinks = _symlink_reports(database.skill_resources(selection.location).outside_symlinks)
        reports.append(SkillReport(ref, violations=violations, resources=resources, symlinks=symlinks))
    layout = _symlink_reports(database.model().outside_symlinks)
    return SkillCheckRun(layout=layout, reports=tuple(reports))


def _symlink_reports(outside_symlinks: tuple[OutsideSymlink, ...]) -> tuple[SymlinkReport, ...]:
    """One report per symlink whose chain leaves the repository, in the order given. Raises nothing.

    Args:
        outside_symlinks: The symlinks, as the model or a skill's resource listing records them.
    """
    reports: list[SymlinkReport] = []
    for outside in outside_symlinks:
        result = validate_outside_symlink(leaves_at=outside.leaves_at)
        reports.append(SymlinkReport(outside.path, violations=result.violations))
    return tuple(reports)


def _skill_file_violations(
    database: Database, source: SkillText, *, link_target: RootRelativePath | None
) -> tuple[tuple[Violation, ...], frozenset[PurePosixPath] | None]:
    """The violations in a skill's decoded `SKILL.md`, and the paths its `metadata` links files in at. Raises nothing.

    Args:
        database: Where the `SKILL.md`'s frontmatter, line count and parse tree are read, and each path its links
            and its `metadata` name is looked up.
        source: The skill's `SKILL.md` text, as the database decoded it.
        link_target: The resolved directory the skill's listed directory leads to when it is a link, or `None`
            when it is not, as `_link_target` reads it from the skill's location.

    Returns:
        The frontmatter's violations, then the line budget's, then the links', then, when the frontmatter is a
        mapping, its `metadata`'s; and every path inside the skill the `metadata` links a file in at, or `None` when
        the frontmatter is not a mapping, so the `metadata` is unknown.
    """
    ref = source.ref
    # `name` is held to the directory an agent lists, never to where a link leads: an agent opens
    # `<entry>/SKILL.md` and lets the OS follow any symlink. Where it leads only words a note.
    directory_name = ref.directory.name
    frontmatter = database.skill_frontmatter(source)
    length_result = validate_skill_length(line_count=database.skill_lines(source))
    match frontmatter:
        case Frontmatter():
            linked_in = linked_in_paths(frontmatter)
            frontmatter_result = validate_skill(
                SKILL_FRONTMATTER_SCHEMA,
                frontmatter=frontmatter,
                directory_name=directory_name,
                link_target=link_target,
            )
            link_result = _skill_links(database, source, linked_in=linked_in)
            metadata_result = validate_skill_metadata(
                frontmatter=frontmatter, listed=_listed_files(database, frontmatter)
            )
            violations = (
                frontmatter_result.violations
                + length_result.violations
                + link_result.violations
                + metadata_result.violations
            )
            return violations, linked_in
        case MissingFrontmatter() | InvalidYamlFrontmatter() | NonMappingFrontmatter():
            # No mapping, so no `metadata` to read; the frontmatter check reports the frontmatter itself.
            frontmatter_result = validate_skill(
                SKILL_FRONTMATTER_SCHEMA,
                frontmatter=frontmatter,
                directory_name=directory_name,
                link_target=link_target,
            )
            link_result = _skill_links(database, source, linked_in=None)
            violations = frontmatter_result.violations + length_result.violations + link_result.violations
            return violations, None
        case _:
            assert_never(frontmatter)


def _link_target(location: SkillLocation) -> RootRelativePath | None:
    """The resolved directory a skill's listed directory leads to when it is a link, or `None` when it is not.

    Read from the location the model records, never from the disk. Raises nothing.

    Args:
        location: The skill and where its files live, as the model hands it out.
    """
    if location.resolves_to == location.ref.directory:
        return None
    return location.resolves_to


def _skill_links(
    database: Database, source: SkillText, *, linked_in: frozenset[PurePosixPath] | None
) -> SkillCheckResult:
    """The link violations of a skill's decoded `SKILL.md`. Raises nothing.

    Args:
        database: Where the skill's parse tree is read from, and each path its links name is looked up.
        source: The text of the skill whose `SKILL.md` links are checked.
        linked_in: Every path inside the skill the skill's `metadata` links a file in at, or `None` when that
            `metadata` is unknown.
    """
    parsed = database.skill_parse(source)
    return validate_skill_links(
        links=parsed.links,
        anchors=parsed.anchors,
        targets=_link_targets(database, source.ref, parsed.links),
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
    # Joined to `ref.directory`, the directory an agent reaches the skill by, never to the resolved directory it
    # leads to: `find_path` then follows every symlink on the way, the skill's own entry and any inside it,
    # as an agent's read of the path would. Only what is left after the lexical normalisation is followed: a `..`
    # the link wrote already cancelled the component before it as spelled, so `guides/../SKILL.md` is
    # `SKILL.md`, whatever directory a `guides` symlink leads to. With no `..` left, the join stays root-relative.
    joined = ref.directory / str(path)
    if database.find_path(joined) is None:
        return LinkTargetState.MISSING
    return LinkTargetState.PRESENT


def _skill_resource_reports(
    database: Database, skill: SkillLocation, *, linked_in: frozenset[PurePosixPath] | None
) -> tuple[SkillResourceReport, ...]:
    """One report per resource of a skill, in the order the database lists them.

    A resource's links are held to the same rules as the `SKILL.md`'s, and a fragment-only link in it names one of
    the resource's own headings, read from its own parse tree.

    Args:
        database: Where the skill's resources are listed, each one's parse tree is read from, and each path a
            link names is looked up.
        skill: The skill whose resources are checked, located as the model hands it out.
        linked_in: Every path inside the skill the skill's `metadata` links a file in at, or `None` when that
            `metadata` is unknown.

    Raises:
        SkillResourcesListError: If a directory the walk over the skill's resources enters cannot be listed.
        SkillResourcesSymlinkResolveError: If a symlink the walk over the skill's resources meets cannot be
            resolved.
        SkillResourceReadError: If a resource is missing from the snapshot; a decode failure is a finding.
    """
    reports: list[SkillResourceReport] = []
    for location in database.skill_resources(skill).resources:
        resource = location.ref
        source = database.skill_resource_text(location)
        match source:
            case Undecodable():
                reports.append(SkillResourceReport(resource, violations=(_undecodable_skill('resource'),)))
            case SkillResourceText():
                parsed = database.skill_resource_parse(source)
                result = validate_skill_links(
                    links=parsed.links,
                    anchors=parsed.anchors,
                    targets=_link_targets(database, skill.ref, parsed.links),
                    linked_in=linked_in,
                )
                reports.append(SkillResourceReport(resource, violations=result.violations))
            case _:
                assert_never(source)
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
    if database.find_file(path) is not None:
        return ListedFileState.PRESENT
    if database.is_in_scope(path):
        return ListedFileState.MISSING
    return ListedFileState.OUTSIDE_SCOPE


def _budgeted(structure_specs: tuple[StructureSpec, ...]) -> tuple[StructureSpec, ...]:
    """The structure specifications that set a `tokens` budget, in the order given.

    Args:
        structure_specs: The structure specifications governing a document; those without a `tokens` budget are dropped.
    """
    budgeted: list[StructureSpec] = []
    for structure_spec in structure_specs:
        if structure_spec.tokens is not None:
            budgeted.append(structure_spec)
    return tuple(budgeted)


def _undecodable(rule_namespace: str) -> Violation:
    """The violation a governed document that is not UTF-8 carries instead of the check's own.

    Args:
        rule_namespace: Prefix of the `undecodable` rule: the document's corpus.
    """
    return Violation(
        line=LineNumber.from_int(1),
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
        line=LineNumber.from_int(1),
        rule='skill.undecodable',
        message=f'{file} is not valid UTF-8',
    )
