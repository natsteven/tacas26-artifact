# This file is part of lib-fm-tools, a library for interacting with FM-Tools files:
# https://gitlab.com/sosy-lab/benchmarking/fm-tools
#
# SPDX-FileCopyrightText: 2024 Dirk Beyer <https://www.sosy-lab.org>
#
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

import pytest

import fm_tools.exceptions
import fm_tools.update_archives
from fm_tools.competition_participation import Competition


def test_update_archive_2ls():
    fm_tools_path = Path(__file__).parent.parent.parent.parent / "data"
    fm_tools.update_archives.update_archives(
        fm_tools_path,
        "2ls",
        fm_tools_path.parent / "archives",
        Competition.SV_COMP,
        2025,
        "Verification",
    )


def test_update_archive_fail():
    fm_tools_path = Path(__file__).parent.parent.parent.parent / "data"
    with pytest.raises(fm_tools.exceptions.DownloadUnsuccessfulException):
        fm_tools.update_archives.update_archives(
            fm_tools_path,
            "2lsX",
            fm_tools_path.parent / "archives",
            Competition.SV_COMP,
            2025,
            "Verification",
        )


if __name__ == "__main__":
    test_update_archive_fail()
