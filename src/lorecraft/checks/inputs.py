"""How each input a rule reads is built from the database's queries, for one decoded subject.

An input a specification governs is built governance first: when no specification governs the subject for the
input, its builder returns `Ungoverned` without asking for the facts the input would hold, so an ungoverned subject
never pays for them. Only then does it ask the queries, each computed once per subject however many rules read the
input. An input the package governs, such as a skill's line count, has no governance to read, so its builder asks
the queries straight away and never returns `Ungoverned`.

A builder takes the decode query's witness, never a bare ref, so an input of a file that does not decode cannot be
asked for. The runner builds an input only when an enabled rule reads it.

An input that holds a shared analysis, such as the problems the frontmatter schemas find, reads it from the query
that memoizes it, so the analysis is computed once per subject however many inputs and rules read it.
"""

from dataclasses import dataclass
from typing import assert_never

from lorecraft.core.num import NonZeroUnsignedInt, UnsignedInt
from lorecraft.project.schemas import (
    AnySections,
    OutlineEntry,
    SectionEntry,
    StructureSpec,
    TitleChecks,
    field_line,
)
from lorecraft.project.syntax import (
    SECTION_LEVEL,
    Frontmatter,
    FrontmatterNode,
    Heading,
    InvalidYamlFrontmatter,
    LineNumber,
    MissingFrontmatter,
    NonMappingFrontmatter,
    count_words,
)
from lorecraft.rules.inputs import (
    Budget,
    DocumentFrontmatterOwner,
    FrontmatterBlock,
    FrontmatterBlockInput,
    FrontmatterFields,
    HeadingsInput,
    HeadingsSpec,
    LineCountInput,
    NameField,
    OutlineDivergenceInput,
    RepeatedKey,
    SchemaProblemsInput,
    SectionCap,
    SkillFrontmatterOwner,
    TitleCap,
    TitleCharCap,
    TitleMismatch,
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

    The structure specifications are read first, and the document is parsed only when one governs it. Each section's
    word cap is worked out here, from the outline, and so are the title's, with the words and the characters of the
    title's text, so a rule over the caps only compares numbers. The title's text is matched against its pattern here
    too, so a rule over the pattern only reads the outcome.

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
    title = _find_title(headings)
    sections = tuple(heading for heading in headings if heading.level == SECTION_LEVEL)
    namespaces: list[HeadingsSpec] = []
    for namespace_spec in governance.namespace_specs:
        if namespace_spec.structure is not None:
            namespaces.append(_headings_spec(namespace_spec.structure, title, sections))
    return HeadingsInput(
        headings=headings, corpus=_headings_spec(corpus_structure, title, sections), namespaces=tuple(namespaces)
    )


def _find_title(headings: tuple[Heading, ...]) -> Heading | None:
    """A document's title: its first H1 heading, or `None` when it has none. Raises nothing.

    A later H1 is a second title, which is a finding of its own, so no check on the title is held against it.

    Args:
        headings: The document's top-level headings, in document order.
    """
    for heading in headings:
        if heading.level == 1:
            return heading
    return None


def _headings_spec(structure_spec: StructureSpec, title: Heading | None, sections: tuple[Heading, ...]) -> HeadingsSpec:
    """What one structure specification states over a document's headings, its caps resolved. Raises nothing.

    Args:
        structure_spec: The structure specification that governs the document.
        title: The document's title, its first H1 heading, or `None` when it has none.
        sections: The document's H2 headings, in document order, each with its prose word count.
    """
    return HeadingsSpec(
        spec=structure_spec.path,
        title_cap=_title_cap(structure_spec.title, title),
        title_char_cap=_title_char_cap(structure_spec.title, title),
        title_mismatch=_title_mismatch(structure_spec.title, title),
        forbid_empty_sections=structure_spec.forbid_empty_sections,
        forbidden=structure_spec.forbidden,
        section_caps=_section_caps(structure_spec.outline, sections),
    )


def _title_cap(title_checks: TitleChecks | None, title: Heading | None) -> TitleCap | None:
    """The cap on a document's title words under one specification, measured against its title. Raises nothing.

    Args:
        title_checks: The checks the specification's `title` states, or `None` when it states none.
        title: The document's title, its first H1 heading, or `None` when it has none.

    Returns:
        The cap with the title it applies to and the words of the title's text; or `None` when the specification
        sets no cap, or when the document has no title.
    """
    if title_checks is None or title_checks.words is None or title is None:
        return None
    return TitleCap(title=title, title_words=count_words(title.text), words=title_checks.words)


def _title_char_cap(title_checks: TitleChecks | None, title: Heading | None) -> TitleCharCap | None:
    """The cap on a document's title characters under one specification, measured against its title. Raises nothing.

    The characters are those of the title's text as the parse holds it, inline markup already stripped, counted as
    Unicode code points: the `len` of the text, neither its bytes nor the letters a reader sees, so an emoji built
    of several code points counts each of them.

    Args:
        title_checks: The checks the specification's `title` states, or `None` when it states none.
        title: The document's title, its first H1 heading, or `None` when it has none.

    Returns:
        The cap with the title it applies to and the characters of the title's text; or `None` when the
        specification sets no cap, or when the document has no title.
    """
    if title_checks is None or title_checks.chars is None or title is None:
        return None
    return TitleCharCap(title=title, title_chars=len(title.text), chars=title_checks.chars)


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
