"""Lorecraft project: the model of what a repository declares — corpora, specifications, documents and skills.

The model is built by reading through a ``lorecraft_vfs`` filesystem view, never the disk directly, so it
loads the same from a snapshot as from the disk. The repository layout it reads is fixed in ``layout``.
"""
