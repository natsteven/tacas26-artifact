#!/bin/bash
# this is mostly a modified copy of scripts/execute_runs/mkRunVerify.sh

set -euo pipefail

SCRIPT_DIR="scripts";
WITNESSTARGET="witness.graphml witness.yml"
RESULTSVERIFICATION="results-verified";
BENCHEXECOPTIONS="--maxLogfileSize 2MB --read-only-dir / --read-only-dir $(realpath .) --overlay-dir ./ --hidden-dir /home/"
LIMIT_TIME=""
LIMIT_CORES=""
LIMIT_MEMORY=""

VERIFIER=${VERIFIER:-"spf"}
export VERIFIER

BENCHDEF="$VERIFIER.xml"
ARCHIVE="archives/spf-verify.zip"

echo "($VERIFIER) Run started";

# this could be simpler as we use the same container
CONTAINER="registry.gitlab.com/sosy-lab/benchmarking/competition-scripts/user:2023"
if [[ "$CONTAINER" != "" ]]; then
  echo "Using container $CONTAINER"
fi
"$SCRIPT_DIR"/execute_runs/execute-runcollection.sh \
	  "benchexec/bin/benchexec" "$ARCHIVE" "$BENCHDEF" \
	  "\"$WITNESSTARGET\"" "$(dirname "$0")/$RESULTSVERIFICATION/" \
	  "$BENCHEXECOPTIONS $LIMIT_TIME $LIMIT_CORES $LIMIT_MEMORY"

date -Iseconds

echo "Getting HTML and CSV tables:"
RESULTS="$(ls $RESULTSVERIFICATION/$VERIFIER.*.xml.bz2)"
./benchexec/bin/table-generator $RESULTS > /dev/null

RESULTS="$(ls $RESULTSVERIFICATION/results.*.table.html)"
 if [[ "$RESULTS" =~ $RESULTSVERIFICATION/results\.([0-9]{4}-[0-9]{2}-[0-9]{2}_[0-9]{2}-[0-9]{2}-[0-9]{2})\.table\.html$ ]]; then
   DATETIME="${BASH_REMATCH[1]}"
 fi

mv $RESULTSVERIFICATION/results.*.table.* ../results
rm -rf $RESULTSVERIFICATION/*

rm -rf bin/$VERIFIER*