# This file is part of lib-fm-tools, a library for interacting with FM-Tools files:
# https://gitlab.com/sosy-lab/benchmarking/fm-tools
#
# SPDX-FileCopyrightText: 2024 Dirk Beyer <https://www.sosy-lab.org>
#
# SPDX-License-Identifier: Apache-2.0

from contextlib import contextmanager
from pathlib import Path
from typing import IO, TYPE_CHECKING, Dict, Iterable, Iterator, cast

from fm_tools.exceptions import DownloadUnsuccessfulException
from fm_tools.files import write_file_from_iterator

from .fmtypes import RequestsResponse, RequestsSession, Response, Session

if TYPE_CHECKING:
    import httpx

    from .fmtool import FmTool

DOWNLOAD_CHUNK_SIZE = 4096


class DownloadDelegate:
    def __init__(self, session: Session | None = None):
        self.session = session

        if self.session is None:
            import httpx  # type: ignore

            self.session = httpx.Client(http2=True)

    @contextmanager
    def stream(self, url: str, headers: Dict[str, str], follow_redirects=False, timeout=30):
        try:
            self.session = cast("httpx.Client", self.session)
            with self.session.stream(
                "GET",
                url,
                headers=headers,
                follow_redirects=follow_redirects,
                timeout=timeout,
            ) as response:
                yield response
        except TypeError:
            self.session = cast(RequestsSession, self.session)
            response = self.session.get(
                url,
                headers=headers,
                allow_redirects=follow_redirects,
                timeout=timeout,
                stream=True,
            )
            yield response
        finally:
            response.close()

    def get(
        self,
        url: str,
        headers: Dict[str, str],
        follow_redirects=False,
        timeout=30,
    ) -> Response:
        """
        This method wraps both httpx and requests get methods.
        The streaming syntax is different in httpx and requests.
        `.stream` also exists in requests Sessions but it is a boolean,
        thus raising a TypeError if requests is used as `session`.
        Similarly, `follow_redirects` is a known keyword in httpx but
        raises a TypeError in requests.

        """

        try:
            self.session = cast("httpx.Client", self.session)
            return self.session.get(url, headers=headers, follow_redirects=follow_redirects, timeout=timeout)
        except TypeError:
            self.session = cast(RequestsSession, self.session)
            return self.session.get(
                url,
                headers=headers,
                allow_redirects=follow_redirects,
                timeout=timeout,
                stream=False,
            )

    def head(self, url: str, headers: Dict[str, str], follow_redirects=False, timeout=30) -> Response:
        try:
            self.session = cast("httpx.Client", self.session)
            return self.session.head(url, headers=headers, follow_redirects=follow_redirects, timeout=timeout)
        except TypeError:
            self.session = cast(RequestsSession, self.session)
            return self.session.head(url, headers=headers, allow_redirects=follow_redirects, timeout=timeout)

    def __hash__(self):
        return hash(self.session)


def response_iterator(response: Response) -> Iterator[bytes]:
    try:
        # httpx
        response = cast("httpx.Response", response)
        return response.iter_bytes(chunk_size=DOWNLOAD_CHUNK_SIZE)
    except AttributeError:
        # requests
        response = cast(RequestsResponse, response)
        return cast(Iterator[bytes], response.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE, decode_unicode=False))


def response_tqdm_iterator(response: Response) -> "Iterable[bytes]":
    from tqdm import tqdm

    total = int(response.headers.get("content-length", 0))
    return tqdm(
        response_iterator(response),
        total=int(total / DOWNLOAD_CHUNK_SIZE),
        unit_scale=int(DOWNLOAD_CHUNK_SIZE / 1024),
        unit="KiB",
    )


def is_download_qualified_url(url: str) -> bool:
    return url.startswith("http://") or url.startswith("https://")


def _download_into_file(url: str, target: IO[bytes], delegate: DownloadDelegate, timeout=10) -> None:
    headers = {}
    response = delegate.get(url, headers=headers, follow_redirects=True, timeout=timeout)
    if response.content is not None:
        target.write(response.content)


def download_into(
    fm_data: "FmTool",
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

    if not target.parent.exists():
        target.parent.mkdir(parents=True)

    if target.exists() and not target.is_file():
        raise FileExistsError(f"The target path {target} exists and is not a file.")

    headers = {}
    archive_location = fm_data.get_archive_location().resolve()

    follow_redirects = False
    if "github.com" in archive_location.resolved:
        follow_redirects = True
    # We must never use redirects to ensure to never accidentally use a redirect DOI for the 'latest version'.
    with delegate.stream(
        archive_location.resolved,
        follow_redirects=follow_redirects,
        headers=headers,
        timeout=60,
    ) as response:
        if response.status_code != 200:
            raise DownloadUnsuccessfulException(
                f"Could not download contents from: {str(archive_location.resolved)}. "
                f"Server returned the code: {response.status_code}"
            )

        response_iter = response_tqdm_iterator(response) if show_loading_bar else response_iterator(response)
        expected_checksum = archive_location.checksum if not archive_location.checksum_is_etag else None
        write_file_from_iterator(target, response_iter, expected_checksum=expected_checksum)
