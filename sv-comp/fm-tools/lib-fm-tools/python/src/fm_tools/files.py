# This file is part of lib-fm-tools, a library for interacting with FM-Tools files:
# https://gitlab.com/sosy-lab/benchmarking/fm-tools
#
# SPDX-FileCopyrightText: 2024 Dirk Beyer <https://www.sosy-lab.org>
#
# SPDX-License-Identifier: Apache-2.0

import contextlib
import hashlib
import os
import shutil
import tarfile
import tempfile
from pathlib import Path
from typing import IO, Iterable, cast
from zipfile import ZipFile, ZipInfo

from fm_tools.exceptions import DownloadUnsuccessfulException


def unzip(archive: Path | str | IO[bytes], target_dir: Path):
    """
    Extracts a zip or tar archive to the target_dir, ensuring only one top-level directory in the archive.
    Supports .zip, .tar, .tar.gz, .tgz files.
    """
    if target_dir.is_dir():
        shutil.rmtree(target_dir)

    is_zip = False
    is_tar = False
    try:
        with ZipFile(archive) as zipfile:
            zipfile.testzip()  # Test if it is a valid zip file
            is_zip = True
    except Exception:
        is_tar = True

    if is_zip:
        with ZipFile(archive, "r") as zipfile:
            root_dir_amount = len(
                {member.filename.split("/")[0] for member in zipfile.filelist if member.filename.count("/") <= 1}
            )
            if root_dir_amount != 1:
                raise ValueError(
                    f"Archive structure is not supported!\n"
                    "Exactly one top level directory expected,"
                    f" {root_dir_amount} were given."
                )
            top_level_zip_folder = zipfile.filelist[0].filename.split("/")[0]
            top_folder = target_dir.parent / top_level_zip_folder
            # Not to use extract all as it does not preserves the permission for executable files.
            # See: https://bugs.python.org/issue15795
            # See https://stackoverflow.com/questions/39296101/python-zipfile-removes-execute-permissions-from-binaries
            for member in zipfile.namelist():
                if not isinstance(member, ZipInfo):
                    member = zipfile.getinfo(member)
                extracted_file = zipfile.extract(member, target_dir.parent)
                # This takes first two bytes from four bytes.
                attr = member.external_attr >> 16
                if attr != 0:
                    os.chmod(extracted_file, attr)
            top_folder.rename(target_dir)
    elif is_tar:
        # Use explicit if-else to avoid type issues with tarfile.open
        archive_path = Path(archive) if isinstance(archive, (str, Path)) else None
        if archive_path:
            with tarfile.open(str(archive_path), "r:*") as tar:
                members = tar.getmembers()
                top_dirs = {m.name.split("/")[0] for m in members if m.name.count("/") <= 1}
                if len(top_dirs) != 1:
                    raise ValueError(
                        f"Archive structure is not supported!\n"
                        "Exactly one top level directory expected,"
                        f" {len(top_dirs)} were given."
                    )
                top_level_tar_folder = next(iter(top_dirs))
                top_folder = target_dir.parent / top_level_tar_folder
                tar.extractall(path=target_dir.parent)
                # Restore permissions
                for member in members:
                    extracted_path = target_dir.parent / member.name
                    if member.mode and extracted_path.exists():
                        extracted_path.chmod(member.mode)
                top_folder.rename(target_dir)
        else:
            # Only allow file-like objects for fileobj
            if not (hasattr(archive, "read") and hasattr(archive, "seek")):
                raise ValueError(
                    "For tar archives, if not a path, archive must be a file-like object (with read/seek methods)."
                )
            archive_fileobj = cast(IO[bytes], archive)
            with tarfile.open(fileobj=archive_fileobj, mode="r|*") as tar:
                members = tar.getmembers()
                top_dirs = {m.name.split("/")[0] for m in members if m.name.count("/") <= 1}
                if len(top_dirs) != 1:
                    raise ValueError(
                        f"Archive structure is not supported!\n"
                        "Exactly one top level directory expected,"
                        f" {len(top_dirs)} were given."
                    )
                top_level_tar_folder = next(iter(top_dirs))
                top_folder = target_dir.parent / top_level_tar_folder
                tar.extractall(path=target_dir.parent)
                # Restore permissions
                for member in members:
                    extracted_path = target_dir.parent / member.name
                    if member.mode and extracted_path.exists():
                        extracted_path.chmod(member.mode)
                top_folder.rename(target_dir)
    else:
        raise ValueError("Unsupported archive format. Only .zip, .tar, .tar.gz, .tgz are supported.")


def write_file_from_iterator(target_path: Path, content_iter: Iterable[bytes], expected_checksum=None):
    try:
        tmp_fd, tmp_file = tempfile.mkstemp(
            prefix="." + os.path.basename(target_path) + ".",
            dir=os.path.dirname(target_path),
        )
    except OSError as e:
        raise DownloadUnsuccessfulException(
            f"Creating temporary file next to the original file '{target_path}' failed: {e}"
        ) from e
    try:
        hash_obj = hashlib.md5()
        for chunk in content_iter:
            os.write(tmp_fd, chunk)
            hash_obj.update(chunk)
        checksum = hash_obj.hexdigest()
        if expected_checksum and checksum != expected_checksum:
            raise DownloadUnsuccessfulException(
                "Checksum of downloaded file does not match provided checksum: "
                f"Expected {expected_checksum}, got {checksum}"
            )
        os.close(tmp_fd)
        os.rename(tmp_file, target_path)
    except OSError as e:
        raise DownloadUnsuccessfulException(f"Writing downloaded content failed for file '{target_path}': {e}") from e
    finally:
        with contextlib.suppress(OSError):
            os.unlink(tmp_file)
