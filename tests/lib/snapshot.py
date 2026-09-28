"""Snapshot files for command output: one plain-text file per snapshot, so a review diff reads like the terminal.

syrupy's default stores every snapshot of a module in one ``.ambr`` file, with each string quoted and indented.
A text extension stores the output exactly as the command printed it. ``just snapshot-update`` writes or
refreshes them and ``just snapshot-review`` shows what changed, before they are committed like any other file.
"""

from syrupy.extensions.single_file import SingleFileSnapshotExtension, WriteMode


class TextSnapshotExtension(SingleFileSnapshotExtension):
    """One snapshot per ``.txt`` file, stored as UTF-8 text."""

    _write_mode = WriteMode.TEXT
    file_extension = 'txt'


class JsonTextSnapshotExtension(TextSnapshotExtension):
    """One snapshot per ``.json`` file, stored as the text the command printed, not re-encoded."""

    file_extension = 'json'
