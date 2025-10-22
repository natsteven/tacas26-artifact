#!/usr/bin/env python3

# This file is part of lib-fm-tools, a library for interacting with FM-Tools files:
# https://gitlab.com/sosy-lab/benchmarking/fm-tools
#
# SPDX-FileCopyrightText: 2024 Dirk Beyer <https://www.sosy-lab.org>
#
# SPDX-License-Identifier: Apache-2.0


import contextlib
import logging
import os
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
import fm_tools.exceptions
from fm_tools.competition_participation import Competition, string_to_Competition
from fm_tools.fmtoolscatalog import FmToolsCatalog
from fm_tools.fmtoolversion import FmToolVersion

sys.path.append(str(Path(__file__).parent.parent.parent.parent.parent / "ci"))
import _ciutil as util


def update_archives(
    fm_root: Path,
    tool_id: str,
    archives_root: Path,
    competition_name: Competition,
    competition_year: int,
    competition_track: str,
):
    fmtools = FmToolsCatalog(fm_root)
    if tool_id not in fmtools:
        raise fm_tools.exceptions.DownloadUnsuccessfulException(f"Could not find tool '{tool_id}' in path '{fm_root}'.")
    tool_version_id = (
        fmtools[tool_id]
        .competition_participations.competition(competition_name, competition_year)[competition_track]
        .tool_version
    )
    tool_version = FmToolVersion(fmtools[tool_id], tool_version_id)
    doi = tool_version.get_archive_location().raw
    assert doi.startswith("10.5281/zenodo.")

    logging.info(f"Updating '{tool_id}' for track '{competition_track}' ({doi})")
    zenodo_id = doi.replace("10.5281/zenodo.", "")
    cache_path = archives_root / f"cache/{zenodo_id}.zip"
    tool_path = archives_root / f"{tool_id}-{util.get_track_for_filename(competition_track)}.zip"
    if not cache_path.is_file():
        tool_version.download_into(cache_path)
    if tool_path.absolute().is_symlink():
        real_path = tool_path.resolve()
        current_doi = os.path.basename(str(real_path)).replace(".zip", "")
        if current_doi == zenodo_id:
            logging.info(f"Archive with DOI {doi} already exists, skipping.")
            return
        with contextlib.suppress(FileNotFoundError):
            # A parallel running process has removed the link already. That's ok.
            tool_path.unlink()
            # Do not remove cached archive, because it might be used by other versions, or even other tools.
    with contextlib.suppress(FileExistsError):
        # A parallel running process has created the link already. That's ok.
        os.symlink(
            os.path.relpath(cache_path, start=archives_root),
            tool_path.absolute(),
        )


def parse_arguments():
    import argparse

    parser = argparse.ArgumentParser(description="Download an archive from Zenodo")
    parser.add_argument(
        "--fm-root",
        type=Path,
        help="Path to FM-Tools folder",
        default=Path(__file__).parent.parent.parent.parent.parent / "data",
    )
    parser.add_argument(
        "--archives-root",
        type=Path,
        help="Path to archives folder",
        default=Path(__file__).parent.parent.parent.parent.parent.parent / "archives",
    )
    parser.add_argument(
        "--competition",
        type=str,
        help="Competition (e.g., 'Test-Comp 2025')",
        required=True,
    )
    parser.add_argument(
        "--competition-track",
        type=str,
        help="Competition track (e.g., 'Test Generation')",
        required=True,
    )
    parser.add_argument(
        "tool",
        nargs=1,
        type=str,
        default="",
        help="Tool to download",
    )
    return parser.parse_args()


def main():
    logging.basicConfig(format="%(levelname)s:%(message)s", level=logging.INFO)
    args = parse_arguments()
    competition_name, competition_year = args.competition.split(" ")
    update_archives(
        args.fm_root,
        args.tool[0],
        args.archives_root,
        string_to_Competition(competition_name),
        int(competition_year),
        args.competition_track,
    )


if __name__ == "__main__":
    main()
