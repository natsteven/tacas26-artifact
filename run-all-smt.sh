#!/bin/bash
set -euo pipefail

if [[ ${#@} -ge 2 ]]; then
  echo "Usage: $0 <timeout-secs>"
  exit 1
fi

./scripts/smt-run.sh --s all --b all $@

./scripts/make-table.sh $HOME/tacas26-artifact/results/smt-results.csv smt
./scripts/make-table.sh $HOME/tacas26-artifact/results/real-results.csv real

./scripts/make-graphs.py

echo -e "===================================================\n\
All done. Results in $HOME/tacas26-artifact/results/"