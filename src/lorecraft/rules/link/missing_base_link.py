"""`LINK006`: a document that extends another does not link to it under References."""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import ClassVar, Final, Self

from lorecraft.core.path import RootRelativePath
from lorecraft.project.item import ItemKind
from lorecraft.project.link_target import DocumentDirectory, LinkTarget
from lorecraft.project.query import ItemQuery, item_name, item_parse
from lorecraft.project.syntax import FIRST_LINE, LineNumber, RelativeDestination, find_title
from lorecraft.rules.collector import rule
from lorecraft.rules.identity import Level, Release, RuleCode, RuleName
from lorecraft.rules.location import Help, Note, Subdiagnostic
from lorecraft.rules.subject import ByMetaSpec, Gate, MetaSpecPart, QueriedItemRule

from .__ruleset__ import GROUP_ID, GovernanceSyntaxLinkResolutionPrimitives

_REFERENCES: Final[str] = 'References'
"""The heading of the section that names the documents a document builds on."""


@dataclass(frozen=True, slots=True)
class MissingBase:
    """The base a document does not link under its References section.

    Attributes:
        line: The line of the `References` heading, or of the title when there is no such section.
        base: The filename, with its extension, of the base.
        extension: The filename, with its extension, of the document that extends it.
    """

    line: LineNumber
    base: str
    extension: str


def missing_base(primitives: GovernanceSyntaxLinkResolutionPrimitives) -> MissingBase | None:
    """The base a document leaves out of its References section; `None` when it has no base or links it.

    A query: it reads the item's base, name, links, their targets, their base and its headings and nothing else.

    Args:
        primitives: The model state of the document.
    """
    base = primitives.item_base()
    name = primitives.query(item_name)
    link_base = primitives.link_base()
    if base is None or name is None or not isinstance(link_base, DocumentDirectory):
        return None
    headings = primitives.query(item_parse).headings
    title = find_title(headings)
    references = next((heading for heading in headings if heading.level <= 2 and heading.text == _REFERENCES), None)
    wanted = link_base.directory / RootRelativePath.parse(f'{base}.md')
    if references is not None:
        end = next(
            (heading.line for heading in headings if heading.level <= 2 and heading.line > references.line), None
        )
        targets = primitives.link_targets()
        for link in primitives.query(item_parse).links:
            destination = link.to_destination()
            if not isinstance(destination, RelativeDestination):
                continue
            if link.line <= references.line or (end is not None and link.line >= end):
                continue
            entry = targets.get(destination.path)
            if isinstance(entry, LinkTarget) and entry.path == wanted:
                return None
    line: LineNumber = references.line if references is not None else (title.line if title else FIRST_LINE)
    return MissingBase(line=line, base=f'{base}.md', extension=f'{name}.md')


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class MissingBaseLink(QueriedItemRule[MissingBase | None]):
    """A document that extends another does not link to it under References.

    ## What it does

    Checks for a document whose base is not linked in its `References` section. A document's base is the narrowest
    document of its corpus whose name the document's name continues after a hyphen: `python-fn` for
    `python-fn-unchecked`, even when `python-fn-unchecked` sits two names below it. A document with no such name
    has no base and is not judged. The link must lead to the base's file, and lie between the `References` heading
    and the next heading of its level or above, so a link in the text or under `External References` does not count.
    A meta specification of `docs/__meta__/` is judged the same way, its base looked for among the specifications.
    No meta spec key states the rule: every document of a corpus that states a structure file, and every meta
    specification, is held to it.

    The finding is reported on the `References` heading, or on the title when the document has no such section.

    ## Why is this bad?

    An extension specialises its base and is read with it. A reader, or an agent, that loads the extension and finds
    no link to the base has no way to reach what the extension builds on.

    ## Example

    `docs/guide/setup-extra.md`, beside `docs/guide/setup.md`:

    ```markdown
    # Setup extra

    ## References

    - [other](other.md) - Related: Something else
    ```

    ## Use instead

    Name the base, first under References:

    ```markdown
    # Setup extra

    ## References

    - [setup](setup.md) - Extends: What this document specialises
    - [other](other.md) - Related: Something else
    ```

    Attributes:
        spec: Always `None`: the package states the rule.
        base: The filename, with its extension, of the base the document does not link.
        extension: The filename, with its extension, of the document that holds no link to it.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 6)
    NAME: ClassVar[RuleName] = RuleName('missing-base-link')
    LEVEL: ClassVar[Level] = Level.WARN
    SINCE: ClassVar[Release] = Release('0.4.0')
    GATES: ClassVar[Mapping[ItemKind, Gate]] = MappingProxyType(
        {
            ItemKind.DOCUMENT: ByMetaSpec(MetaSpecPart.STRUCTURE),
            ItemKind.SPECIFICATION: ByMetaSpec(MetaSpecPart.STRUCTURE),
        }
    )

    spec: None = None
    base: str
    extension: str

    def message(self) -> str:
        """Name the base the References section leaves out."""
        return f'`{self.extension}` does not link its base `{self.base}` under References'

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Say why the document has that base, then what to add."""
        return (
            Note(f'`{self.extension}` continues the name of `{self.base}`, so it extends it'),
            Help(f'link `{self.base}` first under References'),
        )

    @classmethod
    def query(cls) -> ItemQuery[MissingBase | None]:
        """The base the document does not link under References, when it has one."""
        return missing_base

    @classmethod
    def judge(cls, facts: MissingBase | None, /) -> tuple[Self, ...]:
        """One occurrence when the document has a base that its References section does not link.

        Args:
            facts: The base left out; `None` when the document has no base or links it.
        """
        if facts is None:
            return ()
        return (cls(line=facts.line, base=facts.base, extension=facts.extension),)
