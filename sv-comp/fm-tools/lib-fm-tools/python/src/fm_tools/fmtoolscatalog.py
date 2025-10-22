# This file is part of lib-fm-tools, a library for interacting with FM-Tools files:
# https://gitlab.com/sosy-lab/benchmarking/fm-tools
#
# SPDX-FileCopyrightText: 2024 Dirk Beyer <https://www.sosy-lab.org>
#
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path
from typing import Dict, Iterator

from fm_tools.basic_config import BASE_DIR
from fm_tools.competition_participation import Competition, Track
from fm_tools.fmtool import FmTool


class FmToolsCatalog:
    """Class representing a catalog of all FM-Tools and providing access to the data.

    fm_tools_catalog = FmToolsCatalog(path)

    path: Path to the directory that holds the YAML files for all FM-Tools.

    """

    def __init__(self, base_dir: Path = None):
        self.base_dir = base_dir or BASE_DIR
        self.data = self._parse_all_files()

    def _parse_all_files(self) -> Dict[str, FmTool]:
        data = {}
        for file in self.base_dir.glob("*.yml"):
            if file.stem == "schema":
                continue
            data[file.stem] = FmTool.from_file(file)
            assert data[file.stem].id == file.stem, (
                f"Tool from '{file}' should have id '{file.stem}' but has id '{data[file.stem].id}'."
            )
        return data

    def get(self, item: str) -> FmTool:
        return self.data[item]

    def __getitem__(self, item: str) -> FmTool:
        return self.get(item)

    def __getattr__(self, item: str) -> FmTool:
        if item in {"__getstate__", "__setstate__"}:
            return object.__getattr__(self, item)

        try:
            return self.data[item]
        except KeyError:
            raise AttributeError(f"File '{item}' not found") from KeyError

    def __iter__(self) -> Iterator[FmTool]:
        return iter(self.data.values())

    def __contains__(self, item: str) -> bool:
        return item in self.data

    def query(self, competition: Competition, year: int, track: Track = Track.Any):
        from fm_tools.query import Query

        return Query(self, competition, year, track)
