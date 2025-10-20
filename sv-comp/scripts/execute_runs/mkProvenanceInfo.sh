#!/bin/bash

# This file is part of the competition environment.
#
# SPDX-FileCopyrightText: 2011-2020 Dirk Beyer <https://www.sosy-lab.org>
#
# SPDX-License-Identifier: Apache-2.0

set -euo pipefail

# @title Write provenance information to config file
# @description Prepare Phase: write info about competition and components used to file

DIR="$(dirname "$0")"
source "$DIR"/../configure.sh

TOOL_ARCHIVE=$1
GIT_REPOS="fm-tools sv-benchmarks benchexec scripts ."

if [ -z "$TOOL_ARCHIVE" ]; then
  echo "Error: No verifier specified."
  exit 1
fi

if [[ ! -e "$TOOL_ARCHIVE" ]]; then
  echo "Tool archive $TOOL_ARCHIVE not found."
  exit 1
fi

echo ""
echo "Provenance information:"
echo "Benchmark executed"
echo "for $COMPETITIONNAME $YEAR, https://$TARGETSERVER.sosy-lab.org/$YEAR/"
echo "by $ORGANIZER_NAME, $ORGANIZER_EMAIL (as $USER@$HOSTNAME)"
echo "on $(date -Iminutes)"
echo "based on the components"
for repo in $GIT_REPOS; do
  (
  pushd "$DIR/../../$repo" > /dev/null || exit
  MSG="$(git remote get-url origin)  git-describe: "
  if [ "$repo" == "benchexec" ]; then
    MSG="$MSG $(git describe --long --always)"
  else
    # Use the tags made for this competition
    MSG="$MSG $(git describe --long --always --match "$(echo "$COMPETITIONNAME" | tr "[:upper:]" "[:lower:]" | sed "s/-//")*")"
  fi
  echo "$MSG"
  popd > /dev/null || exit
  )
done

echo "Archive: $(basename "$TOOL_ARCHIVE")  ($(basename $(realpath "$TOOL_ARCHIVE")))  DATE: $(date -Iminutes --date=@"$(stat --format=%Y "$TOOL_ARCHIVE")")  SHA1: $(shasum "$TOOL_ARCHIVE" | sed "s/\(.\{10\}\).*/\1/")..."
echo ""
