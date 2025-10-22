#!/bin/bash

# first run each solver in bin on a benchmark
solver_arr=("a-str" "cvc5" "ostrich" "z3-noodler")
bench="instance00022.smt2"
logs="smoketest_results.csv"
echo "solver, time, result, model" > $logs

echo -e "Running smoketest on SMT-LIB\n======================================="

for solver in "${solver_arr[@]}"; do
    if [[ $solver == "a-str" ]]; then
        file="benchmarks/a-str/automatark/$bench.json"
    else
        file="benchmarks/smt/automatark/$bench"
    fi
    echo "Running $solver on $file"
    taskset -c 0 ./scripts/run_solver.sh "$solver" "$file" "automatark"

    #accumulate logs and times
    echo -n "$solver, " >> "$logs"
    awk -F'[ ,]' '/^real=/{print $2}' "logs/$solver/automatark/$(basename "$file").time" >> "$logs"
    cat "logs/$solver/automatark/$(basename "$file").log" | tr -d '\n' >> "$logs"
done

echo -e "\n=======================================\nRunning smoketest on SV-COMP"
# then run SPF on one file
cd sv-comp
export VERIFIER="smoketest.spf"
./myRunVerify.sh


echo -e "=======================================\nSmoketest completed. SMT-LIB results in $logs, and SV-COMP results in sv-comp/results-verified"