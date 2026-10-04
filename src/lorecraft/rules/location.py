"""Where an occurrence points, and the labels, help and notes it renders around its message.

An occurrence names no subject: `Here` is a line of the subject it was found in, `WholeSubject` the subject itself,
and the run that checked the subject supplies its path. `Elsewhere` names another file, such as the specification
that states the rule.

Each subject kind gets only the locations it has. A subject with lines, a document or a skill, takes `Label`,
`Help` and `Note`, which may point at one of its lines or elsewhere. A layout entry has no lines, so it takes
`EntryLabel`, `EntryHelp` and `EntryNote`, which can only point elsewhere. They are separate classes rather than
subclasses narrowing a field, so the type checker rejects a layout rule that writes `Here`.
"""

from dataclasses import dataclass

from lorecraft.core.path import RootRelativePath
from lorecraft.project.syntax import LineNumber


@dataclass(frozen=True, slots=True)
class Here:
    """A line of the subject the occurrence was found in; the run supplies the subject's path.

    Attributes:
        line: The line in the subject.
    """

    line: LineNumber


@dataclass(frozen=True, slots=True)
class WholeSubject:
    """The subject itself, for a subject without lines, such as a layout entry."""


@dataclass(frozen=True, slots=True)
class Elsewhere:
    """A place in another file: the specification, a link's target, a first definition.

    Attributes:
        path: The other file.
        line: The line in that file, or None when the location is the whole file.
    """

    path: RootRelativePath
    line: LineNumber | None = None


# Where a diagnostic points first: a line of the subject, or the subject itself when it has no lines.
type Primary = Here | WholeSubject

# Where a label or a sub-diagnostic of a subject with lines may point.
type Location = Here | Elsewhere


@dataclass(frozen=True, slots=True)
class Label:
    """Text attached to a location of a subject with lines: what is wrong there, or how it relates.

    Attributes:
        at: The place it labels: a line of the subject, or a line or the whole of another file.
        text: What is wrong at `at`, or how that place relates to the occurrence.
    """

    at: Location
    text: str


@dataclass(frozen=True, slots=True)
class Help:
    """How to fix this occurrence, on a subject with lines.

    Attributes:
        text: The fix, addressed to the user who edits the subject.
        at: The place the help points at, or None when it points nowhere.
    """

    text: str
    at: Location | None = None


@dataclass(frozen=True, slots=True)
class Note:
    """Context that explains this occurrence, on a subject with lines.

    Attributes:
        text: The context; for a rule the package states, it names the external specification, with no `at`.
        at: The place the note points at, or None when it points nowhere.
    """

    text: str
    at: Location | None = None


# A sub-diagnostic of a subject with lines, printed under the message.
type Subdiagnostic = Help | Note


@dataclass(frozen=True, slots=True)
class EntryLabel:
    """Text attached to a place in another file, for a layout entry, which has no lines of its own.

    Attributes:
        at: The place it labels.
        text: What is wrong at `at`, or how that place relates to the occurrence.
    """

    at: Elsewhere
    text: str


@dataclass(frozen=True, slots=True)
class EntryHelp:
    """How to fix this occurrence, on a layout entry.

    Attributes:
        text: The fix, addressed to the user who edits the entry.
        at: The place in another file the help points at, or None when it points nowhere.
    """

    text: str
    at: Elsewhere | None = None


@dataclass(frozen=True, slots=True)
class EntryNote:
    """Context that explains this occurrence, on a layout entry.

    Attributes:
        text: The context; for a rule the package states, it names the external specification, with no `at`.
        at: The place in another file the note points at, or None when it points nowhere.
    """

    text: str
    at: Elsewhere | None = None


# A sub-diagnostic of a layout entry, printed under the message.
type EntrySubdiagnostic = EntryHelp | EntryNote
