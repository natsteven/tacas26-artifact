# This file is part of lib-fm-tools, a library for interacting with FM-Tools files:
# https://gitlab.com/sosy-lab/benchmarking/fm-tools
#
# SPDX-FileCopyrightText: 2024 Dirk Beyer <https://www.sosy-lab.org>
#
# SPDX-License-Identifier: Apache-2.0

from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional, Sequence

from benchexec.tools.template import BaseTool2

from fm_tools.exceptions import ToolInfoNotResolvedError

from .benchexec_helper import DataModel, load_tool_info

if TYPE_CHECKING:
    from benchexec.tools.template import BaseTool2

    from .fmtool import FmTool
    from .fmtoolversion import FmToolVersion


@dataclass(frozen=True)
class Limits:
    """
    Dataclass representing the desired limits for the execution of a tool.
    The limits *are not enforced nor guaranteed*. They merely serve as optional
    data that is used while generating the command line for a tool.

    """

    cpu_time: Optional[int] = None
    wall_time: Optional[int] = None
    memory: Optional[int] = None
    cores: Optional[int] = None

    def as_benchexec_limits(self) -> "BaseTool2.ResourceLimits":
        from benchexec.tools.template import BaseTool2

        return BaseTool2.ResourceLimits(
            cputime=self.cpu_time,
            cputime_hard=self.cpu_time,
            walltime=self.wall_time,
            memory=self.memory,
            cpu_cores=self.cores,
        )


@cache
def get_tool_info(fm_tool: "FmTool") -> "BaseTool2":
    try:
        _, tool = load_tool_info(str(fm_tool.get_toolinfo_module()))
        return tool
    except (ImportError, ModuleNotFoundError) as e:
        raise ToolInfoNotResolvedError(
            "Could not load toolinfo module. "
            "Make sure it is available in the sys.path, e.g., by calling the make_available() method. "
            f"Original error was: {repr(e)}"
        ) from e


def get_executable_path(fm_data: "FmTool", tool_dir: Path):
    locator = BaseTool2.ToolLocator(tool_directory=tool_dir)
    tool = get_tool_info(fm_data)
    return tool.executable(locator)


def command_line_run(
    fm_tool_version: "FmToolVersion",
    tool_dir: Path,
    input_files: Sequence[Path],
    working_dir: Optional[Path] = None,
    property: Optional[Path] = None,  # noqa: A002
    data_model: Optional[DataModel] = None,
    options: Optional[List[str]] = None,
    add_options_from_fm_data: bool = False,
    limits: Optional[Limits] = None,
) -> List[str]:
    options = options or []

    if add_options_from_fm_data:
        options = fm_tool_version.get_options() + options

    if not fm_tool_version.get_toolinfo_module():
        raise ToolInfoNotResolvedError("The toolinfo module must be resolved before generating the command line.")

    executable = get_executable_path(fm_tool_version, tool_dir)
    tool = get_tool_info(fm_tool_version)
    task_options = None

    if data_model:
        # There exist a utility ion benchexec for extracting the data model
        # the utility only continues if the language is set and is C
        task_options = {"data_model": data_model.value, "language": "C"}

    task = BaseTool2.Task.with_files(input_files, property_file=property, options=task_options)

    rlimits = limits.as_benchexec_limits() if limits else BaseTool2.ResourceLimits()

    return tool.cmdline(executable, options, task, rlimits)
