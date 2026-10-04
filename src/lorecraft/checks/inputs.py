"""How each input a rule reads is built from the database's queries, for one decoded subject.

An input builder reads governance first: when no specification governs the subject for the input, it returns
`Ungoverned` without asking for the facts the input would hold, so an ungoverned subject never pays for them. Only
then does it ask the queries, each computed once per subject however many rules read the input.

A builder takes the decode query's witness, never a bare ref, so an input of a file that does not decode cannot be
asked for. The runner builds an input only when an enabled rule reads it.
"""

from dataclasses import dataclass

from lorecraft.core.num import UnsignedInt
from lorecraft.rules.inputs import Budget, TokenCountInput

from .database import Database
from .text import DocumentText


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
