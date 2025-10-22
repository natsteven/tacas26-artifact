# This file is part of lib-fm-tools, a library for interacting with FM-Tools files:
# https://gitlab.com/sosy-lab/benchmarking/fm-tools
#
# SPDX-FileCopyrightText: 2024 Dirk Beyer <https://www.sosy-lab.org>
#
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path
from typing import Any, Dict, Optional

from fm_tools.basic_config import BASE_DIR
from fm_tools.competition_participation import CompetitionParticipation
from fm_tools.exceptions import (
    MissingKeysException,
)
from fm_tools.tool_info_module import ToolInfoModule


class FmTool:
    """Class representing one FM-Tool from a YAML file and providing access to the data of the tool.

    fm_tool = FmTool(config)

    config: Dictionary that holds the content of one YAML file for an FM-Tool.

    """

    def __init__(
        self,
        config: Dict[str, Any],
    ):
        self._config = config
        self._check_fm_data_integrity()

    @staticmethod
    def from_tool_identifier(tool_id: str, base_dir: Optional[Path] = None):
        """
        Load the fm-data file with the given tool_id from the given base directory.

        Raises FileNotFoundError if the no file tool_id.yml exists in the base directory.
        """
        base_dir = base_dir or BASE_DIR

        candidates = Path(base_dir).glob(f"**/{tool_id}.yml")
        candidate = None
        try:
            candidate = next(candidates)
        except StopIteration:
            raise FileNotFoundError(f"No file '{tool_id}.yml' found in '{base_dir}' or its subdirectories.") from None

        try:
            next(candidates)
            raise ValueError(f"Multiple files '{tool_id}.yml' found in '{base_dir}' or its subdirectories.")
        except StopIteration:
            pass

        return FmTool.from_file(candidate)

    @staticmethod
    def from_file(file: Path):
        """
        Load the fm-data file from the given path.
        """
        import yaml

        with open(file, "r") as stream:
            config = yaml.safe_load(stream)

        return FmTool(config)

    def get_toolinfo_module(self) -> ToolInfoModule:
        if not hasattr(self, "_tool_info"):
            self._tool_info = ToolInfoModule(self._config["benchexec_toolinfo_module"])
        return self._tool_info

    def _check_fm_data_integrity(self):
        # check if the essential tags are present.
        # Essentiality of tags can be defined in a schema.
        essential_tags = {
            "benchexec_toolinfo_module",
            "name",
            "versions",
        }
        diff = essential_tags - self._config.keys()
        if diff:
            raise MissingKeysException(diff)

    @property
    def competition_participations(self) -> CompetitionParticipation:
        return CompetitionParticipation(self)

    def get(self, key: str, default: Any = None) -> Any:
        return self._config.get(key, default)

    def __getattr__(self, name: str) -> Any:
        """
        Pass on unknown attribute calls to return the key of the _config.
        """
        if name in {"__getstate__", "__setstate__"}:
            return object.__getattr__(self, name)  # type: ignore

        if name in self._config:
            return self._config[name]
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")
