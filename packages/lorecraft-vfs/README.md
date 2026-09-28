# lorecraft-vfs

The filesystem boundary behind the [`lorecraft`](https://pypi.org/project/lorecraft/) command line. It reads a
repository through one read-only view with two implementations: one that reads the disk, and one that answers
from a snapshot a single scan produced, without touching the disk. Two snapshots compare into a change set.
Every path it takes or returns is a root-relative path, a type that cannot be absolute or climb with `..`, so
no argument can name a file outside the repository. What a scan reads is the scope its caller passes.

It prints nothing and installs no logging handler. Most users want the command line: `uv tool install lorecraft`.

Licensed under either of the [MIT](LICENSE-MIT) or [Apache 2.0](LICENSE-APACHE) licenses, at your option.
