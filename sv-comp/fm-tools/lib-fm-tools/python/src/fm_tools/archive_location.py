# This file is part of lib-fm-tools, a library for interacting with FM-Tools files:
# https://gitlab.com/sosy-lab/benchmarking/fm-tools
#
# SPDX-FileCopyrightText: 2024 Dirk Beyer <https://www.sosy-lab.org>
#
# SPDX-License-Identifier: Apache-2.0

from dataclasses import dataclass
from typing import Optional

from fm_tools.download import DownloadDelegate
from fm_tools.zenodo import (
    get_archive_url_from_zenodo_doi,
)


@dataclass(frozen=True)
class ArchiveLocation:
    raw: str
    resolved: Optional[str] = None
    checksum: Optional[str] = None
    checksum_is_etag: bool = False

    def resolve(self, download_delegate=None) -> "ArchiveLocation":
        if self.resolved is not None and self.checksum is not None:
            return self

        delegate = download_delegate or DownloadDelegate()

        if self.resolved is not None:
            # If we already have a resolved URL, but no checksum, we can try to resolve the checksum
            #  with a HEAD request checking for the etag
            follow_redirects = "github.com" in self.resolved

            headers = delegate.head(
                self.resolved,
                headers={"Accept": "*/*", "User-Agent": "fm-tools/1.0"},
                follow_redirects=follow_redirects,
            ).headers
            checksum = headers.get("etag", None)
            return ArchiveLocation(self.raw, self.resolved, checksum, checksum_is_etag=True)

        resolved, checksum = get_archive_url_from_zenodo_doi(self.raw, delegate)
        return ArchiveLocation(self.raw, resolved, checksum)
