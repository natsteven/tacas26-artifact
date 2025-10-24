#!/usr/bin/env bash

set -euo pipefail

# Local runner that mirrors submit.sh + job_slurm.sh without SLURM.
# Usage: scripts/run_local.sh --s s1,s2,... --b b1,b2,... [--timeout secs]

if [[ $# -lt 4 ]]; then
  echo "Usage: $0 --s s1,s2... --b b1,b2... [--timeout secs]"
  exit 1
fi

solvers=""
benchsets=""
TIMEOUT_SECS="120"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --s) solvers="$2"; shift 2 ;;
    --b) benchsets="$2"; shift 2 ;;
    --timeout) TIMEOUT_SECS="$2"; shift 2 ;;
    -h|--help)
      echo "Args: --s s1,s2 --b b1,b2 [--timeout secs]"
      exit 0
      ;;
    *) echo "Unknown arg $1"; exit 1 ;;
  esac
done

IFS=',' read -r -a solver_arr <<< "$solvers"
IFS=',' read -r -a bench_arr <<< "$benchsets"

if [[ ${#solver_arr[@]} -eq 0 || ${#bench_arr[@]} -eq 0 ]]; then
  echo "At least one solver and one benchset must be specified."
  exit 1
fi

if [[ ${#solver_arr[@]} -eq 1 && ${solver_arr[0]} == "all" ]]; then
  solver_arr=("a-str" "cvc5" "ostrich" "z3-noodler")
fi
if [[ ${#bench_arr[@]} -eq 1 && ${bench_arr[0]} == "all" ]]; then
  bench_arr=("automatark" "matching" "real" "rna-sat" "rna-unsat" "woorpje")
fi

export TIMEOUT_SECS

echo "Running for solvers: ${solver_arr[*]} and benchsets: ${bench_arr[*]} (timeout=${TIMEOUT_SECS}s)"

declare -a job_list

for benchset in "${bench_arr[@]}"; do
  filenames="util/${benchset}-filenames.txt"
  if [[ ! -f "$filenames" ]]; then
    echo "Missing filenames list: $filenames" >&2
    exit 1
  fi
  mapfile -t files < "$filenames"

  for solver in "${solver_arr[@]}"; do
    for file in "${files[@]}"; do
      path="benchmarks"
      if [[ $solver == "a-str" ]]; then
        path="${path}/a-str/${benchset}/${file}.smt2.json"
      else
        if [[ $benchset == "real" ]]; then
          path="${path}/not_smt/${solver}/${benchset}/${file}.smt2"
        else
          path="${path}/smt/${benchset}/${file}.smt2"
        fi
      fi
      if [[ ! -f "$path" ]]; then
        echo "Warning: missing benchmark file $path (skipping)" >&2
        continue
      fi

      # accumulate jobs
      job_list+=("$solver,$path,$benchset") 

    done
  done
done
echo "Total jobs to run: ${#job_list[@]}"
parallel --memfree 1536M --bar --colsep ',' 'prlimit --as=1610612736 -- scripts/run_solver.sh "{1}" "{2}" "{3}"' ::: "${job_list[@]}"
