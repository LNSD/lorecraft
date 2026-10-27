"""What the `LC2xx` group's rules share: the group and the schemas governing each subject's frontmatter.

A document's and a skill's frontmatter block is governed by the ordered schema inputs available to it. Rules over
both subject kinds declare a gate for each and judge either kind through the shared query facts. The frontmatter
part is governed when at least one applicable schema is loaded. `owner_spec` and `schema_spec` state which spec
grounds an occurrence, and `spec_note` or `schema_note` says which it is. Rules over a skill's `allowed-tools` use
`Always` and name the field's source through `ALLOWED_TOOLS_NOTE`; its recommended length is set by Lorecraft, not
the spec.

A field's line, or line 1 in its absence, is decided in one place, `field_line` in `lorecraft.project.schemas`: the
schema problems arrive placed through it, and a rule that reports at a field's line calls it rather than search the
keys itself.

What the schema states about a field reaches the reader as typed data on the occurrence, rendered the same way by every
rule that has it: the values it allows through `allowed_values_help`, an example through `example_note`. A rule lists
its children in one order: the note naming the spec first, then the help, then the other notes.
"""

from typing import Final

from lorecraft.rules.identity import RuleGroup, RuleGroupPrefix

GROUP_ID: Final[RuleGroup] = RuleGroup(RuleGroupPrefix('LC'), 'Frontmatter checks', range(200, 300))
"""The group of the rules over a subject's frontmatter: the block itself, and the schema that governs it."""
