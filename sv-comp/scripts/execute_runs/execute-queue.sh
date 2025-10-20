#!/bin/bash

# Start this script with `ionice -c 3 nice `.

set -euo pipefail

while true; do
  # Update job queue.
  source scripts/execute_runs/update-queue.sh

  # Process next job.
  set +e
  JOB=$(ls -t queue/ | grep -v "\(^README.md$\|\.wait$\|\.running$\|\.finished$\)" | tail -1)
  set -e
  if [[ "$JOB" == "" ]]; then
    echo ""
    echo "No jobs available. Build witness store if necessary."
    date -Iseconds
    sleep 600
    continue
  fi
  echo ""
  echo "Processing job: $JOB"
  mv "queue/$JOB" "queue/$JOB.running"
  # Remove previously 'finished' state if it exists.
  rm -f "queue/$JOB.finished"
  sleep 10
  source scripts/execute_runs/mkRunVerify.sh "$JOB" |& tee -a "./results-logs/$JOB.log"
  mv -f "queue/$JOB.running" "queue/$JOB.finished"
done

echo "All jobs finished."

