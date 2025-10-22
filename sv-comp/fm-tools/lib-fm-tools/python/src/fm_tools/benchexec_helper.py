# This file is part of lib-fm-tools, a library for interacting with FM-Tools files:
# https://gitlab.com/sosy-lab/benchmarking/fm-tools
#
# SPDX-FileCopyrightText: 2024 Dirk Beyer <https://www.sosy-lab.org>
#
# SPDX-License-Identifier: Apache-2.0
from enum import Enum


class DataModel(Enum):
    """
    Enum representing the data model of the tool.
    """

    LP64 = "LP64"
    ILP32 = "ILP32"

    def __str__(self):
        return self.value


def load_tool_info(tool_name: str):
    """
    Adaptation of the load_tool_info function from benchexec.model. It does not
    call sys.exit() on error but raises an exception instead.
    Load the tool-info class.
    @param tool_name: The name of the tool-info module.
    Either a full Python package name or a name within the benchexec.tools package.
    @return: A tuple of the full name of the used tool-info module
        and an instance of the tool-info class.
    @raise AttributeError:
        If the tool-info module does not contain a class named "Tool".
    @raise TypeError:
        If the tool-info module could not be adapted to the current version.
    @raise ImportError: If the tool-info module could not be located in the PYTHONPATH.
    """
    from benchexec import tooladapter

    tool_module = tool_name if "." in tool_name else f"benchexec.tools.{tool_name}"
    print("tool_module: ", tool_module)
    try:
        tool = __import__(tool_module, fromlist=["Tool"]).Tool()
        tool = tooladapter.adapt_to_current_version(tool)
    except AttributeError as ae:
        raise AttributeError(f'Unsupported tool "{tool_name}" specified, class "Tool" is missing: {ae}') from ae
    except TypeError as te:
        TypeError(f'Unsupported tool "{tool_name}" specified. TypeError: {te}')
    assert isinstance(tool, tooladapter.CURRENT_BASETOOL)
    return tool_module, tool
