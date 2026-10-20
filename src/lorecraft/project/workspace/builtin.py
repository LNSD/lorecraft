"""Builtin workspace specifications."""

from lorecraft.core.num import NonZeroUnsignedInt
from lorecraft.core.path import RootRelativePath
from lorecraft.project.schemas import StructureSchema, StructureSpec, StructureSpecFile, parse_spec_name

_SKILLS_SPEC_FILE = StructureSpecFile(
    # LEN002 uses only the builtin source identity; other structure fact readers still require repository paths.
    RootRelativePath.parse('docs/__meta__/skills.spec.json'),
    parse_spec_name('skills'),
)

AGENT_SKILLS_STRUCTURE_SPEC = StructureSpec.parse(_SKILLS_SPEC_FILE, StructureSchema('{"lines": 500}'))
assert isinstance(AGENT_SKILLS_STRUCTURE_SPEC, StructureSpec), (
    'the builtin skills line limit is a usable structure spec'
)
assert AGENT_SKILLS_STRUCTURE_SPEC.lines == NonZeroUnsignedInt(500), 'the builtin skill floor is 500 lines'
