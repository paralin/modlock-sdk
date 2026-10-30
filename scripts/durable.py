"""Write files so a crash or power loss never leaves a later run trusting bad data.

Windows records a new file's size before its lazy writer puts the data on disk,
so a power loss in between leaves a file of the right size filled with zeros.
Each operation here flushes the data before writing whatever a later run trusts
to mean the data is good: a marker, a modification time, or a file's name.
"""

from __future__ import annotations

import io
import os
import shutil
import tarfile
import zipfile
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# Written into an unpacked folder once every file in it is on disk.
COMPLETE = ".complete"
# Files flushed at once while unpacking; each flush waits on the disk.
FLUSH_THREADS = 16


def flush(path: Path) -> None:
    """Wait until a file's data is on disk."""
    # FlushFileBuffers, behind fsync on Windows, needs a handle that can write.
    fd = os.open(path, os.O_RDWR if os.name == "nt" else os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def flush_all(paths: Iterable[Path]) -> None:
    """Wait until every file's data is on disk, flushing several at once."""
    with ThreadPoolExecutor(FLUSH_THREADS) as pool:
        list(pool.map(flush, paths))


def flush_changed(folder: Path, since: float) -> None:
    """Wait until the data of every file in folder modified since a time is on disk.

    For files another program wrote without flushing them; since is a
    time.time() taken before it started.
    """
    flush_all(path for path in folder.rglob("*")
              if path.is_file() and not path.is_symlink() and path.stat().st_mtime >= since)


def write(path: Path, data: bytes) -> None:
    """Replace a file's contents so a crash leaves the old contents or the new."""
    staging = path.with_name(path.name + ".partial")
    staging.write_bytes(data)
    flush(staging)
    os.replace(staging, path)


def copy(source: Path, target: Path) -> None:
    """Copy a file and its modification time, which marks the copy complete.

    The time is set only once the data is on disk, so a crash leaves a copy
    whose time differs from its source and is copied again.
    """
    shutil.copyfile(source, target)
    flush(target)
    shutil.copystat(source, target)


def unpack(folder: Path, download: Callable[[], bytes]) -> None:
    """Make folder hold a zip or tar archive's files, downloading it only when needed.

    A folder is complete once it holds the COMPLETE marker, written after every
    file reached the disk; any other folder is replaced, so an extraction cut
    short by a crash is redone.
    """
    if (folder / COMPLETE).is_file():
        return
    shutil.rmtree(folder, ignore_errors=True)
    archive = io.BytesIO(download())
    if zipfile.is_zipfile(archive):
        zipfile.ZipFile(archive).extractall(folder)
    else:
        with tarfile.open(fileobj=archive) as tar:
            tar.extractall(folder, filter="tar")
    flush_all(path for path in folder.rglob("*") if path.is_file() and not path.is_symlink())
    write(folder / COMPLETE, b"")
