"""The shape of a structure specification file, as it is written: the one declaration of its fields.

These models describe the JSON a ``<stem>.structure.json`` file holds, field for field, where ``StructureAspect``
holds the rules decoded from it. They are the edge: ``StructureAspect.parse`` deserializes a file's text straight
into ``StructureFile`` and nothing else reads the JSON, so a file that gets past them has this shape exactly. And
``just gen`` renders them into ``docs/schemas/structure.spec.json``, the JSON Schema an editor validates the file
against while it is written, so the editor and the check hold a file to the same declaration.

Every model is strict, frozen and closed. Strict, so a JSON value is never coerced into another type: ``true`` is
not a count and ``"yes"`` is not a boolean. Frozen, so a parsed file cannot change after it was validated. Closed
(``extra='forbid'``), so a misspelt field is an error rather than a rule silently ignored.

What the schema shows an editor is declared here too: each field's docstring is its description, ``Field`` adds
its examples and bounds, and each model's config names it and gives a whole example. Only the shape is stated
here; what a shape cannot state, such as an outline naming a section twice, is refused by ``StructureAspect``.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue


def _code_outline_example() -> list[JsonValue]:
    """The outline of a rule document in docs/code/, as an example: its own sections, then the Checklist and the
    two references, with a word cap on each of its own sections and on the Checklist. A fresh list for each example
    that shows it."""
    return [
        {'any': True, 'words': 350},
        {'section': 'Checklist', 'words': 250},
        {'section': 'References', 'optional': True},
        {'section': 'External References', 'optional': True},
    ]


class _StructureFileModel(BaseModel):
    """The settings every model of the file shares; each model's own config is merged over them."""

    model_config = ConfigDict(extra='forbid', frozen=True, strict=True, use_attribute_docstrings=True)


class StructureFileTitle(_StructureFileModel):
    """How many H1 titles a document carries, and whether one opens it."""

    model_config = ConfigDict(title='Title rule', json_schema_extra={'examples': [{'count': 1, 'first': True}]})

    count: int = Field(ge=1, examples=[1])
    """The number of H1 titles a document carries."""
    first: bool
    """True when an H1 title must come before any other heading."""


class StructureFileSection(_StructureFileModel):
    """An outline entry naming one section, fixing its position against every other name in the outline."""

    model_config = ConfigDict(
        title='Named section',
        json_schema_extra={
            'examples': [
                {'section': 'Checklist', 'words': 250},
                {'section': 'References', 'optional': True},
            ]
        },
    )

    section: str = Field(examples=['Checklist', 'References'])
    """The section's heading text, without its `#` markers or inline markup."""
    optional: bool = False
    """True when a document may leave the section out."""
    words: int | None = Field(default=None, ge=1, examples=[250])
    """The most words of prose the section may hold, its H3 subsections included; no cap when absent."""


class StructureFileAny(_StructureFileModel):
    """An outline entry matching a run, of any length, of sections the outline does not name.

    The run stops at any section the outline names, so each named section still matches its own entry.
    """

    model_config = ConfigDict(
        title='Unnamed sections', json_schema_extra={'examples': [{'any': True}, {'any': True, 'words': 350}]}
    )

    any: Literal[True]
    """Always true: the field that marks the entry as a run."""
    words: int | None = Field(default=None, ge=1, examples=[350])
    """The most words of prose each section in the run may hold, its H3 subsections included: a cap on every
    section alone, not on the run's total. No cap when absent."""


class StructureFile(_StructureFileModel):
    """A structure specification: the section outline a document governed by this file must follow."""

    model_config = ConfigDict(
        title='Structure specification',
        json_schema_extra={
            'examples': [
                {
                    'description': 'Section structure and word caps for a rule document in docs/code/.',
                    'title': {'count': 1, 'first': True},
                    'empty_sections': 'forbidden',
                    'outline': _code_outline_example(),
                }
            ],
        },
    )

    # `$schema` is no Python name, so the field is declared under another and read from the file by its alias.
    schema_reference: str | None = Field(default=None, alias='$schema')
    """The JSON Schema this file is written against, for editors; ignored by the check."""
    description: str = Field(
        default='', examples=['Section structure and word caps for a rule document in docs/code/.']
    )
    """What this file governs and why, for whoever opens it; not read by the check."""
    title: StructureFileTitle | None = None
    """How many H1 titles a document carries, and whether one opens it; no title rule when absent."""
    empty_sections: Literal['forbidden'] | None = None
    """`forbidden` reports every section left without content: one that ends the document, or is followed straight
    away by a heading of its own level or higher. Empty sections are allowed when absent."""
    outline: tuple[StructureFileSection | StructureFileAny, ...] = Field(default=(), examples=[_code_outline_example()])
    """The order of the document's sections, matched left to right. A named section is required unless optional,
    and may be named once; an `{"any": true}` entry matches a run of sections the outline does not name, and two
    may not sit side by side. An entry's `words` caps each section it matches; an entry without one caps none. A
    word is a whitespace-delimited token of prose: fenced code and table rows are not counted."""
    forbidden: tuple[str, ...] = Field(default=(), examples=[['Changelog']])
    """Sections that must not appear at all; none may also be named in the outline."""
