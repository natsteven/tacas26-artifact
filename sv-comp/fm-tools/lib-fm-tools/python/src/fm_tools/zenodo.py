# This file is part of lib-fm-tools, a library for interacting with FM-Tools files:
# https://gitlab.com/sosy-lab/benchmarking/fm-tools
#
# SPDX-FileCopyrightText: 2024 Dirk Beyer <https://www.sosy-lab.org>
#
# SPDX-License-Identifier: Apache-2.0

import json
from functools import lru_cache

from fm_tools.download import DownloadDelegate
from fm_tools.exceptions import DownloadUnsuccessfulException, UnsupportedDOIException

ZENODO_API_URL_BASE = "https://zenodo.org/api/records/"


@lru_cache(maxsize=128)
def get_metadata_from_zenodo_doi(doi, download_delegate=None):
    if download_delegate is None:
        download_delegate = DownloadDelegate()

    assert doi.startswith("10.5281/zenodo.")
    zenodo_record_id = doi.replace("10.5281/zenodo.", "")
    response = download_delegate.get(
        ZENODO_API_URL_BASE + zenodo_record_id,
        headers={"Accept": "application/json"},
    )

    if response.status_code != 200:
        raise UnsupportedDOIException(
            f"Failed to get the Zenodo record. "
            f"Status code: {response.status_code}, "
            f"URL: {response.url}. "
            "The DOI must point to a specific version and not redirect to the latest version."
        )

    return json.loads(response.content)


# Check meta data and return expected checksum for given JSON record
def get_checksum(file_info):
    if not file_info["checksum"].startswith("md5:"):
        raise DownloadUnsuccessfulException("Checksum is not calculated with md5.")
    if not file_info["key"].endswith(".zip"):
        raise DownloadUnsuccessfulException("File is not a ZIP file.")
    checksum = file_info["checksum"][len("md5:") :]
    if not checksum:
        raise DownloadUnsuccessfulException("No checksum found.")
    return checksum


def get_archive_url_from_zenodo_doi(doi, download_delegate=None):
    if download_delegate is None:
        download_delegate = DownloadDelegate()

    data = get_metadata_from_zenodo_doi(doi, download_delegate)

    if len(data["files"]) > 1:
        raise DownloadUnsuccessfulException(
            "There are more than one file in the Zenodo record, but only one is allowed."
        )

    # the archive URL is the first file's self link
    download_url = data["files"][0]["links"]["self"]
    checksum = get_checksum(data["files"][0])
    return download_url, checksum
