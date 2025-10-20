#!/bin/bash

# Copy the results to web server and to backup drive

source $(dirname "$0")/../configure.sh

if [[ "$YEAR" != "2025" ]]; then
  echo "Info: We should not copy results for past competitions to the web server."
  exit;
fi

VERIFIER=$1;
if [[ "$VERIFIER" == "" ]]; then
  echo "Usage: $0 VERIFIER"
  exit;
fi

cd "$PATHPREFIX"

#echo "Validator statistics ...";
#./contrib/mkValidatorStatistics.py --category-structure benchmark-defs/category-structure.yml --htmlfile ${PATHPREFIX}/${RESULTSVERIFICATION}/validatorStatistics.html
#gzip -9 --force ${PATHPREFIX}/${RESULTSVERIFICATION}/validatorStatistics.html

echo "Copy results for $VERIFIER to web server ..."
echo "... $RESULTSVERIFICATION"
SOURCE="$PATHPREFIX/$RESULTSVERIFICATION/"
TARGET="www-comp.sosy.ifi.lmu.de:/srv/web/data/$TARGETDIR/$YEAR/results/$RESULTSVERIFICATION/"
RESULT_ID=$(latest_matching_filename "$RESULTSVERIFICATION/$VERIFIER.????-??-??_??-??-??.results.*txt" | sed -e "s#^.*/##" -e "s/\.results\..*txt$//")
if [ -z "$RESULT_ID" ]; then
  echo "    No results (txt) found for $VERIFIER."
  echo
  exit
fi
echo "Results: $RESULT_ID"
rsync -axzq "$RESULTSVERIFICATION/$VERIFIER.results.$COMPETITION.table.html.gz" "$TARGET"
rsync -axzq "$RESULTSVERIFICATION/$VERIFIER.list.html" "$TARGET"
rsync -axzq --dirs --no-recursive --include="$RESULT_ID.*.html.gz" --exclude="*" "$SOURCE" "$TARGET"
rsync -axzq --dirs --no-recursive --include="$RESULT_ID.*.xml.bz2" --exclude="*" "$SOURCE" "$TARGET"
rsync -axzq --dirs --no-recursive --include="$RESULT_ID.*.zip"     --exclude="*" "$SOURCE" "$TARGET"
rsync -axzq --dirs --no-recursive --include="$RESULT_ID.*.txt"     --exclude="*" "$SOURCE" "$TARGET"
rsync -axzq --dirs --no-recursive --include="$RESULT_ID.*.json"    --exclude="*" "$SOURCE" "$TARGET"

echo "... $RESULTSVALIDATION"
SOURCE="$PATHPREFIX/$RESULTSVALIDATION/"
TARGET="www-comp.sosy.ifi.lmu.de:/srv/web/data/$TARGETDIR/$YEAR/results/$RESULTSVALIDATION/"
for VALIDATION in $VALIDATORLIST; do
  RESULT_ID=$(latest_matching_filename "$RESULTSVALIDATION/$VALIDATION-$VERIFIER.????-??-??_??-??-??.results.*txt" | sed -e "s#^.*/##" -e "s/\.results\..*txt$//")
  if [ -z "$RESULT_ID" ]; then
    echo "    No results (txt) found for $VALIDATION-$VERIFIER."
    continue
  fi
  echo "Results: $RESULT_ID"
  rsync -axzq --dirs --no-recursive --include="$RESULT_ID.*.xml.bz2" --exclude="*" "$SOURCE" "$TARGET"
  rsync -axzq --dirs --no-recursive --include="$RESULT_ID.*.zip"     --exclude="*" "$SOURCE" "$TARGET"
  rsync -axzq --dirs --no-recursive --include="$RESULT_ID.*.txt"     --exclude="*" "$SOURCE" "$TARGET"
  rsync -axzq --dirs --no-recursive --include="$RESULT_ID.*.json"    --exclude="*" "$SOURCE" "$TARGET"
done

echo "... backup of results"
rsync -a "www-comp:/srv/web/data/$TARGETDIR/$YEAR/" "/data/backup/competitions/backup/$TARGETDIR/$YEAR/"
echo

