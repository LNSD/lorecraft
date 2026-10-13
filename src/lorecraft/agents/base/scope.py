"""The two scopes an agent reads in, and a path spelled from the root of each.

An agent reads in the project scope, the repository it works in, and in the user scope, the user's home
directory. Both spell a path the same way, so a path of one scope handed where the other is expected reads as
valid. Each scope has its own type so the type checker rejects that mix-up.
"""

from typing import NewType

from lorecraft.core.path import RootRelativePath

ProjectPath = NewType('ProjectPath', RootRelativePath)
"""A path relative to the repository root, such as ``.claude/skills``. Validated as a ``RootRelativePath``: it is
neither absolute nor holds a ``..`` component."""

UserPath = NewType('UserPath', RootRelativePath)
"""A path relative to the user's home directory, such as ``.claude/skills`` for ``~/.claude/skills``. Validated as
a ``RootRelativePath``, whose root here is the home directory."""
