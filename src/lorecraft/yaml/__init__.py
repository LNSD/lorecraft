"""The YAML syntax Lorecraft reads, and the one package that imports ruamel.yaml.

The subset of YAML 1.2 that frontmatter is written in is read here, with what it leaves out refused as a typed
value. Two importers outside it remain, named in the import contract of `pyproject.toml`, until the event decoding
moves in. Each submodule is its own entry point, imported by its full name, such as `lorecraft.yaml.basic_yaml`.
"""
