# Configuration of variables to initialize the competition environment

set -euo pipefail
shopt -s nullglob

SCRIPT_DIR=$(realpath "scripts");
source "$SCRIPT_DIR"/util.sh

BENCHMARKSDIR="benchmark-defs";

ORGANIZER_EMAIL="dirk.beyer@sosy-lab.org"
ORGANIZER_NAME="Dirk Beyer"
RESULTS_OBSERVERS=$(yq --raw-output '.observer_email' ${BENCHMARKSDIR}/category-structure.yml)

YEAR=$(yq --raw-output '.year' ${BENCHMARKSDIR}/category-structure.yml)
COMPETITIONNAME=$(yq --raw-output '.competition' ${BENCHMARKSDIR}/category-structure.yml)
COMPETITION=${COMPETITIONNAME}${YEAR#??}  # use two last digits of year, only
TRACK="Verification"
TRACK_VALIDATION_PREFIX="Validation"
PRODUCER="verify"
if [[ $COMPETITIONNAME == "Test-Comp" ]]; then
  TRACK="Test Generation"
  PRODUCER="test"
fi
TARGETSERVER=$(echo "$COMPETITIONNAME" | tr "[:upper:]" "[:lower:]")
FILE_STORE_URL_PREFIX="https://${TARGETSERVER}.sosy-lab.org/${YEAR}/results/"

PATHPREFIX=$(realpath .)
TARGETDIR=${COMPETITIONNAME,,}
RESULTSVERIFICATION="results-verified";
RESULTSVALIDATION="results-validated";
BINDIR="bin";
export PYTHONPATH="$PATHPREFIX/benchexec:$SCRIPT_DIR"
BENCHEXEC_PATH="${PATHPREFIX}/benchexec";
BENCHMARKSCRIPT="$(dirname "$0")/../../benchexec/bin/benchexec"
# The directory modes here are for the local determining of the version number (not relevant for run execution).
BENCHEXECOPTIONS="--maxLogfileSize 2MB --read-only-dir / --read-only-dir $PATHPREFIX --overlay-dir ./ --hidden-dir /home/"
if [ -e /data ]; then
  BENCHEXECOPTIONS="$BENCHEXECOPTIONS --hidden-dir /data/"
fi
if [ -e /localhome ]; then
  BENCHEXECOPTIONS="$BENCHEXECOPTIONS --hidden-dir /localhome/"
fi

ADDRESS_BOOK=~/.competition-address-book.txt
OPTIONSVERIFY=${OPTIONSVERIFY:-""}
OPTIONSVALIDATE=${OPTIONSVALIDATE:-""}
LIMIT_CORES=${LIMIT_CORES:-""}
LIMIT_MEMORY=${LIMIT_MEMORY:-""}
LIMIT_TIME=${LIMIT_TIME:-""}
LIMIT_VAL_CORES=${LIMIT_VAL_CORES:-""}
LIMIT_VAL_MEMORY=${LIMIT_VAL_MEMORY:-""}
LIMIT_VAL_TIME=${LIMIT_VAL_TIME:-""}
USER_CONFIG="$PATHPREFIX"/.competition-configure.sh
if [ -e "$USER_CONFIG" ]; then
  source "$USER_CONFIG"
fi
VERIFIERCLOUDOPTIONS=""
VERIFIERCLOUD_CONFIG="$PATHPREFIX"/.competition-configure-verifiercloud.sh
if [ -e "$VERIFIERCLOUD_CONFIG" ]; then
  source "$VERIFIERCLOUD_CONFIG"
else
  OPTIONSVERIFY="$OPTIONSVERIFY -N $(($(nproc) / 8))"    # Number of parallel executing verification/test runs
  OPTIONSVALIDATE="$OPTIONSVALIDATE -N $(($(nproc) / 8))"  # Number of parallel executing validation runs
  # Suggested config for a quick and rough local execution
  # LIMIT_CORES="--limitCores 2"            # Number of cores for verification/test runs
  # LIMIT_VAL_CORES="--limitCores 2"        # Number of corse for validation runs
  # OPTIONSVERIFY="-N $(($(nproc) / 2))"    # Number of parallel executing verification/test runs
  # OPTIONSVALIDATE="-N $(($(nproc) / 2))"  # Number of parallel executing validation runs
fi

ACTIONS=${ACTIONS:-"PRODUCE_RESULTS VALIDATE_RESULTS PREPARE_RESULTS"}

HASHES_BASENAME="fileHashes.json";
HASHDIR_BASENAME="fileByHash";

PROPERTIES=$(yq -r '.properties []' benchmark-defs/category-structure.yml)

VERIFIERLIST=$(yq --raw-output --slurp "map( select( .competition_participations[]? | .competition==\"$COMPETITIONNAME $YEAR\" and .track==\"$TRACK\" ) ) | sort_by([.input_languages[0], .id]) [] .id" fm-tools/data/*.yml)
if [[ -z "${VERIFIERLIST:-}" ]]; then
  echo "INFO: Setting up list of tools"
  VERIFIERLIST=$("$SCRIPT_DIR"/execute_runs/list-tools.py "$COMPETITIONNAME" "$YEAR" "$TRACK" | sort)
fi

VALIDATORLIST=${VALIDATORLIST:-$(yq --raw-output --slurp "map( .id as \$id  | .competition_participations[]? | select( .competition==\"$COMPETITIONNAME $YEAR\" and (.track | startswith(\"$TRACK_VALIDATION_PREFIX\")) ) | [\$id, .track] | join(\" \") | ascii_downcase | gsub(\" \"; \"-\") | sub(\"validation-of\"; \"validate\") ) []" fm-tools/data/*.yml)}
if [[ -z "${VALIDATORLIST:-}" ]]; then
  echo "INFO: Setting up list of validators"
  VALIDATORLIST=$(for i in $("$SCRIPT_DIR"/execute_runs/list-tools.py "$COMPETITIONNAME" "$YEAR" "Validation of Correctness Witnesses 1.0" | sort); do echo "$i""-validate-correctness-witnesses-1.0"; done)
  VALIDATORLIST="$VALIDATORLIST $(for i in $("$SCRIPT_DIR"/execute_runs/list-tools.py "$COMPETITIONNAME" "$YEAR" "Validation of Correctness Witnesses 2.0" | sort); do echo "$i""-validate-correctness-witnesses-2.0"; done)"
  VALIDATORLIST="$VALIDATORLIST $(for i in $("$SCRIPT_DIR"/execute_runs/list-tools.py "$COMPETITIONNAME" "$YEAR" "Validation of Violation Witnesses 1.0" | sort); do echo "$i""-validate-violation-witnesses-1.0"; done)"
  VALIDATORLIST="$VALIDATORLIST $(for i in $("$SCRIPT_DIR"/execute_runs/list-tools.py "$COMPETITIONNAME" "$YEAR" "Validation of Violation Witnesses 2.0" | sort); do echo "$i""-validate-violation-witnesses-2.0"; done)"
  VALIDATORLIST="$VALIDATORLIST $(for i in $("$SCRIPT_DIR"/execute_runs/list-tools.py "$COMPETITIONNAME" "$YEAR" "Validation of Test Suites" | sort); do echo "$i""-validate-test-suites"; done)"
fi

# Examples for temporary restrictions
#VALIDATORLIST="witnesslint-validate-violation-witnesses";
#ACTIONS="PRODUCE_RESULTS VALIDATE_RESULTS"

RESULTSLEVEL="Final";
LIMITSTEXT=""
if [[ -n "$LIMIT_CORES" || -n "$LIMIT_MEMORY" || -n "$LIMIT_TIME" ]]; then
  LIMITSTEXT="$LIMITSTEXT\nLimits: The current pre-run results are limited with: $LIMIT_TIME $LIMIT_CORES $LIMIT_MEMORY.\n"
  RESULTSLEVEL="Pre-run";
fi
if [[ -n "$LIMIT_VAL_CORES" || -n "$LIMIT_VAL_MEMORY" || -n "$LIMIT_VAL_TIME" ]]; then
  LIMITSTEXT="$LIMITSTEXT\nLimits validation: The current pre-run results are limited with: $LIMIT_VAL_TIME $LIMIT_VAL_CORES $LIMIT_VAL_MEMORY.\n"
  RESULTSLEVEL="Pre-run";
fi

TESTCOMPOPTION=""
if [[ "${COMPETITIONNAME}" == "SV-COMP" ]]; then
  VALIDATIONKIND="witnesses";

  WITNESSTARGET="witness.graphml witness.yml";

elif [[ "${COMPETITIONNAME}" == "Test-Comp" ]]; then
  VALIDATIONKIND="test-suites";

  WITNESSTARGET="test-suite.zip";

  TESTCOMPOPTION="--zipResultFiles";

else
  echo "Unhandled competition $COMPETITIONNAME" ; false
fi



