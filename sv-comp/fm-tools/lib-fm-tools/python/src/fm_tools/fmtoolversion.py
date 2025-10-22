# This file is part of lib-fm-tools, a library for interacting with FM-Tools files:
# https://gitlab.com/sosy-lab/benchmarking/fm-tools
#
# SPDX-FileCopyrightText: 2024 Dirk Beyer <https://www.sosy-lab.org>
#
# SPDX-License-Identifier: Apache-2.0

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from tempfile import (
    NamedTemporaryFile,
)
from typing import TYPE_CHECKING, Any, List, Optional, Sequence, Tuple, Union, cast

import werkzeug

from fm_tools.archive_location import ArchiveLocation
from fm_tools.benchexec_helper import DataModel
from fm_tools.download import (
    DownloadDelegate,
    download_into,
)
from fm_tools.exceptions import (
    EmptyVersionException,
    InvalidDataException,
    VersionConflictException,
)
from fm_tools.files import unzip
from fm_tools.fmtool import FmTool
from fm_tools.run import Limits, command_line_run, get_executable_path

if TYPE_CHECKING:
    VersionLike = Union[str, Tuple[str, ...], Tuple[int, ...], int]  # For type hinting purposes


@dataclass(frozen=True)
class FmImageConfig:
    base_images: Tuple[str, ...]
    full_images: Tuple[str, ...]
    required_packages: Tuple[str, ...]

    def with_fallback(self, image: str | None):
        """
        Returns a new FmImageConfig with the given image as the base image if the base image is not set.
        """

        if image is None:
            return self

        return FmImageConfig(
            self.base_images or (image,),
            self.full_images,
            self.required_packages,
        )


class FmToolVersion(FmTool):
    """Class representing one version of an FM-Tool and for downloading, installing, and starting a tool."""

    _config: dict[str, Any]
    _version_id: str

    def __init__(
        self,
        data: Union[FmTool, dict[str, Any]],
        version_id: "VersionLike | None",
    ):
        """
        :param data: The FmTool or a dictionary containing the configuration of the tool.
        :param version_id: The version ID of the tool. If None, first version appearing in versions is taken.
        :raises VersionConflictException: If the version ID is not found in the tool's versions.
        :raises EmptyVersionException: If the tool does not have any versions.
        :raises InvalidDataException: If the tool's data is invalid, e.g.,
                                      if the URL and DOI are both missing or both present.
        """
        try:
            data = cast(FmTool, data)
            self._config = deepcopy(data._config)
        except AttributeError:
            # If data is a dict, we can use it directly.
            self._config = cast(dict[str, Any], data)
            self._check_fm_data_integrity()

        # In some cases a version like 2.1 is interpreted as float 2.1 by the yaml parser.
        # To keep the version as string, we convert it to string here.
        self._version_id = self._prepare_version_id_or_get_first_version_id(version_id)
        self._tool_name_with_version = self._safe_name_from_config()
        self._version_config = self._find_version_config()
        self._options = []
        if "benchexec_toolinfo_options" in self._version_config:
            self._options = self._version_config["benchexec_toolinfo_options"]
        self._archive_location = self._prepare_archive_location()

    def _prepare_version_id_or_get_first_version_id(self, version_id: "VersionLike | None") -> str:
        if version_id is None:
            # If no version ID is provided, use the first version from the config.
            versions = self._config.get("versions", [])
            if len(versions) == 0:
                raise EmptyVersionException("Tool does not have any versions.")
            return str(versions[0]["version"])

        if isinstance(version_id, (tuple, list)):
            # If version_id is a tuple or list, convert it to a string.
            version_id = ".".join(str(v) for v in version_id)

        return str(version_id)

    def _safe_name_from_config(self) -> str:
        return werkzeug.utils.secure_filename(f"{self.name}-{self._version_id}")

    def _find_version_config(self):
        versions = self.versions
        if versions is None:
            versions = []
        tool_configs = [config for config in versions if str(config["version"]) == self._version_id]

        if len(tool_configs) < 1:
            raise VersionConflictException(f"Version '{self.get_version_id}' not found for tool '{self.name}'.")
        if len(tool_configs) > 1:
            raise VersionConflictException(
                f"There are multiple versions '{self._version_id}' in the YAML file for tool '{self.name}'."
            )
        version_config = tool_configs[0]

        if version_config is None:
            raise EmptyVersionException(f"Tool '{self.name}' does not have version '{self._version_id}'.")
        return version_config

    def _check_tool_sources(self):
        has_doi = "doi" in self._version_config
        has_url = "url" in self._version_config

        if not (has_url or has_doi):
            raise InvalidDataException("URL and DOI of tool version missing.")
        if has_url and has_doi:
            raise InvalidDataException("Two tool archives provided (one by a URL, one by a DOI).")

        return has_url, has_doi

    def _prepare_archive_location(self) -> ArchiveLocation:
        has_url, has_doi = self._check_tool_sources()

        if has_doi:
            doi = self._version_config["doi"]
            return ArchiveLocation(doi)

        if has_url:
            return ArchiveLocation(self._version_config["url"], self._version_config["url"])

        raise AssertionError("This should never happen, as we checked for the presence of a URL or DOI.")

    def download_and_install_into(
        self,
        target_dir: Path,
        delegate: DownloadDelegate | None = None,
        show_loading_bar: bool = True,
    ):
        """
        Downloads and installs the associated archive into `target_dir`.
        The `target_dir` must not be '/' or '/tmp' to avoid accidental deletion of the system.

        """
        delegate = delegate or DownloadDelegate()

        with NamedTemporaryFile("+wb", suffix=".zip", delete=True) as tmp:
            archive = Path(tmp.name)
            self.download_into(archive, delegate=delegate, show_loading_bar=show_loading_bar)
            return self.install_from(archive, target_dir)

    def download_into(
        self,
        target: Path,
        delegate: DownloadDelegate | None = None,
        show_loading_bar: bool = True,
    ) -> None:
        """
        Download the associated archive into the given target.
        The target must be a file.
        Rethrows potential exceptions from the session in the download delegate.

        :exception DownloadUnsuccessfulException: if the response code is not 200
        :return: the path to the downloaded archive
        """

        delegate = delegate or DownloadDelegate()

        download_into(self, target, delegate, show_loading_bar)

    def install_from(self, archive_dir: Path, target_dir: Path):
        return unzip(archive_dir, target_dir)

    # implement abstract methods
    def get_archive_location(self) -> ArchiveLocation:
        return self._archive_location

    def get_config(self) -> "dict[str, Any]":
        return self._config

    def get_version_id(self) -> str:
        return self._version_id

    def get_options(self) -> List[str]:
        return self._options

    def get_tool_name_with_version(self) -> str:
        return self._tool_name_with_version

    def _find_key(self, key, default):
        top_level = self._config.get(key, default)
        return self._version_config.get(key, top_level)

    def get_images(self) -> FmImageConfig:
        # Top level images
        base_images = tuple(self._find_key("base_container_images", tuple()))
        full_images = tuple(self._find_key("full_container_images", tuple()))
        required_packages = tuple(
            self._find_key("required_ubuntu_packages", self._find_key("required_packages", tuple()))
        )

        return FmImageConfig(base_images, full_images, required_packages)

    def command_line(
        self,
        tool_dir: Path,
        input_files: Optional[Sequence[Path]] = None,
        working_dir: Optional[Path] = None,
        property: Optional[Path] = None,
        data_model: Optional[DataModel] = None,
        options: Optional[List[str]] = None,
        add_options_from_fm_data: bool = False,
        limits: Optional[Limits] = None,
    ) -> List[str]:
        return command_line_run(
            self,
            tool_dir,
            input_files or [],
            working_dir,
            property,
            data_model,
            options,
            add_options_from_fm_data,
            limits,
        )

    def get_executable_path(self, tool_dir: Path) -> Path:
        return get_executable_path(self, tool_dir)
