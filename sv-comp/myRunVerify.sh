#!/bin/bash
# this is mostly a modified copy of scripts/execute_runs/mkRunVerify.sh

set -euo pipefail

source "scripts/configure.sh"

# LIMIT_TIME=
# LIMIT_MEMORY=

export VERIFIER="spf";

BENCHDEF="$VERIFIER.xml"
ARCHIVE="archives/$VERIFIER-verify.zip"

echo "($VERIFIER) Run started";

# this could be simpler as we use the same container
CONTAINER=$(yq --raw-output '(.competition_participations[]? | select( .competition=="'"$COMPETITIONNAME $YEAR"'" and .track == "'"$TRACK"'") | .tool_version ) as $version  | .versions[] | select(.version == $version  and (.full_container_images | length != 0)) | .full_container_images[0]' "fm-tools/data/$VERIFIER.yml")
if [[ "$CONTAINER" != "" ]]; then
  echo "Using container $CONTAINER"
fi
"$SCRIPT_DIR"/execute_runs/execute-runcollection.sh \
	  "benchexec/bin/benchexec" "$ARCHIVE" "$BENCHDEF" \
	  "\"$WITNESSTARGET\"" "$(dirname "$0")/$RESULTSVERIFICATION/" \
	  "$OPTIONSVERIFY $BENCHEXECOPTIONS $LIMIT_TIME $LIMIT_CORES $LIMIT_MEMORY $TESTCOMPOPTION"\
	  "--numOfThreads 2"

date -Iseconds

echo "Getting HTML and CSV tables:"
RESULTS="$(ls $RESULTSVERIFICATION/$VERIFIER.*.xml.bz2)"
./benchexec/bin/table-generator $RESULTS

RESULTS="$(ls $RESULTSVERIFICATION/results.*.table.html)"
 if [[ "$RESULTS" =~ $RESULTSVERIFICATION/results\.([0-9]{4}-[0-9]{2}-[0-9]{2}_[0-9]{2}-[0-9]{2}-[0-9]{2})\.table\.html$ ]]; then
   DATETIME="${BASH_REMATCH[1]}"
 fi

LOGDIR="$RESULTSVERIFICATION/$VERIFIER-results.$DATETIME"

mkdir "$LOGDIR"
mkdir "$LOGDIR/witnesses"
mkdir "$LOGDIR/util"

rm $RESULTSVERIFICATION/$VERIFIER.*.json
unzip $RESULTSVERIFICATION/$VERIFIER.*.zip -d "$LOGDIR"
rm $RESULTSVERIFICATION/$VERIFIER.*.zip
mv $RESULTSVERIFICATION/$VERIFIER.*.files $LOGDIR/witnesses
mv $RESULTSVERIFICATION/$VERIFIER.* "$LOGDIR/util"
mv $RESULTSVERIFICATION/results.*.table.html "$LOGDIR"
mv $RESULTSVERIFICATION/results.* "$LOGDIR/util"

rm -rf bin/$VERIFIER*