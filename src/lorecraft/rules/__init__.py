"""The rules and engine conditions the package ships, one module each in a directory per group, all with `@rule`.

How a rule is declared and identified, and the base each subject kind gives a rule, live here too, beside the rules,
and so do the levels a run applies, the table that enables rules and the report a run gives. The
registry walks this package and imports every module in it, its unit tests aside; the modules that declare no rule
add none.
"""
