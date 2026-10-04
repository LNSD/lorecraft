"""A rule module that fails as it is imported, by importing a module that does not exist.

The import is made through `importlib` so the type checker, which reads every module under `src/`, does not
report the missing module; at run time it fails as a plain `import` statement would.
"""

import importlib

importlib.import_module('lorecraft.rules.tests.sample_rules.import_failure.absent')
