"""`LINK003`: a relative link names nothing the repository holds where it is read from."""

from dataclasses import dataclass
from typing import ClassVar, Self, assert_never
from urllib.parse import unquote

from lorecraft.project.context import MarkdownContext
from lorecraft.project.link_target import DocumentDirectory, LinkBase, PathLookup, SkillRoot
from lorecraft.rules.declaration import Level, Release, RuleCode, RuleName, rule
from lorecraft.rules.location import Help, Subdiagnostic
from lorecraft.rules.subject import MarkdownRule

from .__ruleset__ import GROUP_ID


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class BrokenLink(MarkdownRule):
    """A relative link names nothing the repository holds.

    ## What it does

    Checks for links and images whose relative path leads to nothing, in every Markdown file the checks read: a
    document whose corpus states a structure specification, a skill's `SKILL.md` and each Markdown file inside the
    skill. A path names a file or a directory, and any symlink on the way to it is followed. No specification key
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
        base: Where the file's relative links are read from, which says what the link fails to name and how to fix
            it: the skill root, or the document's own directory.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 3)
    NAME: ClassVar[RuleName] = RuleName('broken-link')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('0.3.0')

    spec: None = None
    url: str
    base: LinkBase

    def message(self) -> str:
        """Name the destination, percent-decoded as the author wrote it, and what it names nothing in."""
        # The parser percent-encodes a destination, so `[x](a%20b.md)` and `[x](<a b.md>)` both show as `a b.md`.
        match self.base:
            case SkillRoot():
                return f'`{unquote(self.url)}` names nothing in the skill'
            case DocumentDirectory():
                return f'`{unquote(self.url)}` names nothing in the repository'
            case _:
                assert_never(self.base)

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Say what to link, and where the path is read from."""
        match self.base:
            case SkillRoot():
                return (Help('link a file or a directory the skill holds, relative to the skill root'),)
            case DocumentDirectory():
                return (Help('link a file or a directory the repository holds, relative to this file'),)
            case _:
                assert_never(self.base)

    @classmethod
    def check(cls, subject: MarkdownContext) -> tuple[Self, ...]:
        """One occurrence for each relative link whose target holds nothing in the snapshot, on its line, in order.

        Args:
            subject: The Markdown file whose relative links are judged by what the snapshot holds at each target.
        """
        base = subject.link_base()
        targets = subject.link_targets()
        occurrences: list[Self] = []
        for link in subject.parse().links:
            normalised = link.to_normalised_relative_path()
            # A link spelling no relative path names no target.
            if normalised is None:
                continue
            lookup = targets.get(normalised)
            match lookup:
                case PathLookup.MISSING:
                    occurrences.append(cls(line=link.line, url=link.url, base=base))
                case PathLookup.PRESENT:
                    continue
                # The scan never read where the path leads, so whether it names anything cannot be told.
                case PathLookup.OUTSIDE_SCOPE:
                    continue
                # No entry: the link climbs past its bound, above the skill root or above the repository root.
                case None:
                    continue
                case _:
                    assert_never(lookup)
        return tuple(occurrences)
