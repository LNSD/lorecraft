# lorecraft-core

The base every package behind the [`lorecraft`](https://pypi.org/project/lorecraft/) command line builds on:
`Error`, the class each package's failure families derive from, so a caller can catch every expected Lorecraft
failure with one `except`.

It depends on no other package, prints nothing, and installs no logging handler.

Most users want the command line: `uv tool install lorecraft`.

Licensed under either of the [MIT](LICENSE-MIT) or [Apache 2.0](LICENSE-APACHE) licenses, at your option.
