#!/bin/bash

# This file is part of the competition environment.
#
# SPDX-FileCopyrightText: 2011-2021 Dirk Beyer <https://www.sosy-lab.org>
#
# SPDX-License-Identifier: Apache-2.0

# This is the main script to execute benchmarks; this execution phase has four steps:
# Step 1: Call execute-runcollection.sh to execute the tool (e.g., verification or test generation)
#         according to the given benchmark definition
# Step 2: Call execute-runcollection.sh to execute a number of result validators
#         (e.g., witness-based result validation or test-suite validation)
# Step 3: Call mkRunProcessLocal.sh to post-process the results
# Step 4: Call mkRunWebCopy.sh to copy the results to the web server and backup drive
# Step 5: Call mkRunMailResults.sh to send results to participants

set -euo pipefail

source "$(dirname "$0")"/../configure.sh

export VERIFIER=$1;
NUMBER_JOBS_VALIDATORS=$(nproc)
if [[ $NUMBER_JOBS_VALIDATORS > 10 ]]; then
  NUMBER_JOBS_VALIDATORS=10
fi

if [[ $VERIFIER == "" ]]; then
  echo "Usage: $0 VERIFIER"
  exit
fi

echo "";
echo "($VERIFIER)  Run started";

if [[ "$ACTIONS" =~ "PRODUCE_RESULTS" ]]; then
  echo "Downloading archive for $VERIFIER ..."
  "$SCRIPT_DIR"/../fm-tools/lib-fm-tools/python/src/fm_tools/update_archives.py \
      --fm-root "$SCRIPT_DIR"/../fm-tools/data/ \
      --archives-root "$SCRIPT_DIR"/../archives/ \
      --competition "$COMPETITIONNAME $YEAR" \
      --competition-track "$TRACK" \
      "$VERIFIER"
  # Run on VerifierCloud if desired
  OPTIONSVERIFY="$OPTIONSVERIFY $VERIFIERCLOUDOPTIONS"
  CONTAINER=$(yq --raw-output '(.competition_participations[]? | select( .competition=="'"$COMPETITIONNAME $YEAR"'" and .track == "'"$TRACK"'") | .tool_version ) as $version  | .versions[] | select(.version == $version  and (.full_container_images | length != 0)) | .full_container_images[0]' "fm-tools/data/$VERIFIER.yml")
  if [[ "$CONTAINER" != "" ]]; then
    echo "Using container $CONTAINER"
    OPTIONSVERIFY="$OPTIONSVERIFY  --vcloudContainerImage $CONTAINER"
  fi
  # To limit benchmark to a single task-set, uncomment the next line.
  # OPTIONSVERIFY="$OPTIONSVERIFY --tasks ReachSafety-ControlFlow --tasks MemSafety-Heap"
  "$SCRIPT_DIR"/execute_runs/execute-runcollection.sh \
	  "$BENCHMARKSCRIPT" "$(dirname "$0")/../../archives/$VERIFIER-$PRODUCER.zip" "$(dirname "$0")/../../benchmark-defs/$VERIFIER.xml" \
	  "\"$WITNESSTARGET\"" "$(dirname "$0")/../../$RESULTSVERIFICATION/" "$OPTIONSVERIFY $BENCHEXECOPTIONS $LIMIT_TIME $LIMIT_CORES $LIMIT_MEMORY $TESTCOMPOPTION"
fi

pushd "$RESULTSVERIFICATION" > /dev/null || exit
RESULT_DIR=$(latest_matching_filename "$VERIFIER.????-??-??_??-??-??.files" | sed -e "s#^\./##")
if [ -e "$RESULT_DIR" ]; then
  echo "Results in $RESULT_DIR"
else
  echo "No result files found."
  #exit 1
fi
popd > /dev/null || exit

if [[ "$ACTIONS" =~ "VALIDATE_RESULTS" ]]; then
  echo "";
  echo "Processing validation of $VERIFIER's results in $RESULT_DIR ...";
  VAL_COMMANDS=$(mktemp --suffix=-validation-runs.txt)
  # Run on BenchCloud if desired
  OPTIONSVALIDATE="$OPTIONSVALIDATE $VERIFIERCLOUDOPTIONS"
  for VALIDATORXMLTEMPLATE in $VALIDATORLIST; do
    VALIDATOR="${VALIDATORXMLTEMPLATE%-validate-*}"
    echo "";
    echo "Running validation by $VALIDATORXMLTEMPLATE ..."
    echo "Downloading archive for $VALIDATOR ..."
    if [[ "$VALIDATORXMLTEMPLATE" =~ validate-correctness-witnesses-1.0 ]]; then
      VALTRACK="Validation of Correctness Witnesses 1.0"
    elif [[ "$VALIDATORXMLTEMPLATE" =~ validate-correctness-witnesses-2.0 ]]; then
      VALTRACK="Validation of Correctness Witnesses 2.0"
    elif [[ "$VALIDATORXMLTEMPLATE" =~ validate-violation-witnesses-1.0 ]]; then
      VALTRACK="Validation of Violation Witnesses 1.0"
    elif [[ "$VALIDATORXMLTEMPLATE" =~ validate-violation-witnesses-2.0 ]]; then
      VALTRACK="Validation of Violation Witnesses 2.0"
    elif [[ "$VALIDATORXMLTEMPLATE" =~ validate-test-suites-clang-formatted ]]; then
      VALTRACK="Validation of Test Suites Clang Formatted"
    elif [[ "$VALIDATORXMLTEMPLATE" =~ validate-test-suites-clang-unformatted ]]; then
      VALTRACK="Validation of Test Suites Clang Unformatted"
    elif [[ "$VALIDATORXMLTEMPLATE" =~ validate-test-suites-gcc-formatted ]]; then
      VALTRACK="Validation of Test Suites GCC Formatted"
    elif [[ "$VALIDATORXMLTEMPLATE" =~ validate-test-suites-gcc-unformatted ]]; then
      VALTRACK="Validation of Test Suites GCC Unformatted"
    fi
    "$SCRIPT_DIR"/../fm-tools/lib-fm-tools/python/src/fm_tools/update_archives.py \
        --fm-root "$SCRIPT_DIR"/../fm-tools/data/ \
        --archives-root "$SCRIPT_DIR"/../archives/ \
        --competition "$COMPETITIONNAME $YEAR" \
        --competition-track "$VALTRACK" \
        "$VALIDATOR"

    VALIDATORXML="$(dirname "$0")/../../benchmark-defs/${VALIDATORXMLTEMPLATE}-${VERIFIER}.xml";
    sed "s/LOGDIR/$RESULT_DIR/g" "$PATHPREFIX/$BENCHMARKSDIR/$VALIDATORXMLTEMPLATE.xml" > "$VALIDATORXML"
    if [[ "$VALIDATOR" == "witnesslint" ]] &&  yq --exit-status '.competition_participations [] | select(.competition=="'"$COMPETITIONNAME $YEAR"'" and .track == "'"$TRACK"'" and (.label | index("inactive"))) | length > 0' "$BENCHMARKSDIR/../fm-tools/data/$VERIFIER.yml"; then
      echo "Witness-linter call for inactive participation:"
      echo "Insert option into benchmark definition for witnesslint to not perform recent checks on inactive participants."
      VALIDATORBENCHDEF=$(cat "$VALIDATORXML")
      echo "$VALIDATORBENCHDEF" \
	| xmlstarlet edit --append '/benchmark/option[@name="--ignoreSelfLoops"]' --type elem -n 'option' --value '0' \
	                  --insert '/benchmark/option[not(@name)]'                --type attr -n 'name'   --value '--excludeRecentChecks' \
        > "$VALIDATORXML"
    fi
    echo "";
    echo "Processing validation $VALIDATORXML ...";
    # Create a list of task-sets of the verifier, formatted such that it can be passed to BenchExec.
    if [[ "$OPTIONSVALIDATE" =~ "--tasks" ]]; then
      RUNDEFS=""
    else
      RUNDEFS=$(xmlstarlet select --template --match '//*/tasks' \
	        --output '--tasks ' --value-of '@name' --nl "$BENCHMARKSDIR/$VERIFIER.xml" 2>/dev/null)
    fi
    BENCHMARKSCRIPTACTUAL="$BENCHMARKSCRIPT"
    CPUMODEL=$(xmlstarlet select --template --match benchmark/require --value-of '@cpuModel' "$VALIDATORXML" 2>/dev/null)
    OPTIONSVALIDATEEXTRA=""
    if [[ "$CPUMODEL" =~ "AMD EPYC 7713 64-Core" ]]; then
      # Run locally
      BENCHMARKSCRIPTACTUAL="$(dirname "$0")/../../benchexec/bin/benchexec"
      LIMIT_VAL_CORES="--limitCores 1"
      OPTIONSVALIDATEEXTRA="-N $(nproc)"
    fi
    # To limit benchmark to a single task-set, uncomment the next line.
    # RUNDEFS="--tasks ReachSafety-ControlFlow --tasks MemSafety-Heap"

    echo "$SCRIPT_DIR"/execute_runs/execute-runcollection.sh \
	    "$BENCHMARKSCRIPTACTUAL" "$(dirname "$0")/../../archives/$VALIDATORXMLTEMPLATE.zip" "$VALIDATORXML" \
	    "\\\"$WITNESSTARGET\\\"" "$(dirname "$0")/../../$RESULTSVALIDATION/" "$OPTIONSVALIDATE $OPTIONSVALIDATEEXTRA $BENCHEXECOPTIONS $LIMIT_VAL_TIME $LIMIT_VAL_CORES $LIMIT_VAL_MEMORY $TESTCOMPOPTION" $(echo $RUNDEFS) \
	    >> "$VAL_COMMANDS"
  done
  echo "All validation tasks created and ready to be executed.";
  echo "";
  cat "$VAL_COMMANDS" | xargs --max-proc="$NUMBER_JOBS_VALIDATORS" --replace={} --process-slot-var="SLOT" bash -c '{} |& tee -a ./results-logs/"$VERIFIER"-"$SLOT".log'
  rm "$VAL_COMMANDS"
fi

date -Iseconds

if [[ "$ACTIONS" =~ "PREPARE_RESULTS" ]]; then
  # Process results and create HTML tables
  source "$SCRIPT_DIR"/prepare_tables/mkRunProcessLocal.sh "$VERIFIER";
fi

if [[ "$ACTIONS" =~ "PUBLISH_RESULTS" ]]; then
  # Copy results
  source "$SCRIPT_DIR"/prepare_tables/mkRunWebCopy.sh "$VERIFIER"
fi

if [[ "$ACTIONS" =~ "SEND_RESULTS" ]]; then
  # E-mail results
  source "$SCRIPT_DIR"/prepare_tables/mkRunMailResults.sh "$VERIFIER" --really-send-email;
fi

