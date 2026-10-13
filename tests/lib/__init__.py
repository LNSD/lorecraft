"""The test library: helpers the suites under ``tests/`` and the unit tests under ``src/`` share.

Importable as ``lib`` because pytest puts ``tests/`` on ``sys.path`` (``pythonpath`` in the root
``pyproject.toml``); this member is never built, so nothing outside the test run can import it.
"""
