#!/bin/bash

set -euo pipefail
shopt -s nullglob

if [[ ${#@} -ne 2 ]]; then
  echo "Usage: $0 <results-file> <benchset(real or smt)>"
  exit 1
fi

solvers=("a-str" "cvc5" "ostrich" "z3-noodler")
benchsets=("automatark" "matching" "rna-sat" "rna-unsat" "woorpje")
out="$1"
rm -f "$out" 2>/dev/null
echo "bench,a-str_time,cvc5_time,ostrich_time,z3-noodler_time" > "$out"

if [[ "$2" == "real" ]]; then
    benchsets=("real")
elif [[ "$2" != "smt" ]]; then
    echo "Unknown benchset $2, expected real or smt"
    exit 1
fi

for benchset in "${benchsets[@]}"; do
  src_dir="smt-logs/${solvers[0]}/$benchset"
  files=( "$src_dir"/*.time )
  [[ ${#files[@]} -eq 0 ]] && continue

  for file in "${files[@]}"; do
    name=$(basename "$file")
    name=${name%%.*}

    row="$name"
    for solver in "${solvers[@]}"; do
      f="smt-logs/$solver/$benchset/$name.time"
      if [[ $solver == "a-str" ]]; then
        f="smt-logs/$solver/$benchset/$name.json.time"
      fi
      if [[ -f "$f" ]]; then
        time=$(awk -F= '/^real=/{print $2}' "$f")
      else
        time=""
      fi
      row="$row,$time"
    done
    echo "$row" >> "$out"
  done
done

shopt -u nullglob