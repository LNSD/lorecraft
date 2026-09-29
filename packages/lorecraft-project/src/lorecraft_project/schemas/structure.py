"""The structure aspect: a structure specification file's decoded JSON, and the rules it is decoded into.

The repository reads and decodes a ``<stem>.structure.json`` file into a ``StructureSchema``, which proves
nothing about it. ``StructureAspect.parse`` is the check: it reads the JSON's shape into typed rules, and
building the aspect refuses a set of rules that checks nothing or contradicts itself. So every
``StructureAspect`` that exists states usable rules, however it was built.

A document's outline is a sequence whose length varies, and JSON Schema cannot state an order over one, so a
structure specification is not JSON Schema. It is this small dialect:

    {
      "spec": "code.md §5",
      "description": "what this file governs, for whoever opens it",
      "title": {"count": 1, "first": true},
      "empty_sections": "forbidden",
      "outline": [
        {"section": "Table of Contents", "optional": true},
        {"any": true},
        {"section": "Checklist"}
      ],
      "forbidden": ["Changelog"]
    }

- ``spec`` names the prose this file is the machine-checkable half of; every finding quotes it.
- ``description`` is read by people only, and is not kept.
- ``title`` states how many H1 titles a document carries, and whether one opens it ahead of every section.
- ``empty_sections``, whose one value is ``"forbidden"``, reports a section left without content.
- ``outline`` is the order of the document's sections. A ``section`` entry names one and is required unless
  ``optional``; an ``any`` entry matches a run of sections the outline does not name.
- ``forbidden`` names sections that must not appear at all.

Nothing here logs: the command that loads the model catches every ``Error`` that escapes it and reports it.
"""

from dataclasses import dataclass
from itertools import pairwise
from typing import NewType, Self

from lorecraft_core.error import Error
from lorecraft_vfs import RootRelativePath

# The decoded JSON object of a structure specification file, not yet known to state valid rules. A NewType
# only keeps it apart from header and budget JSON; `StructureAspect.parse` is what proves it.
StructureSchema = NewType('StructureSchema', dict[str, object])


class InvalidStructureSchemaError(Error):
    """A structure specification file does not state valid rules in the structure dialect.

    Attributes:
        path: Root-relative path of the rejected file.
    """

    path: RootRelativePath

    def __init__(self, path: RootRelativePath, detail: str) -> None:
        self.path = path
        super().__init__(f'invalid structure schema {path}: {detail}')


@dataclass(frozen=True, slots=True)
class TitleRule:
    """How many H1 titles a document carries, and whether one opens it.

    Attributes:
        count: The number of H1 titles; at least 1, which ``StructureAspect`` checks.
        first: True when an H1 title must come before any other heading.
    """

    count: int
    first: bool


@dataclass(frozen=True, slots=True)
class SectionEntry:
    """An outline entry naming one section, and fixing its position against every other name in the outline.

    Attributes:
        name: The section's heading text.
        optional: True when a document may leave the section out.
    """

    name: str
    optional: bool


@dataclass(frozen=True, slots=True)
class AnySections:
    """An outline entry matching a run, of any length, of sections the outline does not name.

    The run stops at any section the outline names, which pins that name to its own entry wherever it turns up.
    """


type OutlineEntry = SectionEntry | AnySections
"""One entry of a structure specification's outline."""


@dataclass(frozen=True, slots=True)
class StructureAspect:
    """One structure specification's rules, proved usable.

    Construction checks the rules, so an instance is proof of them: no code holding a ``StructureAspect``
    checks them again.

    Attributes:
        path: Root-relative path of the JSON file.
        authority: The prose this file is the machine-checkable half of, such as ``code.md §5``; every finding
            quotes it, so a reader is sent to the rule rather than to the JSON.
        title: The title rule, or None when the specification states none.
        forbid_empty_sections: True when every section must hold content.
        outline: The section order, matched against a document's sections left to right; may be empty.
        forbidden: Sections that must not appear at all.
    """

    path: RootRelativePath
    authority: str
    title: TitleRule | None
    forbid_empty_sections: bool
    outline: tuple[OutlineEntry, ...]
    forbidden: tuple[str, ...]

    def __post_init__(self) -> None:
        """Refuse rules that check nothing, that no title count satisfies, or that contradict themselves.

        Raises:
            InvalidStructureSchemaError: If the aspect states no rule, its title count is below 1, its outline
                names a section twice or places two ``any`` runs side by side, or it forbids a section its own
                outline names.
        """
        if self.title is None and not self.forbid_empty_sections and not self.outline and not self.forbidden:
            raise InvalidStructureSchemaError(self.path, 'states no rule, so it would check nothing')
        if self.title is not None and self.title.count < 1:
            raise InvalidStructureSchemaError(self.path, f'title count must be at least 1, got {self.title.count}')

        named = self.section_names()
        repeated = sorted({name for name in named if named.count(name) > 1})
        if repeated:
            raise InvalidStructureSchemaError(self.path, f'names sections more than once in the outline: {repeated}')

        contradicted = sorted(set(named) & set(self.forbidden))
        if contradicted:
            raise InvalidStructureSchemaError(self.path, f'forbids sections its own outline names: {contradicted}')

        for earlier, later in pairwise(self.outline):
            # Two runs side by side match exactly what one run matches, so an outline written this way means
            # something other than what it says.
            if isinstance(earlier, AnySections) and isinstance(later, AnySections):
                raise InvalidStructureSchemaError(self.path, 'places two `any` runs side by side')

    def section_names(self) -> list[str]:
        """The names of the outline's section entries, in outline order."""
        names: list[str] = []
        for entry in self.outline:
            if isinstance(entry, SectionEntry):
                names.append(entry.name)
        return names

    @classmethod
    def parse(cls, path: RootRelativePath, schema: StructureSchema) -> Self:
        """Read a decoded structure specification into its rules.

        Args:
            path: Where the JSON was read from; every rejection names it.
            schema: The decoded JSON object.

        Raises:
            InvalidStructureSchemaError: If the JSON does not have the dialect's shape, or its rules are not
                usable (see ``__post_init__``).
        """
        unknown = sorted(set(schema) - {'spec', 'description', 'title', 'empty_sections', 'outline', 'forbidden'})
        if unknown:
            raise InvalidStructureSchemaError(path, f'unknown fields: {unknown}')

        authority = schema.get('spec')
        if not isinstance(authority, str):
            raise InvalidStructureSchemaError(path, '`spec` must be a string naming the prose it checks')
        if not isinstance(schema.get('description', ''), str):
            raise InvalidStructureSchemaError(path, '`description` must be a string')

        empty_sections = schema.get('empty_sections')
        if empty_sections is not None and empty_sections != 'forbidden':
            raise InvalidStructureSchemaError(path, f'`empty_sections` can only be "forbidden", got {empty_sections!r}')

        return cls(
            path=path,
            authority=authority,
            title=_parse_title(path, schema.get('title')),
            forbid_empty_sections=empty_sections == 'forbidden',
            outline=_parse_outline(path, schema.get('outline', [])),
            forbidden=_parse_forbidden(path, schema.get('forbidden', [])),
        )


def _parse_title(path: RootRelativePath, value: object) -> TitleRule | None:
    """Read the ``title`` field: absent, or an object with an integer ``count`` and a boolean ``first``.

    Raises:
        InvalidStructureSchemaError: If the field has any other shape.
    """
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) != {'count', 'first'}:
        raise InvalidStructureSchemaError(path, '`title` must be an object with exactly `count` and `first`')
    count = value['count']
    first = value['first']
    # `bool` is a subclass of `int`, so `true` would otherwise pass as a count of 1.
    if not isinstance(count, int) or isinstance(count, bool):
        raise InvalidStructureSchemaError(path, '`title.count` must be an integer')
    if not isinstance(first, bool):
        raise InvalidStructureSchemaError(path, '`title.first` must be a boolean')
    return TitleRule(count=count, first=first)


def _parse_outline(path: RootRelativePath, value: object) -> tuple[OutlineEntry, ...]:
    """Read the ``outline`` field: a list of ``{"section": ..., "optional": ...}`` and ``{"any": true}`` entries.

    Raises:
        InvalidStructureSchemaError: If the field is not a list, or an entry has neither shape.
    """
    if not isinstance(value, list):
        raise InvalidStructureSchemaError(path, '`outline` must be a list')
    entries: list[OutlineEntry] = []
    for entry in value:
        if entry == {'any': True}:
            entries.append(AnySections())
            continue
        if not isinstance(entry, dict) or 'section' not in entry or not set(entry) <= {'section', 'optional'}:
            raise InvalidStructureSchemaError(
                path, f'outline entry {entry!r} is neither {{"section": ...}} nor {{"any": true}}'
            )
        name = entry['section']
        optional = entry.get('optional', False)
        if not isinstance(name, str) or not isinstance(optional, bool):
            raise InvalidStructureSchemaError(
                path, f'outline entry {entry!r} needs a string `section` and a boolean `optional`'
            )
        entries.append(SectionEntry(name=name, optional=optional))
    return tuple(entries)


def _parse_forbidden(path: RootRelativePath, value: object) -> tuple[str, ...]:
    """Read the ``forbidden`` field: a list of section names.

    Raises:
        InvalidStructureSchemaError: If the field is not a list of strings.
    """
    if not isinstance(value, list):
        raise InvalidStructureSchemaError(path, '`forbidden` must be a list of section names')
    names: list[str] = []
    for name in value:
        if not isinstance(name, str):
            raise InvalidStructureSchemaError(path, f'`forbidden` holds {name!r}, which is not a section name')
        names.append(name)
    return tuple(names)
