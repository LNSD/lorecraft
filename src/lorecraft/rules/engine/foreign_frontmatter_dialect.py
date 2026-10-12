"""`LC012`: a structure file's frontmatter schema names another JSON Schema dialect."""

from dataclasses import dataclass
from typing import ClassVar

from lorecraft.project.schemas.structure_file import JSON_SCHEMA_DIALECT
from lorecraft.rules.declaration import EngineCondition, Release, RuleCode, RuleName, Severity, rule
from lorecraft.rules.location import Help, Note, Subdiagnostic, WholeSubject

from .__ruleset__ import GROUP_ID


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class ForeignFrontmatterDialect(EngineCondition):
    """A structure file's frontmatter schema names another JSON Schema dialect.

    ## What it does

    Checks for structure files whose `frontmatter` schema, or a schema inside it, sets `$schema` to anything but the
    2020-12 dialect, the only one a frontmatter schema is written in.
    Such a file is reported once, at the file, and every document its meta spec governs is listed as skipped in
    coverage, with no rule run over it: a document that was not checked is never reported as clean. Every document
    the file does not govern is checked as if the file were fixed.

    `lorecraft check` does not report this code yet: it stops with exit status 2 at a structure file it cannot
    use, so the file is not reported and no document it governs is listed as skipped.

    It has no level, so no configuration turns it off, and it is always reported as an error.

    ## Why is this bad?

    Until the file is fixed, the documents it governs are not checked, so a violation in them goes unreported and an
    agent loads them unreviewed.

    ## Example

    `docs/__meta__/guide.structure.json`, written in draft-07:

    ```json
    {
      "frontmatter": {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object"
      }
    }
    ```

    ## Use instead

    Name the 2020-12 dialect, or leave `$schema` out:

    ```json
    {
      "frontmatter": {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object"
      }
    }
    ```

    Attributes:
        dialect: What `$schema` holds, as Python spells the value.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 12)
    NAME: ClassVar[RuleName] = RuleName('foreign-frontmatter-dialect')
    SINCE: ClassVar[Release] = Release('0.3.0')
    SEVERITY: ClassVar[Severity] = Severity.ERROR

    dialect: str

    def message(self) -> str:
        """Name the condition."""
        return 'frontmatter schema names another JSON Schema dialect'

    def primary(self) -> WholeSubject:
        """The structure file as a whole: no line of it is at fault."""
        return WholeSubject()

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Say what `$schema` holds, and which dialect to name."""
        return (
            Note(f'$schema holds {self.dialect}'),
            Help(f'name {JSON_SCHEMA_DIALECT}, or leave $schema out'),
        )
