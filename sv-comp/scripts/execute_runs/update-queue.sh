#!/bin/bash

set -eao pipefail

echo "----------------------------------------------"
echo "Pulling new archive DOIs."
(cd fm-tools/; git pull --prune --rebase origin main)

VERIFIERLIST=
VALIDATORLIST=
source "$(dirname "$0")"/../configure.sh

echo "----------------------------------------------"
echo "Add new jobs to the queue."
for JOB in $VERIFIERLIST; do
  ARCHIVE_FILE="archives/$JOB-$PRODUCER.zip"
  echo ""
  echo ""
  echo "Considering $JOB"
  echo "Updating archive for $JOB ..."
  "$SCRIPT_DIR"/../fm-tools/lib-fm-tools/python/src/fm_tools/update_archives.py \
      --fm-root "$SCRIPT_DIR"/../fm-tools/data/ \
      --archives-root "$SCRIPT_DIR"/../archives/ \
      --competition "$COMPETITIONNAME $YEAR" \
      --competition-track "$TRACK" \
      "$JOB"

  RESULT=$(latest_matching_filename "results-verified/$JOB.*.logfiles.zip")
  if [[ -e "$RESULT" ]]; then
    # Look at the most recent run result.
    RESULT_TIME=${RESULT##*$JOB.}
    RESULT_TIME=${RESULT_TIME%.logfiles.zip}
    ARCHIVE_TIME=$(date "+%Y-%m-%d_%H-%M-%S" --reference="$ARCHIVE_FILE")
    echo "Time stamp of run-result: $RESULT_TIME"
    echo "Time stamp of archive:    $ARCHIVE_TIME"
    if [[ "$ARCHIVE_TIME" < "$RESULT_TIME" ]]; then
      echo "Job was already processed."
      continue
    fi
  fi
  # Add job only if it is not already added (no file-name extension), or held back (state 'wait'), or currently running ('running').
  if [[ -e "queue/$JOB"  ||  -e "queue/$JOB.wait"  ||  -e "queue/$JOB.running" ]] ; then
    echo "Not scheduled $JOB"
    continue
  fi
  echo "Scheduling $JOB"
  touch --reference="$ARCHIVE_FILE" "queue/$JOB"
done
