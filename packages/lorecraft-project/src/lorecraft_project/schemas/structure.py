"""The structure aspect: a structure specification file's decoded JSON, and the rules it is decoded into.

The repository reads a ``<stem>.structure.json`` file's text, a ``StructureSchema``, which proves nothing about
it. ``StructureAspect.parse`` is the check, in two steps at the edge. It deserializes the text straight into the
strict, frozen ``StructureFile`` model, so JSON that is malformed or not the dialect's shape is refused before
any rule is read. Then it maps the model to typed rules, and building the aspect refuses a set of rules that
checks nothing or contradicts itself, which no shape can state. So every ``StructureAspect`` that exists states
usable rules, however it was built.

A document's outline is a sequence whose length varies, and JSON Schema cannot state an order over one, so a
structure specification is not JSON Schema. It is this small dialect, whose fields ``structure_file`` declares:

    {
      "$schema": "../schemas/structure.spec.json",
      "description": "what this file governs, for whoever opens it",
      "title": {"count": 1, "first": true},
      "empty_sections": "forbidden",
      "outline": [
        {"section": "Table of Contents", "optional": true},
        {"any": true, "words": 350},
        {"section": "Checklist", "words": 250}
      ],
      "forbidden": ["Changelog"]
    }

The file does not name the prose it is the machine-checkable half of: that is ``<stem>.md`` beside it, and every
finding quotes it.

- ``$schema`` points editors at ``docs/schemas/structure.spec.json``, the JSON Schema ``just gen`` renders from
  ``structure_file``; it is not kept. That schema states the shape only: the rules ``StructureAspect`` refuses
  below it cannot state.
- ``description`` is read by people only, and is not kept.
- ``title`` states how many H1 titles a document carries, and whether one opens it ahead of every section.
- ``empty_sections``, whose one value is ``"forbidden"``, reports a section left without content.
- ``outline`` is the order of the document's sections. A ``section`` entry names one and is required unless
  ``optional``; an ``any`` entry matches a run of sections the outline does not name. An entry's ``words`` caps
  the prose words of each section it matches, H3 subsections included: on an ``any`` entry that is every section
  in the run alone, not the run's total. An entry without ``words`` caps nothing. A word is a whitespace-delimited
  token of prose; fenced code and table rows are not counted.
- ``forbidden`` names sections that must not appear at all.

Nothing here logs: the command that loads the model catches every ``Error`` that escapes it and reports it.
"""

from dataclasses import dataclass, field
from itertools import pairwise
from typing import NewType, Self

from pydantic import ValidationError

from lorecraft_core.error import Error
from lorecraft_vfs import RootRelativePath

from .spec_file import SpecFilenameError, parse_spec_file, prose_filename
from .structure_file import StructureFile, StructureFileAny, StructureFileTitle

# The text of a structure specification file as read, not yet known to be JSON, the dialect's shape or usable
# rules. A NewType only keeps it apart from other text; `StructureAspect.parse` is what proves it.
StructureSchema = NewType('StructureSchema', str)


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
        optional: True when a document may leave the section out; False, the default, when it must carry it.
        words: The most prose words the section may hold, its H3 subsections included, or None, the default, for
            no cap; at least 1, which ``StructureAspect`` checks.
    """

    name: str
    optional: bool = False
    # Checked by the enclosing `StructureAspect` rather than here, so a bad cap is refused as an
    # `InvalidStructureSchemaError` naming the specification file, which this record does not know.
    words: int | None = None


@dataclass(frozen=True, slots=True)
class AnySections:
    """An outline entry matching a run, of any length, of sections the outline does not name.

    The run stops at any section the outline names, which pins that name to its own entry wherever it turns up.

    Attributes:
        words: The most prose words each section in the run may hold, its H3 subsections included, or None, the
            default, for no cap. It caps every section alone, not the run's total; at least 1, which
            ``StructureAspect`` checks.
    """

    # Checked by the enclosing `StructureAspect` rather than here, so a bad cap is refused as an
    # `InvalidStructureSchemaError` naming the specification file, which this record does not know.
    words: int | None = None


type OutlineEntry = SectionEntry | AnySections
"""One entry of a structure specification's outline."""


@dataclass(frozen=True, slots=True)
class StructureAspect:
    """One structure specification's rules, proved usable.

    Construction checks the rules, so an instance is proof of them: no code holding a ``StructureAspect``
    checks them again.

    Attributes:
        path: Root-relative path of the JSON file, ``<stem>.structure.json``; the prose it is the
            machine-checkable half of is ``<stem>.md`` beside it, which ``authority`` names.
        title: The title rule, or None when the specification states none.
        forbid_empty_sections: True when every section must hold content.
        outline: The section order, matched against a document's sections left to right; may be empty.
        forbidden: Sections that must not appear at all.
        authority: The filename of the prose this file is the machine-checkable half of, such as ``code.md``,
            derived from ``path`` at construction. Every finding quotes it, so a reader is sent to the rule rather
            than to the JSON.
    """

    path: RootRelativePath
    title: TitleRule | None
    forbid_empty_sections: bool
    outline: tuple[OutlineEntry, ...]
    forbidden: tuple[str, ...]
    authority: str = field(init=False)

    def __post_init__(self) -> None:
        """Derive the authority from the path, then refuse rules that check nothing, that no count or cap satisfies,
        or that contradict themselves.

        Raises:
            InvalidStructureSchemaError: If the path is not a specification filename, the aspect states no rule,
                its title count or any word cap is below 1, its outline names a section twice or places two ``any``
                runs side by side, or it forbids a section its own outline names.
        """
        try:
            spec_file = parse_spec_file(self.path)
        except SpecFilenameError as exc:
            raise InvalidStructureSchemaError(self.path, f'is not at a specification filename: {exc}') from exc
        # `authority` is derived from `path` rather than passed in, so the two cannot disagree. A frozen dataclass
        # refuses plain assignment, and `object.__setattr__` is the one way to set a field during construction.
        object.__setattr__(self, 'authority', prose_filename(spec_file.name))

        if self.title is None and not self.forbid_empty_sections and not self.outline and not self.forbidden:
            raise InvalidStructureSchemaError(self.path, 'states no rule, so it would check nothing')
        if self.title is not None and self.title.count < 1:
            raise InvalidStructureSchemaError(self.path, f'title count must be at least 1, got {self.title.count}')
        for entry in self.outline:
            if entry.words is not None and entry.words < 1:
                raise InvalidStructureSchemaError(
                    self.path, f'outline word cap must be at least 1, got {entry.words} on {_describe_entry(entry)}'
                )

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
        """Deserialize a structure specification's text into its rules.

        Args:
            path: Where the text was read from; every rejection names it.
            schema: The file's text.

        Raises:
            InvalidStructureSchemaError: If the text is not JSON, does not have the dialect's shape, or its rules
                are not usable (see ``__post_init__``).
        """
        try:
            file = StructureFile.model_validate_json(schema)
        except ValidationError as exc:
            raise InvalidStructureSchemaError(path, _describe(exc)) from exc

        outline: list[OutlineEntry] = []
        for entry in file.outline:
            if isinstance(entry, StructureFileAny):
                outline.append(AnySections(words=entry.words))
            else:
                outline.append(SectionEntry(name=entry.section, optional=entry.optional, words=entry.words))

        return cls(
            path=path,
            title=_title_rule(file.title),
            forbid_empty_sections=file.empty_sections == 'forbidden',
            outline=tuple(outline),
            forbidden=file.forbidden,
        )


def _title_rule(title: StructureFileTitle | None) -> TitleRule | None:
    """The title rule a file's ``title`` field states, or None when the file states none."""
    if title is None:
        return None
    return TitleRule(count=title.count, first=title.first)


def _describe_entry(entry: OutlineEntry) -> str:
    """How an outline entry is named in a rejection: its section name, or ``any`` for a run."""
    if isinstance(entry, SectionEntry):
        return f'section {entry.name!r}'
    return 'an `any` run'


def _describe(error: ValidationError) -> str:
    """Every problem pydantic found in one file, as ``<field path>: <message>``, joined into one line."""
    problems: list[str] = []
    for detail in error.errors(include_url=False):
        location = '.'.join(str(part) for part in detail['loc'])
        if location:
            problems.append(f'{location}: {detail["msg"]}')
        else:
            problems.append(detail['msg'])
    return '; '.join(problems)
