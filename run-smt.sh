#!/bin/bash
set -euo pipefail

if [[ ${#@} -ge 2 ]]; then
  echo "Usage: $0 <timeout-secs>"
  exit 1
fi

./scripts/smt-run.sh --s all --b automatark,matching,real,woorpje $@

./scripts/make-table.sh results/smt-results.csv smt
./scripts/make-table.sh results/real-results.csv real

./scripts/make-graph.py results/smt-results.csv SMT
./scripts/make-graph.py results/real-results.csv Real

echo -e "===================================================\n\
All done. Results in results/"