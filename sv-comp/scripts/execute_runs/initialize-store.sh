#!/bin/bash

# This file is part of the competition environment.
#
# SPDX-FileCopyrightText: 2011-2020 Dirk Beyer <https://www.sosy-lab.org>
#
# SPDX-License-Identifier: Apache-2.0

set -euo pipefail

# This script gets two parameters: log directory and witness name
LOG_DIR=$1
WITNESSTARGETS=$2
ROOT_DIR=$(realpath "$(dirname "$0")/../..")
SCRIPTS_DIR=$(dirname "$0")
HASHES_BASENAME="fileHashes.json"

if [[ "$LOG_DIR" == "" || "$WITNESSTARGETS" == "" ]]; then
  echo "Usage: $0 <log directory> <witness name>"
  exit 1
fi

# Create hashes map for programs
"$SCRIPTS_DIR"/create-hashes.py \
  -o "${LOG_DIR%.files}.$HASHES_BASENAME" \
  --root-dir "$ROOT_DIR" \
  "$ROOT_DIR"/sv-benchmarks/c

# Attention, there are double quotes around the value of $WITNESSTARGETS: remove them.
for WITNESSTARGET in ${WITNESSTARGETS//\"/}; do
  # Make sure that names of witnesses are always the same
  "$SCRIPTS_DIR"/create-uniform-witness-structure.py \
    --copy-to-files-dir "$WITNESSTARGET" \
    "$LOG_DIR"

  # Create hashes map for witnesses/test-suites
  "$SCRIPTS_DIR"/create-hashes.py \
    -o "${LOG_DIR%.files}.$HASHES_BASENAME" \
    --root-dir "$ROOT_DIR" \
    "$LOG_DIR" \
    --glob "$WITNESSTARGET"
done
