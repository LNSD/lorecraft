"""How each input a rule reads is built from the database's queries, for one decoded document.

An input is built governance first: when no specification governs the document for the input, its builder returns
`Ungoverned` without asking for the facts the input would hold, so an ungoverned document never pays for them. Only
then does it ask the queries, each computed once per document however many rules read the input.

A builder takes the decode query's witness, never a bare ref, so an input of a file that does not decode cannot be
asked for. The runner builds an input only when an enabled rule reads it.

Only the outline rules, not yet moved onto a context, read an input; a later change moves them and removes this module.

An input that holds a shared analysis, such as where the sections stop matching the outlines, reads it from the query
that memoizes it, so the analysis is computed once per document however many inputs and rules read it.
"""

from dataclasses import dataclass

from lorecraft.project.database import Database, DocumentText
from lorecraft.project.schemas import StructureSpec, TitleChecks
from lorecraft.project.syntax import Heading, find_title
from lorecraft.rules.inputs import HeadingsInput, HeadingsSpec, OutlineDivergenceInput, TitleMismatch


@dataclass(frozen=True, slots=True)
class Ungoverned:
    """No specification governs the subject for an input, so no rule over that input judges it.

    It is coverage, not a diagnostic: it describes the specifications, not the subject.
    """


def build_headings_input(database: Database, source: DocumentText) -> HeadingsInput | Ungoverned:
    """A document's headings, with what each structure specification that governs it states over them.

    The structure specifications are read first, and the document is parsed only when one governs it. The title's
    text is matched against its pattern here, so a rule over the pattern only reads the outcome.

    Args:
        database: The revision the document is read from; its model decides which specifications govern it.
        source: The document's text, as `Database.text` returns it.

    Returns:
        The input, with one entry per structure specification that governs the document, in the order the
        specifications apply; or `Ungoverned` when no structure specification governs the document, or when it is
        in no corpus the database's model holds.

    Raises:
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
        AdjacentAnyRunsError: If the model is not loaded yet and an outline places two `any` runs side by side.
        InvalidTitlePatternError: If the model is not loaded yet and a title's pattern does not compile.
        InvalidFrontmatterSchemaError: If the model is not loaded yet and a frontmatter schema is rejected by the
            meta-schema.
        FrontmatterSchemaIdError: If the model is not loaded yet and a schema in a frontmatter schema carries `$id`.
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
    governance = database.model().find_governance(source.ref)
    if governance is None:
        return Ungoverned()
    # Without the corpus's structure specification a namespace one governs nothing, as `structure_specs` states.
    corpus_structure = governance.corpus_spec.structure
    if corpus_structure is None:
        return Ungoverned()

    headings = database.parse(source).headings
    title = find_title(headings)
    namespaces: list[HeadingsSpec] = []
    for namespace_spec in governance.namespace_specs:
        if namespace_spec.structure is not None:
            namespaces.append(_headings_spec(namespace_spec.structure, title))
    return HeadingsInput(
        headings=headings, corpus=_headings_spec(corpus_structure, title), namespaces=tuple(namespaces)
    )


def _headings_spec(structure_spec: StructureSpec, title: Heading | None) -> HeadingsSpec:
    """What one structure specification states over a document's headings, its title pattern matched. Raises nothing.

    Args:
        structure_spec: The structure specification that governs the document.
        title: The document's title, its first H1 heading, or `None` when it has none.
    """
    return HeadingsSpec(
        spec=structure_spec.path,
        title_mismatch=_title_mismatch(structure_spec.title, title),
        forbid_empty_sections=structure_spec.forbid_empty_sections,
        forbidden=structure_spec.forbidden,
    )


def _title_mismatch(title_checks: TitleChecks | None, title: Heading | None) -> TitleMismatch | None:
    """The title and the pattern it fails under one specification, or `None`. Raises nothing.

    Args:
        title_checks: The checks the specification's `title` states, or `None` when it states none.
        title: The document's title, its first H1 heading, or `None` when it has none.

    Returns:
        The title with the pattern its text does not match; or `None` when its text matches, when the
        specification sets no pattern, or when the document has no title.
    """
    if title_checks is None or title_checks.pattern is None or title is None:
        return None
    if title_checks.pattern.is_found_in(title.text):
        return None
    return TitleMismatch(title=title, pattern=str(title_checks.pattern))


def build_outline_divergence_input(database: Database, source: DocumentText) -> OutlineDivergenceInput | Ungoverned:
    """Where a document's sections first stop matching each outline that governs them.

    The structure specifications are read first, and where the document's sections diverge from the outlines is
    asked for only when one of them states an outline.

    Args:
        database: The revision the document is read from; its model decides which specifications govern it.
        source: The document's text, as `Database.text` returns it.

    Returns:
        The input, with one entry per structure specification that governs the document and states an outline, in
        the order the specifications apply; or `Ungoverned` when none states one, or when the document is in no
        corpus the database's model holds.

    Raises:
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
        AdjacentAnyRunsError: If the model is not loaded yet and an outline places two `any` runs side by side.
        InvalidTitlePatternError: If the model is not loaded yet and a title's pattern does not compile.
        InvalidFrontmatterSchemaError: If the model is not loaded yet and a frontmatter schema is rejected by the
            meta-schema.
        FrontmatterSchemaIdError: If the model is not loaded yet and a schema in a frontmatter schema carries `$id`.
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
    governance = database.model().find_governance(source.ref)
    if governance is None:
        return Ungoverned()
    if not any(structure_spec.outline for structure_spec in governance.structure_specs()):
        return Ungoverned()
    return OutlineDivergenceInput(specs=database.outline_divergences(source))
