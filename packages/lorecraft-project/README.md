# lorecraft-project

The workspace model behind the [`lorecraft`](https://pypi.org/project/lorecraft/) command line: which corpora,
specifications and documents a repository declares, and which specifications govern each document. It also
fixes the repository layout Lorecraft reads under `docs/`, and how deep a scan goes into it, and parses a
document's text into the parse tree the checks read: its frontmatter, with the line every key is written on.
A check that reads only the frontmatter can have that parsed alone.

The model is loaded through a [`lorecraft-vfs`](https://pypi.org/project/lorecraft-vfs/) filesystem view, never
the disk directly, so it loads the same from a snapshot as from the disk. It prints nothing and installs no
logging handler.

Most users want the command line: `uv tool install lorecraft`.

Licensed under either of the [MIT](LICENSE-MIT) or [Apache 2.0](LICENSE-APACHE) licenses, at your option.
