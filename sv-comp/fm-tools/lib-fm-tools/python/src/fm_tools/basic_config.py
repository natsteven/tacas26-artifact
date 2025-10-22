# This file is part of lib-fm-tools, a library for interacting with FM-Tools files:
# https://gitlab.com/sosy-lab/benchmarking/fm-tools
#
# SPDX-FileCopyrightText: 2024 Dirk Beyer <https://www.sosy-lab.org>
#
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.parent.parent.parent / "data"


def basicConfig(base_dir: Path = BASE_DIR):
    global BASE_DIR
    BASE_DIR = base_dir
