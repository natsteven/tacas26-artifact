#!/usr/bin/env python3

# Check logos

# This file is part of FM-Tools.
# https://gitlab.com/sosy-lab/benchmarking/fm-tools
# SPDX-FileCopyrightText: 2025 Dirk Beyer <https://www.sosy-lab.org>
#
# SPDX-License-Identifier: Apache-2.0


from pathlib import Path
import re
import sys


def check_tool_id(tool_name: str) -> bool:
    if not re.fullmatch(r"[a-z0-9\-\+]+", tool_name):
        print(
            f"Error: Tool id '{tool_name}' should use only lower-case letters, digits, periods, pluses, and hyphens."
        )
        return False
    return True


def main():
    success = True

    for file in Path(".").glob("*.yml"):
        # Check that no '.yml' file is located in the root folder.
        print(f"Error: File '{file}' should not be located in the root folder.")
        success = False

    # Data
    for file in Path("data").glob("*"):
        # Check the tool id in file name
        success &= check_tool_id(file.stem)
        # Check that every data file has a name according to the conventions.
        if file.suffix != ".yml":
            print(
                f"Error: File '{file}' in folder 'data/' does not have the required file-name extension '.yml'."
            )
            success = False

    # Logos
    for file in Path("logos").glob("*.svg"):
        # Check the tool id in file name
        success &= check_tool_id(file.stem)
        # Check that a license file exists for every logo.
        license_file = Path(str(file) + ".license")
        if not license_file.is_file():
            print(
                f"Error: The required license file '{license_file}' is missing for logo file '{file}'."
            )
            success = False
        # Check that a file 'data/<tool>.yml' exists for every logo.
        tool_file = Path("data") / Path(file.stem).with_suffix(".yml")
        if not tool_file.is_file():
            print(
                f"Error: For logo file '{file}', the corresponding tool file '{tool_file}' does not exist."
            )
            success = False
    for file in Path("logos").glob("*.license"):
        # Check the tool id in file name
        success &= check_tool_id(Path(file.stem).stem)
        # Check that a logo file exists for every license.
        logo_file = Path(str(file).replace(".license", ""))
        if not logo_file.is_file():
            print(
                f"Error: For license file '{file}', the corresponding logo file '{logo_file}' does not exist."
            )
            success = False
    if not success:
        exit(1)


if __name__ == "__main__":
    sys.exit(main())
