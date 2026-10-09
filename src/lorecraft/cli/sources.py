"""Read the source lines the text output excerpts, through the database of the run that found the diagnostics.

A diagnostic points at lines of its own subject and of other files, such as the specification that states the rule.
The lines come from the same database as the rules' own, so an excerpt shows the text the rules numbered.
"""

from lorecraft.checks import SubjectReport
from lorecraft.core.path import RootRelativePath
from lorecraft.project.database import Database

from .diagnostic_parts import diagnostic_marks, ordered_diagnostics
from .diagnostic_text import SourceLines


def read_sources(database: Database, reports: tuple[SubjectReport, ...]) -> SourceLines:
    """The lines of every file a diagnostic of the run points at a line of.

    A file the database cannot give as text, such as one that is not UTF-8, is left out, and its diagnostics print
    without an excerpt.

    Args:
        database: The revision the reports were produced from.
        reports: One report per subject the run checked.
    """
    paths: set[RootRelativePath] = set()
    for diagnostic in ordered_diagnostics(reports):
        for mark in diagnostic_marks(diagnostic):
            if mark.line is not None:
                paths.add(mark.path)

    sources: dict[RootRelativePath, tuple[str, ...]] = {}
    for path in paths:
        lines = database.source_lines(path)
        if lines is not None:
            sources[path] = lines
    return sources
