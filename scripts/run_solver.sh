#!/bin/bash

set -euo pipefail
solver="$1"
file="$2"
benchset="$3"

mkdir -p smt-logs smt-logs/"$solver" smt-logs/"$solver"/"$benchset"

log="smt-logs/$solver/$benchset/$(basename "$file").log"
performance_log="smt-logs/$solver/$benchset/$(basename "$file").time"
rm -f "$log" "$performance_log"

rc=0
TIMEOUT_SECS=${TIMEOUT_SECS:-60}
MEM_LIMIT_MB=${MEM_LIMIT_MB:-1536}

systemd-run --user --scope \
  --slice=solver-runs.slice \
  -p MemoryMax=${MEM_LIMIT_MB}M \
  -p MemoryHigh=$((MEM_LIMIT_MB * 90 / 100))M \
  --quiet \
  -- \
  /usr/bin/time -f 'real=%e\nuser=%U\nsys=%S\nmax_rss_kb=%M' \
    -o "$performance_log" \
    timeout "${TIMEOUT_SECS}s" ./bin/"$solver" "$file" > "$log" 2>&1 || rc=$?

if [ $rc -eq 124 ]; then
  echo "timeout" > "$log"
  echo "real=$TIMEOUT_SECS" > "$performance_log"
elif [[ $rc -eq 137 || $rc -eq 143 ]]; then
  echo "memout" > "$log"
  echo "real=$TIMEOUT_SECS" > "$performance_log"
elif grep -qi "out of memory\|cannot allocate memory" "$log" 2>/dev/null; then
  echo "memout" > "$log"
  echo "real=$TIMEOUT_SECS" > "$performance_log"
elif [ $rc -ne 0 ]; then
  echo "EXITED with $rc" > "$log"
  echo "real=$TIMEOUT_SECS" > "$performance_log"
fi