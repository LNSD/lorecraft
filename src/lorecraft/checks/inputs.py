"""How each input a rule reads is built from the database's queries, for one decoded subject.

An input a specification governs is built governance first: when no specification governs the subject for the
input, its builder returns `Ungoverned` without asking for the facts the input would hold, so an ungoverned subject
never pays for them. Only then does it ask the queries, each computed once per subject however many rules read the
input. An input the package governs, such as a skill's line count, has no governance to read, so its builder asks
the queries straight away and never returns `Ungoverned`.

A builder takes the decode query's witness, never a bare ref, so an input of a file that does not decode cannot be
asked for. The runner builds an input only when an enabled rule reads it.

An input that is a shared analysis, such as the problems the frontmatter schemas find, is a judgment rather than a
query: its builder runs the analysis each time it is called, once per subject per run, and never memoizes it.
"""

from dataclasses import dataclass
from typing import assert_never

from lorecraft.core.num import NonZeroUnsignedInt, UnsignedInt
from lorecraft.project.schemas import (
    SKILL_FRONTMATTER_SCHEMA,
    AnySections,
    BlockProblem,
    FrontmatterProblem,
    InvalidValueProblem,
    MissingFieldProblem,
    OutlineEntry,
    SectionEntry,
    UnknownFieldProblem,
    WrongTypeProblem,
)
from lorecraft.project.syntax import (
    Frontmatter,
    FrontmatterNode,
    Heading,
    InvalidYamlFrontmatter,
    LineNumber,
    MissingFrontmatter,
    NonMappingFrontmatter,
)
from lorecraft.rules.frontmatter.__ruleset__ import FIRST_LINE, field_line
from lorecraft.rules.inputs import (
    SECTION_LEVEL,
    AgentSkillsSchema,
    Budget,
    DocumentFrontmatterOwner,
    FrontmatterBlock,
    FrontmatterBlockInput,
    FrontmatterFields,
    HeadingsInput,
    HeadingsSpec,
    LineCountInput,
    LocatedProblem,
    NameField,
    RepeatedKey,
    SchemaProblems,
    SchemaProblemsInput,
    SectionCap,
    SkillFrontmatterOwner,
    StructureSpecSchema,
    TokenCountInput,
)
from lorecraft.vfs import ResolvedPath

from .database import Database
from .text import DocumentText, SkillText


@dataclass(frozen=True, slots=True)
class Ungoverned:
    """No specification governs the subject for an input, so no rule over that input judges it.

    It is coverage, not a diagnostic: it describes the specifications, not the subject.
    """


def build_token_count_input(database: Database, source: DocumentText) -> TokenCountInput | Ungoverned:
    """A document's whole-file token count, with every token budget that governs it.

    The budgets are read first, and the tokens are counted only when one is set.

    Args:
        database: The revision the document is read from; its model decides which specifications govern it.
        source: The document's text, as `Database.text` returns it.

    Returns:
        The input, with one budget per structure specification that governs the document and sets one, in the
        order the specifications apply; or `Ungoverned` when none sets a budget, or when the document is in no
        corpus the database's model holds, so no specification governs it.

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
    budgets: list[Budget] = []
    for structure_spec in governance.structure_specs():
        if structure_spec.tokens is not None:
            budgets.append(Budget(tokens=structure_spec.tokens, spec=structure_spec.path))
    if not budgets:
        return Ungoverned()
    # A count is never negative, so building the `UnsignedInt` cannot raise `NegativeIntError` here.
    return TokenCountInput(token_count=UnsignedInt(database.tokens(source)), budgets=tuple(budgets))


def build_line_count_input(database: Database, source: SkillText) -> LineCountInput:
    """A skill's whole-`SKILL.md` line count. Raises nothing.

    Args:
        database: The revision the skill is read from.
        source: The skill's `SKILL.md` text, as `Database.skill_text` returns it.
    """
    # A count is never negative, so building the `UnsignedInt` cannot raise `NegativeIntError` here.
    return LineCountInput(line_count=UnsignedInt(database.skill_lines(source)))


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

    The schemas are read first, and the frontmatter is read and held to them only when one governs the document.

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

    frontmatter = database.frontmatter(source)
    match frontmatter:
        case MissingFrontmatter() | InvalidYamlFrontmatter() | NonMappingFrontmatter():
            # The block is governed, so the document is not ungoverned, but no schema can be applied to it.
            return SchemaProblemsInput(schemas=())
        case Frontmatter():
            pass  # the mapping is held to each schema below
        case _:
            assert_never(frontmatter)

    found: list[SchemaProblems] = []
    for schema in schemas:
        found.append(
            SchemaProblems(
                source=StructureSpecSchema(spec=schema.path),
                problems=_located_problems(frontmatter, schema.validate(frontmatter.data)),
            )
        )
    return SchemaProblemsInput(schemas=tuple(found))


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
    frontmatter = database.skill_frontmatter(source)
    match frontmatter:
        case MissingFrontmatter() | InvalidYamlFrontmatter() | NonMappingFrontmatter():
            return SchemaProblemsInput(schemas=())
        case Frontmatter():
            pass  # the mapping is held to the specification below
        case _:
            assert_never(frontmatter)

    problems = _located_problems(frontmatter, SKILL_FRONTMATTER_SCHEMA.validate(frontmatter.data))
    return SchemaProblemsInput(schemas=(SchemaProblems(source=AgentSkillsSchema(), problems=problems),))


def _located_problems(frontmatter: Frontmatter, problems: tuple[FrontmatterProblem, ...]) -> tuple[LocatedProblem, ...]:
    """Each problem a schema found, with the line it is reported on, in the order given.

    Args:
        frontmatter: The frontmatter the problems were found in.
        problems: What the schema rejected in it.
    """
    located: list[LocatedProblem] = []
    for problem in problems:
        located.append(LocatedProblem(problem=problem, line=_problem_line(frontmatter, problem)))
    return tuple(located)


def _problem_line(frontmatter: Frontmatter, problem: FrontmatterProblem) -> LineNumber:
    """The line a schema problem is reported on: its field's, or line 1 when it has no written field.

    Args:
        frontmatter: The frontmatter the problem was found in; searched for the line its field is written on.
        problem: What the schema rejected; a problem on a written field is placed on that field's line.
    """
    match problem:
        # A missing field is not written, and a block constraint concerns none.
        case MissingFieldProblem() | BlockProblem():
            return FIRST_LINE
        case UnknownFieldProblem() | WrongTypeProblem() | InvalidValueProblem():
            return field_line(frontmatter, problem.field)
        case _:
            assert_never(problem)


def build_headings_input(database: Database, source: DocumentText) -> HeadingsInput | Ungoverned:
    """A document's headings, with what each structure specification that governs it states over them.

    The structure specifications are read first, and the document is parsed only when one governs it. Each section's
    word cap is worked out here, from the outline, so a rule over the caps only compares numbers.

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
    structure_specs = governance.structure_specs()
    if not structure_specs:
        return Ungoverned()

    headings = database.parse(source).headings
    sections = tuple(heading for heading in headings if heading.level == SECTION_LEVEL)
    specs: list[HeadingsSpec] = []
    for structure_spec in structure_specs:
        specs.append(
            HeadingsSpec(
                spec=structure_spec.path,
                title=structure_spec.title,
                forbid_empty_sections=structure_spec.forbid_empty_sections,
                forbidden=structure_spec.forbidden,
                section_caps=_section_caps(structure_spec.outline, sections),
            )
        )
    return HeadingsInput(headings=headings, specs=tuple(specs))


def _section_caps(outline: tuple[OutlineEntry, ...], sections: tuple[Heading, ...]) -> tuple[SectionCap, ...]:
    """The word cap each section of a document is held to under one outline, in document order. Raises nothing.

    A section the outline names takes the cap of the entry naming it, which may be none. Any other section takes
    the cap of the `any` run it falls in: the first `any` entry after the entry naming the last named section
    before it. In a document that follows the outline, that is the run which matches it. A section no cap applies
    to is left out.

    Args:
        outline: The entries of the structure specification's outline, which carry the caps; may be empty.
        sections: The document's H2 headings, in document order, each with its prose word count.
    """
    caps: list[SectionCap] = []
    last_named_at = -1  # the outline index of the last named section passed; -1 before any
    for section in sections:
        entry_at = _find_entry_index(outline, section.text)
        if entry_at is None:
            cap = _find_run_cap(outline, last_named_at)
        else:
            last_named_at = entry_at
            cap = outline[entry_at].words
        if cap is not None:
            caps.append(SectionCap(section=section, words=cap))
    return tuple(caps)


def _find_entry_index(outline: tuple[OutlineEntry, ...], name: str) -> int | None:
    """Where in the outline the section entry naming `name` sits, or `None` when no entry names it. Raises nothing.

    Args:
        outline: The entries to search, in outline order.
        name: Heading text of the section to find.
    """
    for index, entry in enumerate(outline):
        match entry:
            case SectionEntry():
                if entry.name.value == name:
                    return index
            case AnySections():
                pass  # a run names no section
            case _:
                assert_never(entry)
    return None


def _find_run_cap(outline: tuple[OutlineEntry, ...], after: int) -> NonZeroUnsignedInt | None:
    """The cap of the first `any` entry past outline index `after`, or `None` when there is none. Raises nothing.

    Args:
        outline: The entries to search, in outline order.
        after: Outline index of the last named section passed, exclusive; -1 searches from the start.
    """
    for entry in outline[after + 1 :]:
        match entry:
            case AnySections():
                return entry.words
            case SectionEntry():
                pass  # a section entry caps only its own section
            case _:
                assert_never(entry)
    return None
