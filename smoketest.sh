#!/bin/bash

# first run each solver in bin on a benchmark
solver_arr=("a-str" "cvc5" "ostrich" "z3-noodler")
bench="instance00022.smt2"
set="automatark"
smt_out="results/smoketest-smt-results.csv"
spf_out="results/smoketest-spf-results.csv"
echo "solver, time, result, model" > $smt_out

echo -e "======================================\nRunning smoketest on SMT-LIB\n======================================="

for solver in "${solver_arr[@]}"; do
    if [[ $solver == "a-str" ]]; then
        file="benchmarks/a-str/$set/$bench.json"
    else
        file="benchmarks/smt/$set/$bench"
    fi
    echo "Running $solver"
    taskset -c 0 ./scripts/run_solver.sh "$solver" "$file" "$set"

    #accumulate smt-logs and times
    echo -n "$solver, " >> "$smt_out"
    awk -F'[=]' '/^real/{print $2}' "smt-logs/$solver/$set/$(basename "$file").time" | tr -d '\n' >> "$smt_out"
    echo -n ", " >> "$smt_out"
    cat "smt-logs/$solver/$set/$(basename "$file").log" | tr -d '\n' | sed 's/sat[^,]/sat,/' >> "$smt_out"
    echo "" >> "$smt_out"
done

echo -e "\n=======================================\nRunning smoketest on SV-COMP\n======================================="
# then run SPF on one file
cd sv-comp
export VERIFIER="smoketest.spf"

./myRunVerify.sh

cd ..
mv results/results.*.table.csv "$spf_out"
rm results/results.*.table.html


echo -e "\n=======================================\n\
Tests completed - Validating results...\n\
Checking SMT-LIB results in $smt_out..."
astr_actual=$(cat smt-logs/a-str/$set/$bench.json.log | tr -d '\n')
astr_act_0=${astr_actual%,*}
astr_act_1=${astr_actual#:}
if [[ "$astr_act_0" != "sat" || "$astr_act_1" != ' ""' ]]; then
    echo -e "\033[0;31ma-str model output does not match expected.\033[0m"
    echo $astr_act_0 
    echo $($actr_act_0 == "sat")
    echo $astr_act_1
    echo $($astr_act_1 == ' ""')
    echo "Actual:   '$astr_actual'"
fi
cvc5_expect="sat((define-fun X () String \"\"))"
cvc5_actual=$(cat smt-logs/cvc5/$set/$bench.log | tr -d '\n')
if [[ "$cvc5_actual" != "$cvc5_expect" ]]; then
    echo -e "\033[0;31mcvc5 model output does not match expected.\033[0m"
    echo "Expected: '$cvc5_expect'"
    echo "Actual:   '$cvc5_actual'"
fi
ostrich_expect="sat(model  (define-fun X () String \"\"))"
ostrich_actual=$(cat smt-logs/ostrich/$set/$bench.log | tr -d '\n')
if [[ "$ostrich_actual" != "$ostrich_expect" ]]; then
    echo -e "\033[0;31mostrich model output does not match expected.\033[0m"
    echo "Expected: '$ostrich_expect'"
    echo "Actual:   '$ostrich_actual'"
fi
z3_expect="sat( (define-fun X () String \"\"))"
z3_actual=$(cat smt-logs/z3-noodler/$set/$bench.log | tr -d '\n' | tr -s ' ')
if [[ "$z3_actual" != "$z3_expect" ]]; then
    echo -e "\033[0;31mz3-noodler model output does not match expected.\033[0m"
    echo "Expected: '$z3_expect'"
    echo "Actual:   '$z3_actual'"
fi

echo -e "Checking SV-COMP results in $spf_out..."

result=$(awk '/^String/{print $2, $6}' "$spf_out")
if [[ "$result" != "true true" ]]; then
    echo -e "\033[0;31mSV-COMP results do not match expected.\033[0m"
fi

rm -rf smt-logs

echo -e "=======================================\nSmoketest completed.\n\
SMT-LIB results in $smt_out\n\
SV-COMP results in $spf_out"