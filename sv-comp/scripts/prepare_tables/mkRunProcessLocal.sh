#!/bin/bash

# @title Locally Process the Run Results
# @phase Run (Or Post Process)
# @description Creates the the nice HTML tables from the run results.
# First it collects the results xmls and merges them, and then calls BenchExec's table generator on it.
# Then it creates an HTML summarty page.
# It removes scores from the html, merge jsons, create files, replaces links to the files, compresses the html files.

source $(dirname "$0")/../configure.sh

VERIFIER=$1;
if [[ $VERIFIER == "" ]]; then
  echo "Usage: $0 VERIFIER"
  exit;
fi

cd "$PATHPREFIX/$RESULTSVERIFICATION"
echo "================================================================================================";
date -Iseconds
echo "";
echo "Processing $VERIFIER";

if [[ "$COMPETITIONNAME" == "SV-COMP" ]]; then
  TABLETEMPLATE="$SCRIPT_DIR/prepare_tables/tableDefinition-single-svcomp.xml";
elif [[ "$COMPETITIONNAME" == "Test-Comp" ]]; then
  TABLETEMPLATE="$SCRIPT_DIR/prepare_tables/tableDefinition-single-testcomp.xml";
else
  echo "Unhandled competition name $COMPETITIONNAME"
  exit 1;
fi
HTMLFILESTOREPLACE="$PATHPREFIX/todoTables-$VERIFIER.txt";
rm -f $HTMLFILESTOREPLACE;
CATEGORIES=$(yq -r '.categories [] | .categories []' "../$BENCHMARKSDIR/category-structure.yml" | grep "\." | sed "s/.*\.//" | sort -u)
#CATEGORIES="ReachSafety-BitVectors";
for PROP in $PROPERTIES; do
 echo "";
 echo "  Property $PROP";
 for CAT in $CATEGORIES; do
  echo "";
  echo "    Category $CAT";
  FILEVERIFICATION=$(latest_matching_filename "$VERIFIER.????-??-??_??-??-??.results.${COMPETITION}_$PROP.$CAT.xml.bz2")
  if [ -e "$FILEVERIFICATION" ]; then
    if bzcat "$FILEVERIFICATION" | xmlstarlet sel -t --if '/result/run' --output good --nl 2>/dev/null | grep -q "good"; then
      echo "      $FILEVERIFICATION";
    else
      echo "      INFO: Empty results file found for this property and category ($PROP, $CAT)."
      continue;
    fi
  else
    echo "      INFO: No results found for this property and category ($PROP, $CAT).";
    continue;
  fi
  VALIDATIONFILES="$PATHPREFIX/$RESULTSVERIFICATION/tableFiles_${VERIFIER}.txt";
  rm -f ${VALIDATIONFILES};
  touch ${VALIDATIONFILES};
  for VALIDATION in $VALIDATORLIST; do
    VALIDATOR=${VALIDATION%-validate-*};
    VAL="val_$VALIDATOR"
    FILEVALIDATIONCURR=$(latest_matching_filename "../$RESULTSVALIDATION/$VALIDATION-$VERIFIER.????-??-??_??-??-??.results.${COMPETITION}_$PROP.$CAT.xml.bz2")
    if [ -e "$FILEVALIDATIONCURR" ]; then
      # TODO  check invariant: validation run is newer than the verification run,
      #       otherwise hard fail (see https://gitlab.com/sosy-lab/sv-comp/archives-2021/-/issues/37)
      #       Example date string extraction: mkRunQueueFill.sh
      echo "      $FILEVALIDATIONCURR";
      if [ -e "$FILEVALIDATIONCURR" ]; then
        echo "$FILEVALIDATIONCURR " >> ${VALIDATIONFILES};
      fi
    fi
  done
  echo "    Adjusting result category for correct score calculation";
  CMD="$SCRIPT_DIR/prepare_tables/adjust_results_verifiers.py -i $PATHPREFIX/sv-benchmarks/Invalid-TaskDefs.set $FILEVERIFICATION $(xargs < $VALIDATIONFILES)"
  echo "    Executing: $CMD"
  $CMD

  if [[ ! "$ACTIONS" =~ "PREPARE_RESULTS" ]]; then
    continue
  fi
  FILERESULT=$(latest_matching_filename "$VERIFIER.????-??-??_??-??-??.results.${COMPETITION}_$PROP.$CAT*.xml.bz2")
  RUNDEFNAME=$(echo $FILERESULT | sed "s/.*\.results\.\(${COMPETITION}_${PROP}\)\.${CAT}.*/\1/")
  echo "    Run-definition name: $RUNDEFNAME";
  TABLEDEF="$FILERESULT.xml";
  cat ${TABLETEMPLATE} | grep -v "</table>" | grep -v "<column" > ${TABLEDEF};
  echo '  <result filename="'$FILERESULT'">'  >> ${TABLEDEF};
  cat ${TABLETEMPLATE} | grep '\<column' | grep -v '_covered' | grep -v 'branches_plot' \
      | sed -e "s/___RUNDEFNAME___/${RUNDEFNAME}/" >> ${TABLEDEF};
  echo '  </result>' >> ${TABLEDEF};
  for FILEVALIDATION in $(cat "$VALIDATIONFILES"); do
    echo '  <result filename="'$FILEVALIDATION'">' >> ${TABLEDEF};
    cat ${TABLETEMPLATE} | grep "<column" | grep -v "score" \
        | sed -e "s/___RUNDEFNAME___/${RUNDEFNAME}/" >> ${TABLEDEF};
    echo '  </result>' >> ${TABLEDEF};
  done
  echo '</table>' >> ${TABLEDEF};
  rm ${VALIDATIONFILES};
  # Collect the tables
  echo "$RESULTSVERIFICATION/$FILERESULT.table.html" >> ${HTMLFILESTOREPLACE};
  date -Iseconds;
 done # for category
done # for properties
echo "";

if [[ ! "$ACTIONS" =~ "PREPARE_RESULTS" ]]; then
  echo "Finish results postprocessing without generating tables (requested actions: $ACTIONS)."
  exit
fi

echo "Generating table definitions ...";
TABLEDEFALL="$VERIFIER.results.$COMPETITION.xml";
PYTHONPATH="$PYTHONPATH":"$SCRIPT_DIR"/../benchexec:"$SCRIPT_DIR":"$SCRIPT_DIR"/../fm-tools/lib-fm-tools/python/src/ \
  "$SCRIPT_DIR"/prepare_tables/mkAnaAllTablesVerifier.py --category-structure ../"$BENCHMARKSDIR"/category-structure.yml "$VERIFIER"
echo "$RESULTSVERIFICATION/${TABLEDEFALL/.xml/.table.html}" >> ${HTMLFILESTOREPLACE};
date -Iseconds;
cd ..

tac "$HTMLFILESTOREPLACE" \
  | sed "s/.table.html/.xml/" \
  | xargs --max-proc=$(nproc) --replace={} bash -c "\"$BENCHEXEC_PATH\"/bin/table-generator --no-diff --format html --xml {}  |& grep -v \"\(No result for task\)\|\(A variable was not replaced in\)\"; echo 'Done with {}'"

echo "Removing score row from tables ...";
tac "$HTMLFILESTOREPLACE" \
  | xargs --max-proc=$(nproc) --max-args=1 "$SCRIPT_DIR"/prepare_tables/mkRunProcessLocal_RemoveScoreStats.py --insitu


# We need a unique name because of concurrency - use a temporary file.
ALL_HASHES=$(mktemp --suffix=-comp.json)
# For verification results
WITNESS_VERIFIER_HASHES=$(latest_matching_filename "$RESULTSVERIFICATION/$VERIFIER.????-??-??_??-??-??.$HASHES_BASENAME")
echo "Merging hashes maps (${WITNESS_VERIFIER_HASHES}) ..."
"$SCRIPT_DIR"/prepare_tables/mkRunProcessLocal_MergeJsons.py \
    --output "$ALL_HASHES" \
    "$WITNESS_VERIFIER_HASHES"
date -Iseconds;
# For validation results
for VALIDATION in $VALIDATORLIST; do
  VALIDATOR=${VALIDATION%-validate-*};
  VAL="val_$VALIDATOR"
  echo "Processing $VALIDATION ...";
  WITNESS_VALIDATOR_HASHES=$(latest_matching_filename "$RESULTSVALIDATION/$VALIDATION-$VERIFIER.????-??-??_??-??-??.$HASHES_BASENAME")
  if [ -e "$WITNESS_VALIDATOR_HASHES" ]; then
    echo "Merging hashes maps (${WITNESS_VALIDATOR_HASHES}) ..."
    "$SCRIPT_DIR"/prepare_tables/mkRunProcessLocal_MergeJsons.py \
        --output "$ALL_HASHES" \
        "$ALL_HASHES" "$WITNESS_VALIDATOR_HASHES"
    date -Iseconds;
  fi
done
echo "Creating file store ..."
python3 -m prepare_tables.mkRunProcessLocal_CreateFileStore \
    --output "$HASHDIR_BASENAME" \
    --root-dir "$PATHPREFIX" \
    "$ALL_HASHES"
date -Iseconds;


echo "Replacing witness links ..."
tac "$HTMLFILESTOREPLACE" \
  | xargs --max-proc=$(nproc) --max-args=1 "$SCRIPT_DIR"/prepare_tables/mkRunProcessLocal_ReplaceLinks.py --hashmap "$ALL_HASHES" --file-store-url-prefix "${FILE_STORE_URL_PREFIX}"
date -Iseconds;

echo
echo "Compressing HTML tables ...";
for FILE in $(cat "$HTMLFILESTOREPLACE"); do
  chmod g-s "$FILE"
  gzip -9 --force "$FILE"
done
date -Iseconds;
rm ${HTMLFILESTOREPLACE};
rm ${ALL_HASHES};


echo
echo "Generating list of HTML pages ...";
HTMLOVERVIEW="$VERIFIER.list.html"
VERIFIERXML="${VERIFIER}.xml";
echo "Processing $VERIFIER starting at $(date --rfc-3339=seconds)"
cd ${PATHPREFIX};
if [ ! -e "$BENCHMARKSDIR/$VERIFIERXML" ]; then
  echo "File $BENCHMARKSDIR/$VERIFIERXML not found."
  continue
fi
cd ${PATHPREFIX}/${RESULTSVERIFICATION};
echo "<h3>$VERIFIER</h3>" > ${HTMLOVERVIEW};
LINK=$(latest_matching_filename "$VERIFIER.results.$COMPETITION.table.html.gz")
if [ -e "$LINK" ]; then
  echo "<a href=\"${LINK%\.gz}#/table\">${LINK%\.gz}</a>" >> ${HTMLOVERVIEW};
  echo "<br/>" >> ${HTMLOVERVIEW};
fi
for PROP in $PROPERTIES; do
  echo "";
  echo "  Property $PROP";
  for i in $CATEGORIES; do
    LINK=$(latest_matching_filename "$VERIFIER.????-??-??_??-??-??.results.${COMPETITION}_$PROP.$i*.html.gz")
    if [ -e "$LINK" ]; then
      echo "<a href=\"${LINK%\.gz}#/table\">${LINK%\.gz}</a>" >> ${HTMLOVERVIEW};
      echo "<br/>" >> ${HTMLOVERVIEW};
    fi
  done # for category
done # for property

cd "$PATHPREFIX"
