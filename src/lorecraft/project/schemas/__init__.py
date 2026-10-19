"""The specifications: their files, the schemas they state, and the repository that reads them.

That is the specification filenames and names, the structure specification with the frontmatter schema, the
counts and the section names it carries, the repository that reads them, the skill frontmatter schema, the
problems both frontmatter schemas report, each placed on the line it is reported on, and where a document's sections
first stop matching an outline.
"""

from .agent_skills_schema import AGENT_SKILLS_FRONTMATTER_SCHEMA
from .document_facts import (
    DocumentTitle,
    TitleConstraint,
    TitleFacts,
    find_document_title,
    title_facts,
)
from .frontmatter_owner import DocumentFrontmatterOwner, FrontmatterOwner, SkillFrontmatterOwner
from .frontmatter_problem import (
    BlockProblem,
    FieldCount,
    FieldGuidance,
    FieldLimit,
    InvalidValueProblem,
    MaxFields,
    MinFields,
    MissingFieldProblem,
    OneOfValues,
    OtherBlockConstraint,
    OtherValueConstraint,
    PatternMismatch,
    UnknownFieldProblem,
    WrongTypeProblem,
)
from .frontmatter_queries import frontmatter_schema_problems, owner_of_frontmatter, parsed_skill_fields
from .frontmatter_schema import FrontmatterSchema, FrontmatterSchemaFailure, StatedFrontmatterSchema
from .name import CorpusSpecName, NamespaceSpecName, SpecName, parse_spec_name
from .outline_alignment import (
    AnyRunAlignment,
    NamedAlignment,
    OutlineAlignmentSpec,
    UnalignedSection,
    align_outlines,
)
from .outline_divergence import (
    AbsentSection,
    DocumentEnd,
    ExpectedSection,
    LeftOver,
    MisplacedSection,
    OutlineDivergenceSpec,
    OutlineEnd,
    UnlistedSection,
    match_outlines,
)
from .outline_queries import outline_alignment
from .repo import Repository, StructureSchemaReadError
from .schema_problems import (
    AgentSkillsSchema,
    LocatedProblem,
    SchemaProblems,
    SchemaSource,
    StructureSpecSchema,
    field_line,
    locate_agent_skills_schema_problems,
    locate_schema_problems,
)
from .section_name import SectionName
from .skill_fields import (
    AllowedTool,
    AllowedTools,
    CommaSeparated,
    MalformedEntry,
    NotATool,
    SkillField,
    SkillFields,
    SkillFieldValue,
    UnbalancedParentheses,
    parse_skill_fields,
)
from .spec_file import (
    DottedSpecStemError,
    InvalidSpecStemError,
    NotASpecFileError,
    NotASpecStemError,
    ProseSpecFile,
    SpecFile,
    SpecFileType,
    StructureSpecFile,
    UnknownSpecFileTypeError,
    parse_spec_file,
    spec_filename,
)
from .structure import (
    SectionEntry,
    StructureSchema,
    StructureSpec,
    TitlePattern,
)
from .structure_failure import StructureSpecProblem
from .structure_file import StructureFile

__all__: list[str] = [
    'DocumentTitle',
    'TitleConstraint',
    'find_document_title',
    'title_facts',
    'TitleFacts',
    'outline_alignment',
    'DocumentFrontmatterOwner',
    'FrontmatterOwner',
    'owner_of_frontmatter',
    'frontmatter_schema_problems',
    'parsed_skill_fields',
    'SkillFrontmatterOwner',
    'CorpusSpecName',
    'NamespaceSpecName',
    'SpecName',
    'parse_spec_name',
    'SpecFileType',
    'ProseSpecFile',
    'StructureSpecFile',
    'SpecFile',
    'parse_spec_file',
    'spec_filename',
    'DottedSpecStemError',
    'NotASpecFileError',
    'UnknownSpecFileTypeError',
    'NotASpecStemError',
    'InvalidSpecStemError',
    'StructureSchema',
    'StructureSpec',
    'FrontmatterSchema',
    'StatedFrontmatterSchema',
    'StructureFile',
    'TitlePattern',
    'SectionEntry',
    'SectionName',
    'FrontmatterSchemaFailure',
    'StructureSpecProblem',
    'StructureSchemaReadError',
    'Repository',
    'AGENT_SKILLS_FRONTMATTER_SCHEMA',
    'SkillField',
    'SkillFieldValue',
    'SkillFields',
    'AllowedTools',
    'AllowedTool',
    'MalformedEntry',
    'CommaSeparated',
    'UnbalancedParentheses',
    'NotATool',
    'parse_skill_fields',
    'MissingFieldProblem',
    'UnknownFieldProblem',
    'WrongTypeProblem',
    'InvalidValueProblem',
    'BlockProblem',
    'FieldCount',
    'FieldLimit',
    'FieldGuidance',
    'OneOfValues',
    'PatternMismatch',
    'OtherValueConstraint',
    'MinFields',
    'MaxFields',
    'OtherBlockConstraint',
    'field_line',
    'SchemaSource',
    'StructureSpecSchema',
    'AgentSkillsSchema',
    'LocatedProblem',
    'SchemaProblems',
    'locate_schema_problems',
    'locate_agent_skills_schema_problems',
    'DocumentEnd',
    'ExpectedSection',
    'LeftOver',
    'OutlineEnd',
    'AbsentSection',
    'MisplacedSection',
    'UnlistedSection',
    'OutlineDivergenceSpec',
    'match_outlines',
    'NamedAlignment',
    'AnyRunAlignment',
    'UnalignedSection',
    'OutlineAlignmentSpec',
    'align_outlines',
]
