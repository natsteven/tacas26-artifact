#!/bin/bash

# Enable exit on error
set -euo pipefail

COMPETITION="$1"
TOOL="$2"

FMTOOLS_DIR="$(dirname "$0")/.."

if [[ -z "$COMPETITION" || -z "$TOOL" ]]; then
  echo "Usage: $0 <competition> <tool>"
  echo "Example: $0 'SV-COMP 2024' 'cpachecker'"
  exit 1
fi

TRACKS=$(yq --raw-output "[.competition_participations [] | select(.competition == \"$COMPETITION\") | .track] | unique []" "$FMTOOLS_DIR/data/$TOOL.yml")
if [ -z "$TRACKS" ]; then
    echo "Tool '$TOOL' does not participate in '$COMPETITION'."
    exit
fi
echo "Tool '$TOOL' participates in tracks:"
echo "$TRACKS"

echo "$TRACKS" | while read -r TRACK; do
    echo
    echo "Checking tool '$TOOL' for competition '$COMPETITION' and track '$TRACK' ..."
    mkdir -p archives/cache

    echo
    echo "Downloading archive for '$TOOL' ..."
    "$FMTOOLS_DIR"/lib-fm-tools/python/src/fm_tools/update_archives.py \
        --fm-root "$(dirname "$0")"/../data/ \
        --archives-root archives/ \
        --competition "$COMPETITION" \
        --competition-track "$TRACK" \
        "$TOOL"

    echo
    echo "Checking archive for '$TOOL' for '$COMPETITION' and track '$TRACK' ..."
    "$FMTOOLS_DIR"/ci/check_archive.py \
        --archives-root archives/ \
        --competition "$COMPETITION" \
        --competition-track "$TRACK" \
        "$TOOL"
done