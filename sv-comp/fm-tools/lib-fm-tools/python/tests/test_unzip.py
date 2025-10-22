# This file is part of lib-fm-tools, a library for interacting with FM-Tools files:
# https://gitlab.com/sosy-lab/benchmarking/fm-tools
#
# SPDX-FileCopyrightText: 2024 Dirk Beyer <https://www.sosy-lab.org>
#
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

from fm_tools.files import unzip

ARCHIVE = Path(__file__).parent / "resources" / "archive.zip"


def test_unzip(fs):
    fs.add_real_directory(ARCHIVE.parent)

    unzip(ARCHIVE, Path("/tmp") / "test_unzip_archive")

    assert (Path("/tmp") / "test_unzip_archive").exists()
    assert (Path("/tmp") / "test_unzip_archive" / "tool" / "tool.sh").exists()
    assert (Path("/tmp") / "test_unzip_archive" / "license.txt").is_file()
    assert not (Path("/tmp") / "archive").exists()
