"""Read the source lines the text output excerpts, through the database of the run that found the diagnostics.

A diagnostic points at lines of its own subject and of other files, such as the specification that states the rule.
The lines come from the same database as the rules' own, so an excerpt shows the text the rules numbered.
"""

from typing import assert_never

from lorecraft.core.path import RootRelativePath
from lorecraft.project.database import Database
from lorecraft.rules.report import RunReport

from .diagnostic_parts import LineMark, WholeFileMark, diagnostic_marks, ordered_diagnostics
from .diagnostic_text import SourceLines, SourceText


def read_sources(database: Database, reports: tuple[RunReport, ...]) -> SourceLines:
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
            match mark:
                case LineMark():
                    paths.add(mark.path)
                case WholeFileMark():
                    pass
                case _:
                    assert_never(mark)

    sources: dict[RootRelativePath, SourceText] = {}
    for path in paths:
        lines = database.source_lines(path)
        if lines is not None:
            sources[path] = SourceText(lines)
    return sources
