"""The shape of a structure specification file, as it is written: the one declaration of its fields.

These models describe the JSON a `<name>.structure.json` file holds, field for field, where `StructureSpec`
holds the rules decoded from it. They are the edge: `StructureSpec.parse` deserializes a file's text straight
into `StructureFile` and nothing else reads the JSON, so a file that gets past them has this shape exactly. And
`just gen` renders them into `docs/schemas/structure.spec.json`, the JSON Schema an editor validates the file
against while it is written, so the editor and the check hold a file to the same declaration.

Every model is strict, frozen and closed. Strict, so a JSON value is never coerced into another type: `true` is
not a count and `"yes"` is not a boolean. Frozen, so a parsed file cannot change after it was validated. Closed
(`extra='forbid'`), so a misspelt field is an error rather than a rule silently ignored.

What the schema shows an editor is declared here too: each field's docstring is its description, `Field` adds
its examples and bounds, and each model's config names it and gives a whole example. Only the shape is stated
here; what a shape cannot state, such as an outline naming a section twice, is refused by `StructureSpec`.

A word cap or the token budget is a `NonZeroUnsignedInt`, which states its own bound: it is
built while the file is decoded, and a number it refuses is a validation error carrying its own message. A section
name, in an outline entry or in `forbidden`, is a `SectionName` the same way, which states its own rule.
"""

from typing import Annotated, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, WithJsonSchema, field_validator

from lorecraft.core.num import NonZeroUnsignedInt

from .section_name import SectionName

JSON_SCHEMA_DIALECT: Final[str] = 'https://json-schema.org/draft/2020-12/schema'
"""Draft 2020-12, the one dialect a frontmatter schema is written in: the only one its ``$schema`` may name."""


# Runs once per process, before mutmut swaps a mutant in, so no test can ever see a mutant of it.
def _frontmatter_json_schema() -> dict[str, JsonValue]:  # pragma: no mutate block
    """What an editor holds the `frontmatter` key to.

    That is any schema the Draft 2020-12 meta-schema accepts that also states `"type": "object"` at its root.
    `StructureSpec` refuses the same schemas when it loads the file, and
    a few more no schema here can state, such as one carrying `$id`. A `null` is refused here and at load alike.
    A fresh dict each call, so no caller can change the source of the generated schema.
    """
    return {
        'allOf': [
            {'$ref': JSON_SCHEMA_DIALECT},
            {'type': 'object', 'required': ['type'], 'properties': {'type': {'const': 'object'}}},
        ]
    }


# Runs once per process, before mutmut swaps a mutant in, so no test can ever see a mutant of it.
def _code_frontmatter_example() -> dict[str, JsonValue]:  # pragma: no mutate block
    """The frontmatter schema of a rule document in docs/code/, as an example.

    It is a closed object whose two fields are required strings. A fresh dict for each example that shows it.
    """
    return {
        'type': 'object',
        'required': ['name', 'description'],
        'additionalProperties': False,
        'properties': {'name': {'type': 'string'}, 'description': {'type': 'string'}},
    }


# Runs once per process, before mutmut swaps a mutant in, so no test can ever see a mutant of it.
def _code_outline_example() -> list[JsonValue]:  # pragma: no mutate block
    """The outline of a rule document in docs/code/, as an example.

    It is its own sections, then the Checklist and the two references, with a word cap on each of its own sections
    and on the Checklist. A fresh list for each example that shows it.
    """
    return [
        {'any': True, 'words': 350},
        {'section': 'Checklist', 'words': 250},
        {'section': 'References', 'optional': True},
        {'section': 'External References', 'optional': True},
    ]


# Runs once per process, before mutmut swaps a mutant in, so no test can ever see a mutant of it.
def _code_checklist_example() -> str:  # pragma: no mutate block
    """The body of the Checklist of a rule document in docs/code/, as an example of a section's body."""
    return (
        'Before committing code, verify:\n'
        '\n'
        '- [ ] Every new record is a `@dataclass` unless it decodes data arriving from outside the process\n'
        '- [ ] Every list, dict, or set default uses `field(default_factory=...)`\n'
        '- [ ] Every record used as a dict key, set member, or compared identity is `frozen=True`\n'
        "- [ ] Every record's class docstring lists all public fields under `Attributes:`"
    )


class _StructureFileModel(BaseModel):
    """The settings every model of the file shares; each model's own config is merged over them."""

    model_config = ConfigDict(extra='forbid', frozen=True, strict=True, use_attribute_docstrings=True)


class StructureFileSection(_StructureFileModel):
    """An outline entry naming one section, fixing its position against every other name in the outline.

    Its `description` and `examples` tell the author of a document that lacks the section what to write there.
    """

    model_config = ConfigDict(
        title='Named section',
        json_schema_extra={
            'examples': [
                {'section': 'Checklist', 'words': 250},
                {'section': 'References', 'optional': True},
                {
                    'section': 'Checklist',
                    'words': 250,
                    'description': 'The items a reviewer verifies before committing a change the document governs.',
                    'examples': [_code_checklist_example()],
                },
            ]
        },
    )

    section: SectionName = Field(examples=['Checklist', 'References'])
    """The section's heading text, without its `#` markers or inline markup."""
    optional: bool = False
    """True when a document may leave the section out."""
    words: NonZeroUnsignedInt | None = Field(default=None, examples=[250])
    """The most words of prose the section may hold, its H3 subsections included; no cap when absent."""
    description: str | None = Field(
        default=None,
        min_length=1,
        examples=['The items a reviewer verifies before committing a change the document governs.'],
    )
    """What the section holds; reported as help when a document lacks the section. No help when absent."""
    examples: tuple[Annotated[str, Field(min_length=1)], ...] | None = Field(
        default=None, min_length=1, examples=[[_code_checklist_example()]]
    )
    """A non-empty list of Markdown samples of the section's body, each without its heading. Each is illustrative,
    written as if it belonged to an actual document of the corpus, not a placeholder. The check reports only the
    first, as a note, when a document lacks the section; the rest serve a reader of the specification. No sample
    when absent."""


class StructureFileAny(_StructureFileModel):
    """An outline entry matching a run, of any length, of sections the outline does not name.

    The run stops at any section the outline names, so each named section still matches its own entry.
    """

    model_config = ConfigDict(
        title='Unnamed sections', json_schema_extra={'examples': [{'any': True}, {'any': True, 'words': 350}]}
    )

    any: Literal[True]
    """Always true: the field that marks the entry as a run."""
    words: NonZeroUnsignedInt | None = Field(default=None, examples=[350])
    """The most words of prose each section in the run may hold, its H3 subsections included: a cap on every
    section alone, not on the run's total. No cap when absent."""


class StructureFile(_StructureFileModel):
    """A structure specification: the frontmatter schema, outline and token budget a governed document follows."""

    model_config = ConfigDict(
        title='Structure specification',
        json_schema_extra={
            'examples': [
                {
                    'description': 'Section structure, word caps and token budget for a rule document in docs/code/.',
                    'tokens': 5000,
                    'frontmatter': _code_frontmatter_example(),
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
        default='', examples=['Section structure, word caps and token budget for a rule document in docs/code/.']
    )
    """What this file governs and why, for whoever opens it; not read by the check."""
    tokens: NonZeroUnsignedInt | None = Field(default=None, examples=[5000])
    """The token budget: the most tokens the whole file may cost an agent that loads it, frontmatter, code and
    tables included; no budget when absent. Counted with OpenAI's `o200k_base` encoding, the same whichever agent
    reads the document."""
    # The field's JSON Schema is written out rather than rendered: pydantic would render a dict of JSON values as any
    # object, where an editor should check that the value is a JSON Schema describing an object.
    frontmatter: Annotated[dict[str, JsonValue] | None, WithJsonSchema(_frontmatter_json_schema())] = Field(
        default=None, examples=[_code_frontmatter_example()]
    )
    """The Draft 2020-12 JSON Schema a document's frontmatter must satisfy; no frontmatter rule when absent. Its root
    must state `"type": "object"`, and it may carry neither `$id` nor a `$schema` naming another dialect."""
    empty_sections: Literal['forbidden'] | None = None
    """`forbidden` reports every section left without content: one that ends the document, or is followed straight
    away by a heading of its own level or higher. Empty sections are allowed when absent."""
    outline: tuple[StructureFileSection | StructureFileAny, ...] = Field(default=(), examples=[_code_outline_example()])
    """The order of the document's sections, matched left to right. A named section is required unless optional,
    and may be named once; an `{"any": true}` entry matches a run of sections the outline does not name, and two
    may not sit side by side. An entry's `words` caps each section it matches; an entry without one caps none. A
    word is a whitespace-delimited token of prose: fenced code and table rows are not counted. A named section's
    `description` and the first of its `examples` tell the author of a document that lacks it what to write there."""
    # `uniqueItems` is for the editor only: pydantic does not apply it, and `StructureSpec` refuses a repeated name.
    forbidden: tuple[SectionName, ...] = Field(
        default=(), examples=[['Changelog']], json_schema_extra={'uniqueItems': True}
    )
    """Sections that must not appear at all; none may also be named in the outline."""

    @field_validator('frontmatter', mode='before')
    @classmethod
    def _refuse_null_frontmatter(cls, value: object) -> object:
        """Refuse `"frontmatter": null`, as the editor's schema does, so the two agree on it.

        No frontmatter rule is written by leaving the key out. A validator runs only on a value the file states,
        never on the default.

        Args:
            value: The raw value of the `frontmatter` key before pydantic coerces it; returned unchanged unless `None`.

        Raises:
            ValueError: If the file states the key as `null`; pydantic reports it as a validation error.
        """
        if value is None:
            raise ValueError('may not be null; leave the key out for no frontmatter rule')
        return value
