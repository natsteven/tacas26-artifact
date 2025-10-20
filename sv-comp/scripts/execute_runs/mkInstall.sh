#!/bin/bash

# This file is part of the competition environment.
#
# SPDX-FileCopyrightText: 2011-2020 Dirk Beyer <https://www.sosy-lab.org>
#
# SPDX-License-Identifier: Apache-2.0

set -euo pipefail

# @title Install Tool Archive
# @description Unzips and checks the structure of tool archive.

TOOL_ARCHIVE="$(realpath "$(dirname "$0")/../../${1:-}")"
TOOL_DIR="${2:-}"
YEAR=$(yq --raw-output '.year' benchmark-defs/category-structure.yml)

if [[ -z "$TOOL_ARCHIVE" || -z "$TOOL_DIR" ]]; then
  echo "Usage: $0 <tool> <install directory>"
  exit 1
fi

if [[ ! -e "$TOOL_ARCHIVE" ]]; then
  echo "Tool archive $TOOL_ARCHIVE does not exist."
  exit 1
fi

if [[ ! -e "$TOOL_DIR" ]]; then
  echo "Tool directory $TOOL_DIR does not exist."
  exit 1
fi

# Unzip
echo "Installing $TOOL_ARCHIVE ..."
cd "$TOOL_DIR" || exit
unzip "$TOOL_ARCHIVE"
# Check structure
if [[ $(find . -mindepth 1 -maxdepth 1 | wc -l) == 1 ]]; then
  echo "Info: One folder found in archive."
  DIR="$(find . -mindepth 1 -maxdepth 1)"
  mv "${DIR}" "${DIR}__COMP"
  # Move all files and directories from subfolder into this folder.
  find "${DIR}__COMP"/ -mindepth 1 -maxdepth 1 -exec mv {} ./ \;
  rmdir "${DIR}__COMP"
else
  echo "Error: Archive does not contain exactly one folder."
  exit 1
fi

