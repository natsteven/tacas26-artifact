#!/usr/bin/env python3

# This file is part of fm-tools
# https://gitlab.com/sosy-lab/benchmarking/fm-tools
# SPDX-FileCopyrightText: 2024 Dirk Beyer <https://www.sosy-lab.org>
#
# SPDX-License-Identifier: Apache-2.0


import argparse
import sys
from pathlib import Path
from typing import Iterable

import _ciutil as util


def parse_args(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base-directory",
        default=".",
        help="base directory to use for CODEOWNERS file",
        type=Path,
    )
    parser.add_argument(
        "fm_data",
        help="Data directory of Formal-Methods Tools",
        type=Path,
    )
    args = parser.parse_args(argv)
    missing_files = [f for f in [args.fm_data, args.base_directory] if not f.exists()]
    if missing_files:
        raise ValueError(
            f"File(s) do not exist: {','.join([str(f) for f in missing_files])}"
        )
    return args


def _tool_to_gitlab_handle(fm_data: Path) -> Iterable[tuple[str, str]]:
    fm_files = fm_data.glob("*.yml")
    for fm_file in fm_files:
        try:
            yield fm_file, util.parse_yaml(fm_file)["fmtools_entry_maintainers"]
        except KeyError:
            continue


def create_entries(args):
    for archive, gitlab_handles in _tool_to_gitlab_handle(args.fm_data):
        gitlab_handles = " ".join(f"@{handle}" for handle in sorted(gitlab_handles))
        relevant_files = [
            f.relative_to(args.base_directory)
            for f in args.base_directory.glob(f"**/{archive}")
        ]
        if not relevant_files:
            print(
                f"No files found for {args.base_directory}/**/{archive}",
                file=sys.stderr,
            )
        for f in relevant_files:
            yield f"{f} {gitlab_handles}"


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    args = parse_args(argv)

    print("[Participants]")
    print("CODEOWNERS @dbeyer")
    print("data/schema.yml @dbeyer")
    for entry in sorted(create_entries(args)):
        print(entry)


if __name__ == "__main__":
    sys.exit(main())
