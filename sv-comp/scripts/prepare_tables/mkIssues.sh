#!/bin/bash

# Generate list of issues to initialize the discussion issues per tool in the archives repository.

set -euo pipefail

COMPETITION=$(yq --raw-output '.competition' benchmark-defs/category-structure.yml)
YEAR=$(yq --raw-output '.year' benchmark-defs/category-structure.yml)

echo "title	description	tracks	jury members";
yq --raw-output --arg comp "$COMPETITION $YEAR" -s '
        # filter for current competition
        map(select(.competition_participations // [] | any(.competition == $comp))) |
        # sorting by name
        sort_by(.name | ascii_downcase) |
        # prepare output for each tool
        map(
            # create variable for tracks
            ([.competition_participations [] | select(.competition == $comp) .track] | join(", ") ) as $tracks |
            # create variable for jury members
            ([.competition_participations [] | select(.competition == $comp) .jury_member] | map(if .url then "[\(.name)](\(.url))" else .name end) | unique | join(", ")) as $jury_members |
            # final output as string with all the info
            "\(.name)\t\"Project URL: \(.project_url // "none")\n\nParticipating in tracks: \($tracks)\n\nJury members: \($jury_members)\""
        ) | join("\n")
    ' fm-tools/data/*.yml
