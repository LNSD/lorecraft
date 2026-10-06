"""How each input a rule reads is built from the database's queries, for one decoded subject.

An input a specification governs is built governance first: when no specification governs the subject for the
input, its builder returns `Ungoverned` without asking for the facts the input would hold, so an ungoverned subject
never pays for them. Only then does it ask the queries, each computed once per subject however many rules read the
input. An input the package governs, such as a skill's frontmatter block, has no governance to read, so its builder
asks the queries straight away and never returns `Ungoverned`.

A builder takes the decode query's witness, never a bare ref, so an input of a file that does not decode cannot be
asked for. The runner builds an input only when an enabled rule reads it.

Only the rules not yet moved onto a context read an input; later changes move them and remove this module.

An input that holds a shared analysis, such as the problems the frontmatter schemas find, reads it from the query
that memoizes it, so the analysis is computed once per subject however many inputs and rules read it.
"""

from dataclasses import dataclass
from typing import assert_never

from lorecraft.project.context import DocumentFrontmatterOwner, SkillFrontmatterOwner
from lorecraft.project.database import Database, DocumentText, SkillText
from lorecraft.project.schemas import StructureSpec, TitleChecks, field_line
from lorecraft.project.syntax import (
    Frontmatter,
    FrontmatterNode,
    Heading,
    InvalidYamlFrontmatter,
    LineNumber,
    MissingFrontmatter,
    NonMappingFrontmatter,
    find_title,
)
from lorecraft.rules.inputs import (
    FrontmatterBlock,
    FrontmatterBlockInput,
    FrontmatterFields,
    HeadingsInput,
    HeadingsSpec,
    NameField,
    OutlineDivergenceInput,
    RepeatedKey,
    SchemaProblemsInput,
    TitleMismatch,
)
from lorecraft.vfs import ResolvedPath


@dataclass(frozen=True, slots=True)
class Ungoverned:
    """No specification governs the subject for an input, so no rule over that input judges it.

    It is coverage, not a diagnostic: it describes the specifications, not the subject.
    """


def build_document_frontmatter_block_input(
    database: Database, source: DocumentText
) -> FrontmatterBlockInput | Ungoverned:
    """A document's frontmatter block, with the filename its `name` must equal.

    Governance is read first, and the frontmatter is read only when a schema governs the document.

    Args:
        database: The revision the document is read from; its model decides which specifications govern it.
        source: The document's text, as `Database.text` returns it.

    Returns:
        The input, naming the structure specification of the document's corpus as the one that governs the block;
        or `Ungoverned` when no frontmatter schema governs the document, or when it is in no corpus the database's
        model holds.

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
    schemas = governance.frontmatter_schemas()
    if not schemas:
        return Ungoverned()
    # A schema governs a document only through its corpus's structure specification, which a namespace's schema
    # merely narrows; so that specification exists here, and it states every rule over the block.
    # Without the corpus's structure specification a namespace one governs nothing, as `structure_specs` states.
    corpus_structure = governance.corpus_spec.structure
    if corpus_structure is None:
        # Unreachable: `frontmatter_schemas` is empty whenever the corpus has no structure specification.
        raise AssertionError('a frontmatter schema governs a document whose corpus has no structure specification')
    owner = DocumentFrontmatterOwner(filename=source.ref.filename, spec=corpus_structure.path)
    return FrontmatterBlockInput(frontmatter=_frontmatter_block(database.frontmatter(source)), owner=owner)


def build_skill_frontmatter_block_input(
    database: Database, source: SkillText, link_target: ResolvedPath | None
) -> FrontmatterBlockInput:
    """A skill's frontmatter block, with the directory name its `name` must equal. Raises nothing.

    The package governs every skill's frontmatter, after the Agent Skills specification, so there is no governance
    to read. `name` is held to the directory an agent lists, never to where a link leads: an agent opens
    `<entry>/SKILL.md` and lets the OS follow any symlink.

    Args:
        database: The revision the skill's `SKILL.md` frontmatter is read from.
        source: The skill's `SKILL.md` text, as `Database.skill_text` returns it.
        link_target: The resolved directory the skill's listed directory leads to when it is a link, or `None` when
            it is not; it only words a note.
    """
    owner = SkillFrontmatterOwner(directory_name=source.ref.directory.name, link_target=link_target)
    return FrontmatterBlockInput(frontmatter=_frontmatter_block(database.skill_frontmatter(source)), owner=owner)


def _frontmatter_block(node: FrontmatterNode) -> FrontmatterBlock:
    """The frontmatter block the rules read, with each line they report at located. Raises nothing.

    The three outcomes that hold no mapping pass through as they are; a mapping becomes its `name` and its repeated
    keys, each with its line.

    Args:
        node: The frontmatter node the database parsed.
    """
    match node:
        case MissingFrontmatter() | InvalidYamlFrontmatter() | NonMappingFrontmatter():
            return node
        case Frontmatter():
            return FrontmatterFields(name=_name_field(node), repeated_keys=_repeated_keys(node))
        case _:
            assert_never(node)


def _name_field(frontmatter: Frontmatter) -> NameField | None:
    """The `name` a mapping holds, at the line its key is written on, or `None` when it holds none. Raises nothing.

    Args:
        frontmatter: The decoded mapping.
    """
    if 'name' not in frontmatter.data:
        return None
    return NameField(value=frontmatter.data['name'], line=field_line(frontmatter, 'name'))


def _repeated_keys(frontmatter: Frontmatter) -> tuple[RepeatedKey, ...]:
    """Every top-level key a mapping writes again, one per occurrence after the first, in document order.

    Each points back at the key's first occurrence, so the third occurrence of a key names the first, not the
    second. Raises nothing.

    Args:
        frontmatter: The decoded mapping, whose top-level keys carry the line each is written on.
    """
    first_lines: dict[str, LineNumber] = {}
    repeated: list[RepeatedKey] = []
    for key in frontmatter.keys:
        first_line = first_lines.get(key.name)
        if first_line is None:
            first_lines[key.name] = key.line
        else:
            repeated.append(RepeatedKey(key=key.name, line=key.line, first_line=first_line))
    return tuple(repeated)


def build_document_schema_problems_input(database: Database, source: DocumentText) -> SchemaProblemsInput | Ungoverned:
    """What each frontmatter schema that governs a document rejects in its frontmatter.

    The schemas are read first, and the problems the schemas find are asked for only when one governs the document.

    Args:
        database: The revision the document is read from; its model decides which specifications govern it.
        source: The document's text, as `Database.text` returns it.

    Returns:
        The input, with one entry per frontmatter schema that governs the document, in the order the schemas apply,
        each naming the structure specification that states it; no entry when the block is missing, unparseable or
        not a mapping, which the block's own rules report. `Ungoverned` when no structure specification states a
        schema for the document, or when it is in no corpus the database's model holds.

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
    if not governance.frontmatter_schemas():
        return Ungoverned()
    # A block that is missing, not YAML or not a mapping is still governed, so the document is not ungoverned, but
    # no schema can be applied to it, and the query holds no entry.
    return SchemaProblemsInput(schemas=database.schema_problems(source))


def build_skill_schema_problems_input(database: Database, source: SkillText) -> SchemaProblemsInput:
    """What the Agent Skills specification rejects in a skill's frontmatter. Raises nothing.

    The package governs it, so every skill whose `SKILL.md` decodes has one.

    Args:
        database: The revision the skill is read from.
        source: The skill's `SKILL.md` text, as `Database.skill_text` returns it.

    Returns:
        The input, with one entry, for the Agent Skills specification; no entry when the block is missing,
        unparseable or not a mapping, which the block's own rules report.
    """
    return SchemaProblemsInput(schemas=database.skill_schema_problems(source))


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
