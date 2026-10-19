"""`LINK003`: a relative link names nothing the repository holds where it is read from."""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import ClassVar, Self, assert_never
from urllib.parse import unquote

from lorecraft.core.path import RootRelativePath
from lorecraft.project.item import ItemKind
from lorecraft.project.link_target import (
    DocumentDirectory,
    EscapingTarget,
    LinkBase,
    LinkTarget,
    PathLookup,
    SkillRoot,
)
from lorecraft.project.query import ItemQuery, item_parse
from lorecraft.project.syntax import (
    AbsoluteDestination,
    ExternalDestination,
    FragmentDestination,
    Link,
    RelativeDestination,
)
from lorecraft.rules.collector import rule
from lorecraft.rules.identity import Level, Release, RuleCode, RuleName
from lorecraft.rules.location import Help, Note, Subdiagnostic
from lorecraft.rules.subject import ByMetaSpec, ByPackage, Gate, MetaSpecPart, QueriedItemRule

from .__ruleset__ import GROUP_ID, SKILL_NOTE, SyntaxLinkResolutionPrimitives


@dataclass(frozen=True, slots=True)
class MissingTarget:
    """A relative link whose target the snapshot holds nothing at.

    Attributes:
        link: The link.
        base: Where the file's relative links are read from.
        target: The root-relative path the link names once read from its base.
    """

    link: Link
    base: LinkBase
    target: RootRelativePath


def missing_targets(primitives: SyntaxLinkResolutionPrimitives) -> tuple[MissingTarget, ...]:
    """The relative links of a Markdown file whose target holds nothing, in document order. Raises nothing.

    A query: it reads the item's links, their targets and their base and nothing else.

    Args:
        primitives: The model state of the Markdown file.
    """
    base = primitives.link_base()
    if base is None:
        return ()
    targets = primitives.link_targets()
    missing: list[MissingTarget] = []
    for link in primitives.query(item_parse).links:
        destination = link.to_destination()
        match destination:
            case RelativeDestination():
                entry = targets.get(destination.path)
            # A link spelling no relative path names no target.
            case ExternalDestination() | AbsoluteDestination() | FragmentDestination():
                continue
            case _:
                assert_never(destination)
        match entry:
            case LinkTarget():
                match entry.lookup:
                    case PathLookup.MISSING:
                        missing.append(MissingTarget(link, base, entry.path))
                    case PathLookup.FILE | PathLookup.DIRECTORY:
                        continue
                    # The scan never read where the path leads, so whether it names anything cannot be told.
                    case PathLookup.OUTSIDE_SCOPE:
                        continue
                    case _:
                        assert_never(entry.lookup)
            # The link climbs past its bound, which `LINK004` reports in a skill and nothing reports in a document.
            case EscapingTarget():
                continue
            # No entry: the item holds no target for the path.
            case None:
                continue
            case _:
                assert_never(entry)
    return tuple(missing)


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class BrokenLink(QueriedItemRule[tuple[MissingTarget, ...]]):
    """A relative link names nothing the repository holds.

    ## What it does

    Checks for links and images whose relative path leads to nothing, in every Markdown file the checks read: a
    document whose corpus states a structure file, a skill's `SKILL.md` and each Markdown file inside the
    skill. A path names a file or a directory, and any symlink on the way to it is followed. No meta spec key
    states the rule: every such file is held to it.

    Where the path is read from depends on the file. In a document, it is read from the document's own directory,
    as Markdown renders it. In a skill, it is read from the skill root, whichever file of the skill holds the link,
    as the Agent Skills specification has it: a link in `references/guide.md` to `SKILL.md` is `SKILL.md`.

    A fragment or a query after the path is ignored, and a `..` cancels the directory written before it. A URL with
    a scheme, an absolute link and a fragment-only link name no relative path, so they are not reported. Neither is
    a link in a skill that climbs above the skill root, which `LINK004` reports, nor one in a document that climbs
    above the repository, nor one leading into a directory the checks do not read, such as `../src/main.py` from a
    document: whether it names something cannot be told.

    ## Why is this bad?

    A link to nothing goes nowhere: an agent that follows it finds no file, and reads nothing of what the link
    promised, or guesses at it.

    ## Example

    `docs/guide/setup.md`, beside which no `install.md` exists:

    ```markdown
    # Setup

    Run the steps in [install](install.md) first.
    ```

    ## Use instead

    Name a file that is there:

    ```markdown
    # Setup

    Run the steps in [installation](installation.md) first.
    ```

    Attributes:
        spec: Always `None`: the package states the rule.
        url: The link's destination as the Markdown parser encodes it, which the message shows percent-decoded.
        base: Where the file's relative links are read from: the skill root, or the document's own directory. It
            picks the help and the "read from" note.
        target: The root-relative path the link names once read from its base, which the snapshot holds nothing at.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 3)
    NAME: ClassVar[RuleName] = RuleName('broken-link')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('0.3.0')
    GATES: ClassVar[Mapping[ItemKind, Gate]] = MappingProxyType(
        {
            ItemKind.DOCUMENT: ByMetaSpec(MetaSpecPart.STRUCTURE),
            ItemKind.SPECIFICATION: ByMetaSpec(MetaSpecPart.STRUCTURE),
            ItemKind.SKILL_ENTRY: ByPackage(),
            ItemKind.SKILL_RESOURCE: ByPackage(),
        }
    )

    spec: None = None
    url: str
    base: LinkBase
    target: RootRelativePath

    def message(self) -> str:
        """Name the destination, percent-decoded as the author wrote it."""
        # The parser percent-encodes a destination, so `[x](a%20b.md)` and `[x](<a b.md>)` both show as `a b.md`.
        return f'`{unquote(self.url)}` names nothing'

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Say what to link, and where the link was read from and so what it names.

        A skill's link also gets the meta spec that has it read from the skill root, first.
        """
        match self.base:
            case SkillRoot():
                return (
                    SKILL_NOTE,
                    Help('link a file or a directory the skill holds, relative to the skill root'),
                    Note(f'read from the skill root, it names `{self.target}`'),
                )
            case DocumentDirectory():
                return (
                    Help('link a file or a directory the repository holds, relative to this file'),
                    Note(f'read from `{self.base.directory}`, it names `{self.target}`'),
                )
            case _:
                assert_never(self.base)

    @classmethod
    def query(cls) -> ItemQuery[tuple[MissingTarget, ...]]:
        """The relative links whose target holds nothing."""
        return missing_targets

    @classmethod
    def judge(cls, facts: tuple[MissingTarget, ...], /) -> tuple[Self, ...]:
        """One occurrence for each relative link whose target holds nothing in the snapshot, on its line, in order.

        Args:
            facts: The links to nothing, each with where it was read from and what it names.
        """
        return tuple(
            cls(line=missing.link.line, url=missing.link.url, base=missing.base, target=missing.target)
            for missing in facts
        )
