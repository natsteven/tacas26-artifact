# This file is part of lib-fm-tools, a library for interacting with FM-Tools files:
# https://gitlab.com/sosy-lab/benchmarking/fm-tools
#
# SPDX-FileCopyrightText: 2024 Dirk Beyer <https://www.sosy-lab.org>
#
# SPDX-License-Identifier: Apache-2.0

import shutil
from pathlib import Path

import pytest
import requests
import yaml

import fm_tools.exceptions
from fm_tools.download import DownloadDelegate
from fm_tools.fmtool import FmTool
from fm_tools.fmtoolversion import FmToolVersion

YAML = """
name: Goblint
input_languages:
  - C
project_url: https://goblint.in.tum.de/
repository_url: https://github.com/goblint/analyzer
spdx_license_identifier: MIT
benchexec_toolinfo_module: "https://gitlab.com/sosy-lab/software/benchexec/-/raw/main/benchexec/tools/goblint.py"
fmtools_format_version: "2.0"
fmtools_entry_maintainers:
  - sim642

maintainers:
  - name: Simmo Saan
    institution: University of Tartu
    country: Estonia
    url: https://sim642.eu/
  - name: Michael Schwarz
    institution: Technische Universität München
    country: Germany
    url: https://www.cs.cit.tum.de/en/pl/personen/michael-schwarz/

versions:
  - version: "svcomp24"
    doi: 10.5281/zenodo.10202867
    benchexec_toolinfo_options: ["--conf", "conf/svcomp24.json"]
    required_ubuntu_packages: []
  - version: "goblint-redirecting-doi"
    doi: 10.5281/zenodo.10061261
  - version: "non-zenodo-doi"
    doi: 10.1145/zenodo.10202867
  - version: "non-existing-doi"
    doi: 10.5281/zenodo.10061261x
  - version: "urban-landscapes-several-files"
    doi: 10.5281/zenodo.14403152
  - version: "cousot-pdf-file"
    doi: 10.5281/zenodo.14173478
"""


def teardown_module():
    target = Path(__file__).parent / "output"
    if target.exists():
        shutil.rmtree(target)


def test_download_with_httpx():
    config = yaml.safe_load(YAML)
    fm_tool_version = FmToolVersion(FmTool(config), "svcomp24")
    target = Path(__file__).parent / "output" / "goblint-svcomp24"
    fm_tool_version.download_and_install_into(target)


def test_download_with_httpx_redirecting_doi():
    config = yaml.safe_load(YAML)
    fm_tool_version = FmToolVersion(FmTool(config), "goblint-redirecting-doi")
    target = Path(__file__).parent / "output" / "goblint-svcomp24.zip"
    with pytest.raises(fm_tools.exceptions.UnsupportedDOIException):
        fm_tool_version.download_into(target)


def test_download_with_httpx_non_zenodo_doi():
    config = yaml.safe_load(YAML)
    fm_tool_version = FmToolVersion(config, "non-zenodo-doi")
    target = Path(__file__).parent / "output" / "goblint-svcomp24.zip"
    with pytest.raises(AssertionError):
        fm_tool_version.download_into(target)


def test_download_with_httpx_non_existing_doi():
    config = yaml.safe_load(YAML)
    fm_tool_version = FmToolVersion(config, "non-existing-doi")
    target = Path(__file__).parent / "output" / "goblint-svcomp24.zip"
    with pytest.raises(fm_tools.exceptions.UnsupportedDOIException):
        fm_tool_version.download_into(target)


def test_download_with_httpx_target_not_a_file():
    config = yaml.safe_load(YAML)
    fm_tool_version = FmToolVersion(FmTool(config), "svcomp24")
    target = Path(__file__).parent
    with pytest.raises(FileExistsError):
        fm_tool_version.download_into(target)


def test_download_with_httpx_several_files():
    config = yaml.safe_load(YAML)
    fm_tool_version = FmToolVersion(FmTool(config), "urban-landscapes-several-files")
    target = Path(__file__).parent / "output" / "goblint-svcomp24.zip"
    with pytest.raises(fm_tools.exceptions.DownloadUnsuccessfulException):
        fm_tool_version.download_into(target)


def test_download_with_httpx_pdf_file():
    config = yaml.safe_load(YAML)
    fm_tool_version = FmToolVersion(FmTool(config), "cousot-pdf-file")
    target = Path(__file__).parent / "output" / "goblint-svcomp24.zip"
    with pytest.raises(fm_tools.exceptions.DownloadUnsuccessfulException):
        fm_tool_version.download_into(target)


def test_download_with_requests():
    config = yaml.safe_load(YAML)
    fm_tool_version = FmToolVersion(FmTool(config), "svcomp24")
    target = Path(__file__).parent / "output" / "goblint-svcomp24"
    fm_tool_version.download_and_install_into(target, delegate=DownloadDelegate(requests.Session()))  # type: ignore


def test_checksum():
    config = yaml.safe_load(YAML)
    fm_tool_version = FmToolVersion(FmTool(config), "svcomp24")
    chksum = fm_tool_version.get_archive_location().resolve().checksum
    assert chksum == "17c0415ae72561127bfd8f33dd51ed50"


if __name__ == "__main__":
    test_download_with_httpx()
