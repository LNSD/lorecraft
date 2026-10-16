"""The YAML syntax Lorecraft reads, and the one package that imports ruamel.yaml.

The subset of YAML 1.2 Lorecraft reads is read here, into a tree of values, or into the first problem the
text writes. Each submodule is its own entry point, imported by its full name, such as `lorecraft.yaml.reader`; the
grammar the library is bent to, `lorecraft.yaml.basic_yaml`, is read inside this package alone.
"""
