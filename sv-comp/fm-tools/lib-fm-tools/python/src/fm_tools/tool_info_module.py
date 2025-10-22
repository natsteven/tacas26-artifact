# This file is part of lib-fm-tools, a library for interacting with FM-Tools files:
# https://gitlab.com/sosy-lab/benchmarking/fm-tools
#
# SPDX-FileCopyrightText: 2024 Dirk Beyer <https://www.sosy-lab.org>
#
# SPDX-License-Identifier: Apache-2.0

import shutil
import sys
from pathlib import Path
from tempfile import mkdtemp
from typing import Optional

from fm_tools.download import (
    DownloadDelegate,
    _download_into_file,
    is_download_qualified_url,
)


class ToolInfoModule:
    """
    Tool-info-modules in fm-tools have one of three forms:
        - a URL to a python file
        - The fully qualified name of a python module, i.e. benchexec.tools.<toolname>
        - The name of a tool in the benchexec.tools namespace, i.e. <toolname>[.py]
    benchexec supports the latter two. In the first case, the ToolInfoModule must be downloaded beforehand.
    """

    raw: str
    resolved: Optional[str] = None
    _propagate_delete = False
    _target_location: Optional[Path] = None

    def __init__(self, raw: str):
        self.raw = raw

    def _trivially_resolved(self):
        if self.resolved is not None:
            return self

        if not is_download_qualified_url(self.raw):
            # The tool-info-module is already a valid module name
            if self.raw.endswith(".py"):
                self.resolved = self.raw.rpartition(".")[0]
            else:
                self.resolved = self.raw
            return self

        return None

    def resolve(self, target_dir=None, delegate=None) -> "ToolInfoModule":
        """
        Download the tool-info-module if necessary.
        If target_dir is not used, the module is downloaded into a temporary file.
        """
        delegate = delegate or DownloadDelegate()

        if self._trivially_resolved() is not None:
            return self

        if target_dir is None:
            target_dir = Path(mkdtemp(prefix="toolinfo_"))
            self._propagate_delete = True

        if target_dir.is_file():
            raise FileExistsError("The target directory is a file.")

        target_dir.mkdir(parents=True, exist_ok=True)
        file_name = self.raw.rpartition("/")[-1]
        self._target_location = target = target_dir / file_name
        with target.open("wb") as f:
            _download_into_file(self.raw, f, delegate=delegate)

        self.resolved = "." + target.stem
        return self

    def make_available(self):
        """
        Make the resolved tool-info-module available for import.
        If necessary the tool-info-module is downloaded into a temporary file.
        """
        self.resolve()
        if self._target_location:
            sys.path.insert(0, str(self._target_location.parent))

    def __str__(self):
        return self.resolved or self.raw

    def __del__(self):
        if self._propagate_delete and self._target_location is not None:
            shutil.rmtree(self._target_location.parent)

    def __bool__(self):
        if self._trivially_resolved() is not None:
            return True
        return self.resolved is None
