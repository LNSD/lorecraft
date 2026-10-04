"""Rules packages of sample rules, one per case the registry tests walk.

Each subpackage is a rules package of its own: a test loads the registry from one of them, and sees only the
rules declared there. `rendered_message` is the exception, which no registry test walks: its rule renders its
message from a field, for the tests of the order diagnostics print in.
"""
