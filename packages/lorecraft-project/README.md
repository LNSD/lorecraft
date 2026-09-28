# lorecraft-project

The workspace model behind the [`lorecraft`](https://pypi.org/project/lorecraft/) command line: which corpora,
specifications, documents and skills a repository declares, which specifications govern each document, and
which agents see each skill. It also fixes the repository layout Lorecraft reads — `docs/` and the agent
skills directories, and how deep a scan goes into each.

The model is loaded through a [`lorecraft-vfs`](https://pypi.org/project/lorecraft-vfs/) filesystem view, never
the disk directly, so it loads the same from a snapshot as from the disk. It prints nothing and installs no
logging handler.

Most users want the command line: `uv tool install lorecraft`.

Licensed under either of the [MIT](LICENSE-MIT) or [Apache 2.0](LICENSE-APACHE) licenses, at your option.
