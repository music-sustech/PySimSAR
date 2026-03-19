"""Pack and unpack .pysimsar project archives.

A .pysimsar file is a standard ZIP archive containing the project directory
contents at the archive root (no nested folder).
"""

from __future__ import annotations

import os
import zipfile
from pathlib import Path


def pack_project(dir_path: str | Path, archive_path: str | Path) -> Path:
    """Create a .pysimsar archive from a project directory.

    Parameters
    ----------
    dir_path : Path
        Project directory containing project.json and related files.
    archive_path : Path
        Destination archive path (should end with .pysimsar).

    Returns
    -------
    Path
        The archive path.
    """
    dir_path = Path(dir_path)
    archive_path = Path(archive_path)

    if not dir_path.is_dir():
        raise ValueError(f"Not a directory: {dir_path}")

    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _dirs, files in os.walk(dir_path):
            for file in files:
                full_path = Path(root) / file
                arcname = full_path.relative_to(dir_path).as_posix()
                zf.write(full_path, arcname)

    return archive_path


def unpack_project(archive_path: str | Path, dir_path: str | Path) -> Path:
    """Extract a .pysimsar archive to a directory.

    Parameters
    ----------
    archive_path : Path
        Path to the .pysimsar archive.
    dir_path : Path
        Destination directory.

    Returns
    -------
    Path
        The destination directory.
    """
    archive_path = Path(archive_path)
    dir_path = Path(dir_path)

    if not archive_path.is_file():
        raise ValueError(f"Not a file: {archive_path}")

    dir_path.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(archive_path, "r") as zf:
        zf.extractall(dir_path)

    return dir_path


__all__ = ["pack_project", "unpack_project"]
