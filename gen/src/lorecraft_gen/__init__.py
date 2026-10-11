"""The generators of the committed generated files, run by the `gen-*` recipes of the `justfile`.

Each module is one generator and runs as `python -m lorecraft_gen.<module> [--outdir <dir>]`, from the repository
root. A generator imports what it renders from `lorecraft`; `lorecraft` never imports this package.
"""
