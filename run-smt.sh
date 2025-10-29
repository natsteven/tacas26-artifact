#!/bin/bash
set -euo pipefail

if [[ ${#@} -ge 2 ]]; then
  echo "Usage: $0 <timeout-secs>"
  exit 1
fi

if [ -t 0 ]; then
  read -p "Run full SMT benchmark suite? This will take several hours. (y/n) " response || exit 1
  response=${response,,}
  if [[ -n "$response" && "$response" != "y" && "$response" != "yes" ]]; then
    echo "Aborted"
    exit 0
  fi
fi

./scripts/smt-run.sh --s all --b automatark,matching,real,woorpje $@

./scripts/make-table.sh results/smt-results.csv smt
./scripts/make-table.sh results/real-results.csv real

./scripts/make-graph.py results/smt-results.csv SMT
./scripts/make-graph.py results/real-results.csv Real

echo -e "===================================================\n"
auto_expected=$(wc -l < util/automatark-filenames.txt)
match_expected=$(wc -l < util/matching-filenames.txt)
# rna_sat_expected=$(wc -l < util/rna-sat-filenames.txt)
# rna_unsat_expected=$(wc -l < util/rna-unsat-filenames.txt)
real_expected=$(wc -l < util/real-filenames.txt)
woorpje_expected=$(wc -l < util/woorpje-filenames.txt)

declare -A expected_counts=( ["automatark"]=$auto_expected ["matching"]=$match_expected ["real"]=$real_expected ["woorpje"]=$woorpje_expected )

for solver in a-str cvc5 ostrich z3-noodler; do
  for benchset in "${!expected_counts[@]}"; do
    ran=$(ls smt-logs/"$solver"/"$benchset"/*.time 2>/dev/null | wc -l || echo 0)
    expected=${expected_counts[$benchset]}
    if [[ $ran -ne $expected ]]; then
      echo -e "\033[0;31mWarning: Solver $solver has $ran/$expected results on $benchset\033[0m"
    fi
  done
done
echo "All done. Results in results/"