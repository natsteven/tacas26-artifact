# This file is part of lib-fm-tools, a library for interacting with FM-Tools files:
# https://gitlab.com/sosy-lab/benchmarking/fm-tools
#
# SPDX-FileCopyrightText: 2024 Dirk Beyer <https://www.sosy-lab.org>
#
# SPDX-License-Identifier: Apache-2.0

import os
import shutil
from pathlib import Path

import pytest

import fm_tools.exceptions
import fm_tools.files


def teardown_module():
    target = Path(__file__).parent / "output"
    if target.exists():
        shutil.rmtree(target)
    target = Path(__file__).parent / "output-xyz"
    if target.exists():
        os.chmod(target, 0o755)
        shutil.rmtree(target)


def test_file_checksum_matching():
    target = Path(__file__).parent / "output" / "archive.zip"
    if not target.parent.exists():
        target.parent.mkdir(parents=True)
    with open(Path(__file__).parent / "resources" / "archive.zip", "rb") as file:
        fm_tools.files.write_file_from_iterator(
            target, iter(file), expected_checksum="8e38bfa8b01a04e8419025dcab610d25"
        )


def test_file_checksum_not_matching():
    target = Path(__file__).parent / "output" / "archive.zip"
    if not target.parent.exists():
        target.parent.mkdir(parents=True)
    with (
        open(Path(__file__).parent / "resources" / "archive.zip", "rb") as file,
        pytest.raises(fm_tools.exceptions.DownloadUnsuccessfulException, match=".*checksum.*"),
    ):
        fm_tools.files.write_file_from_iterator(
            target, iter(file), expected_checksum="8e38bfa8b01a04e8419025dcab610d26"
        )


def test_file_overwrite():
    source = Path(__file__).parent / "resources" / "archive.zip"
    target = Path(__file__).parent / "output" / "archive.zip"
    if not target.parent.exists():
        target.parent.mkdir(parents=True)
    shutil.copy(source, target)
    with open(source, "rb") as file:
        fm_tools.files.write_file_from_iterator(target, iter(file), expected_checksum=None)


@pytest.mark.skipif(os.geteuid() == 0, reason="Test skipped: running as root, permissions cannot be enforced.")
def test_file_write_fail():
    source = Path(__file__).parent / "resources" / "archive.zip"
    target = Path(__file__).parent / "output-xyz" / "archive.zip"
    if not target.parent.exists():
        target.parent.mkdir(parents=True)
    os.chmod(target.parent, 0o555)
    with open(source, "rb") as file, pytest.raises(fm_tools.exceptions.DownloadUnsuccessfulException):
        fm_tools.files.write_file_from_iterator(target, iter(file), expected_checksum=None)


if __name__ == "__main__":
    test_file_checksum_matching()
