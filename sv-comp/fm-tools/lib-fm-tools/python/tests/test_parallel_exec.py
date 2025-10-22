# This file is part of lib-fm-tools, a library for interacting with FM-Tools files:
# https://gitlab.com/sosy-lab/benchmarking/fm-tools
#
# SPDX-FileCopyrightText: 2024 Dirk Beyer <https://www.sosy-lab.org>
#
# SPDX-License-Identifier: Apache-2.0

from multiprocessing import Pool
from pathlib import Path

from fm_tools.fmtoolscatalog import FmToolsCatalog


def get_names(tools: FmToolsCatalog):
    return [tool.name for tool in tools]


def run_in_parallel(func, inputs, processes):
    with Pool(processes) as pool:
        return pool.map(func, inputs)


def test_parallel_execution():
    """
    Test succeeds if no recursion errors occur.
    """
    tools = FmToolsCatalog((Path(__file__).parent.parent.parent.parent / "data").resolve())
    names = run_in_parallel(get_names, [tools] * 10, 4)
    print(names)


if __name__ == "__main__":
    test_parallel_execution()
