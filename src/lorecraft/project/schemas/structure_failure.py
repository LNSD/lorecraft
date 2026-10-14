"""The conditions a structure specification fails with when its text is decoded and its rules are checked.

Each is a frozen record of the facts the failure carries, so it is plain data: it compares by value and a result that
holds one can persist (adr-005). They sit below the loader, which records one as the load failure of a structure
file, and are a closed union, so a reader that matches one is checked exhaustive.
"""

from dataclasses import dataclass

from .section_name import SectionName


@dataclass(frozen=True, slots=True)
class StructureSpecProblem:
    """One problem found in a structure specification file, read from the validation error.

    Attributes:
        location: The field the problem concerns, as the keys and indexes that lead to it from the file's root; empty
            when the problem is about the file as a whole.
        message: What is wrong there.
    """

    location: tuple[str | int, ...]
    message: str

    def __str__(self) -> str:
        """The problem as `<field path>: <message>`, or the bare message when it has no location."""
        if not self.location:
            return self.message
        return f'{".".join(str(part) for part in self.location)}: {self.message}'


@dataclass(frozen=True, slots=True)
class UndecodableStructureSpec:
    """The structure file is not JSON, or does not have the structure dialect's shape.

    Attributes:
        problems: Every problem found.
    """

    problems: tuple[StructureSpecProblem, ...]


@dataclass(frozen=True, slots=True)
class EmptyStructureSpec:
    """The structure file states no rule, so it would check nothing."""


@dataclass(frozen=True, slots=True)
class RepeatedOutlineSections:
    """The structure file's outline names one section more than once.

    Attributes:
        sections: The repeated section names, sorted.
    """

    sections: tuple[SectionName, ...]


@dataclass(frozen=True, slots=True)
class RepeatedForbiddenSections:
    """The structure file forbids one section more than once.

    Attributes:
        sections: The repeated section names, sorted.
    """

    sections: tuple[SectionName, ...]


@dataclass(frozen=True, slots=True)
class ForbiddenOutlineSections:
    """The structure file forbids a section its own outline names.

    Attributes:
        sections: The sections both named and forbidden, sorted.
    """

    sections: tuple[SectionName, ...]


@dataclass(frozen=True, slots=True)
class AdjacentAnyRuns:
    """The structure file's outline places two `any` runs side by side."""


@dataclass(frozen=True, slots=True)
class InvalidTitlePattern:
    """The structure file's title `pattern` is not a regular expression that compiles.

    Attributes:
        pattern: The pattern, exactly as written.
        problem: What the compiler rejected.
    """

    pattern: str
    problem: str


@dataclass(frozen=True, slots=True)
class InvalidFrontmatterSchema:
    """The structure file's frontmatter schema is rejected by the Draft 2020-12 meta-schema.

    Attributes:
        problem: What the meta-schema rejected.
    """

    problem: str


@dataclass(frozen=True, slots=True)
class FrontmatterSchemaId:
    """A schema inside the structure file's frontmatter schema carries `$id`, which would make it a resource."""


@dataclass(frozen=True, slots=True)
class ForeignFrontmatterDialect:
    """A schema inside the structure file's frontmatter schema names another dialect than Draft 2020-12.

    Attributes:
        dialect: What the schema's `$schema` holds, as it spells it.
    """

    dialect: str


@dataclass(frozen=True, slots=True)
class UntypedFrontmatterSchema:
    """The structure file's frontmatter schema root does not state `"type": "object"`."""


@dataclass(frozen=True, slots=True)
class UnresolvableFrontmatterSchemaRef:
    """A schema inside the structure file's frontmatter schema holds a `$ref` that does not resolve inside it.

    The reference names a location the schema does not hold, or another resource, which is never fetched.

    Attributes:
        ref: What the `$ref` holds, as written.
    """

    ref: str


@dataclass(frozen=True, slots=True)
class CyclicFrontmatterSchemaRef:
    """A `$ref` in the structure file's frontmatter schema leads back to its own schema with no keyword in between.

    Such a schema never reaches a keyword that reads the document, so validating one would recurse without end.

    Attributes:
        ref: What the `$ref` that closes the cycle holds, as written.
    """

    ref: str


# The conditions a structure specification's rules fail with when they are not usable.
type StructureSpecRuleFailure = (
    EmptyStructureSpec
    | RepeatedOutlineSections
    | RepeatedForbiddenSections
    | ForbiddenOutlineSections
    | AdjacentAnyRuns
)

# Every condition a structure specification fails with once its text is read.
type StructureSpecFailure = (
    UndecodableStructureSpec
    | EmptyStructureSpec
    | RepeatedOutlineSections
    | RepeatedForbiddenSections
    | ForbiddenOutlineSections
    | AdjacentAnyRuns
    | InvalidTitlePattern
    | InvalidFrontmatterSchema
    | FrontmatterSchemaId
    | ForeignFrontmatterDialect
    | UnresolvableFrontmatterSchemaRef
    | CyclicFrontmatterSchemaRef
    | UntypedFrontmatterSchema
)
