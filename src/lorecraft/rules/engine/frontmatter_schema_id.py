"""`LC011`: a structure file's frontmatter schema carries `$id`."""

from dataclasses import dataclass
from typing import ClassVar

from lorecraft.rules.declaration import EngineCondition, Release, RuleCode, RuleName, Severity, rule
from lorecraft.rules.location import Help, Subdiagnostic, WholeSubject

from .__ruleset__ import GROUP_ID


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class FrontmatterSchemaId(EngineCondition):
    """A structure file's frontmatter schema carries `$id`.

    ## What it does

    Checks for structure files whose `frontmatter` schema, or a schema inside it, carries `$id`, which would make it
    a schema resource of its own that nothing can reach.
    Such a file is reported once, at the file, and every document its meta spec governs is listed as skipped in
    coverage, with no rule run over it: a document that was not checked is never reported as clean. Every document
    the file does not govern is checked as if the file were fixed.

    It has no level, so no configuration turns it off, and it is always reported as an error.

    ## Why is this bad?

    Until the file is fixed, the documents it governs are not checked, so a violation in them goes unreported and an
    agent loads them unreviewed.

    ## Example

    `docs/__meta__/guide.structure.json`, with an `$id`:

    ```json
    {
      "frontmatter": {
        "$id": "https://example.com/guide",
        "type": "object"
      }
    }
    ```

    ## Use instead

    Leave `$id` out:

    ```json
    {
      "frontmatter": {"type": "object"}
    }
    ```
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 11)
    NAME: ClassVar[RuleName] = RuleName('frontmatter-schema-id')
    SINCE: ClassVar[Release] = Release('0.3.0')
    SEVERITY: ClassVar[Severity] = Severity.ERROR

    def message(self) -> str:
        """Name the condition."""
        return 'frontmatter schema carries $id'

    def primary(self) -> WholeSubject:
        """The structure file as a whole: no line of it is at fault."""
        return WholeSubject()

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Say how to fix the schema."""
        return (Help('remove $id from every schema in the frontmatter schema'),)
