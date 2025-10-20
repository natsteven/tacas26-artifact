#!/bin/bash

# This file is part of the competition environment.
#
# SPDX-FileCopyrightText: 2011-2025 Dirk Beyer <https://www.sosy-lab.org>
#
# SPDX-License-Identifier: Apache-2.0

# Generate table definitions.


DIR="$(realpath "$(dirname "$0")")"
source "$DIR"/../configure.sh
CATEGORY_STRUCTURE="$DIR/../../benchmark-defs/category-structure.yml"
YEAR=$(yq --raw-output '.year' "$CATEGORY_STRUCTURE")
COMPETITIONNAME=$(yq --raw-output '.competition' "$CATEGORY_STRUCTURE")
MAIN_TRACK="Verification"
if [[ "$COMPETITIONNAME" == "Test-Comp" ]]; then
  MAIN_TRACK="Test Generation"
fi

DOCREATESINGLECATEGORY="YES";

COLUMNSSINGLE='
<column title="status"/>
<column title="score" displayTitle="raw score"/>
<column title="cputime"   numberOfDigits="2" displayTitle="cpu"/>
<column title="memory"  numberOfDigits="2" displayTitle="mem"    displayUnit="MB" sourceUnit="B"/>
<column title="cpuenergy" numberOfDigits="2" displayTitle="energy" displayUnit="J"  sourceUnit="J"/>
';
COLUMNSMETA='
<column title="status"/>
<column title="score" displayTitle="raw score"/>
<column title="cputime"   numberOfDigits="2" displayTitle="cpu"/>
<column title="memory"  numberOfDigits="2" displayTitle="mem"    displayUnit="MB" sourceUnit="B"/>
<column title="cpuenergy" numberOfDigits="2" displayTitle="energy" displayUnit="J"  sourceUnit="J"/>
';

cd ${PATHPREFIX}/${RESULTSVERIFICATION}


VERIFIERS=$(yq --raw-output --slurp "map( select( .competition_participations[]?
                                                  | .competition==\"$COMPETITIONNAME $YEAR\" and .track==\"$MAIN_TRACK\"
                                                )
                                        )
                                     | sort_by([.input_languages[0], .id]) [] .id" \
                "$DIR"/../../fm-tools/data/*.yml)

CATEGORIES=$(yq -r "[.categories | to_entries [] | .value | .categories []] | sort | unique [] | select(contains(\".\"))" "$CATEGORY_STRUCTURE")

CATEGORIES_FALSIFICATION=$(yq -r "[.categories | to_entries [] | .value | .categories []] | sort | unique [] | select(contains(\".\"))" \
                          "$CATEGORY_STRUCTURE" | grep -v Termination)

# Create category-map file
yq -r ".categories | to_entries [] | [.key, (.value | .categories | join(\" \"))] | join(\":\")" \
      "$CATEGORY_STRUCTURE" | grep -v "^Overall$\|^FalsificationOverall$" > CATEGORIES.txt
echo "Overall: $(echo $CATEGORIES | xargs)" >> CATEGORIES.txt
if [[ "$COMPETITIONNAME" == "SV-COMP" ]]; then
  echo "FalsificationOverall: $(echo $CATEGORIES_FALSIFICATION | xargs)" >> CATEGORIES.txt
fi

# Single Categories
if [[ "${DOCREATESINGLECATEGORY}" == "YES" ]]; then
  for CAT in $CATEGORIES; do
    if [[ ! "$CAT" =~ "-" ]]; then
      continue;
    fi
    echo "Processing category $CAT";
    OUTPUT_FILE=$CAT.xml
    echo "<?xml version='1.0' ?>" > $OUTPUT_FILE
    echo "<table>${COLUMNSSINGLE}" >> $OUTPUT_FILE
    for VERIFIER in $VERIFIERS; do
        echo $VERIFIER
        RESULT=$(latest_matching_filename "$VERIFIER.????-??-??_??-??-??.results.${COMPETITION}_$CAT*.xml.bz2")
        if [ -e "$RESULT" ]; then
            echo "<result filename='$RESULT'/>" >> $OUTPUT_FILE
        fi
      done
    echo "</table>" >> $OUTPUT_FILE
  done
fi

# Unioned Categories
yq -r ".categories | to_entries [] | [.key, (.value | .verifiers | join(\" \"))] | join(\":\")" \
      "$CATEGORY_STRUCTURE" \
| while read LINE; do
  METACAT=$(echo "$LINE" | cut -d ':' -f 1)
  echo "Processing meta category $METACAT";
  VERIFIERS=$(echo "$LINE" | cut -d ':' -f 2)
  OUTPUT_FILE="META_${METACAT}.xml";
  echo "<?xml version='1.0' ?>" > $OUTPUT_FILE
  echo "<table>${COLUMNSMETA}" >> $OUTPUT_FILE
  for VERIFIER in $VERIFIERS; do
    echo "    $VERIFIER";
    echo "  <union>" >> $OUTPUT_FILE
    cat CATEGORIES.txt \
    | while read CATLINE; do
      META=$(echo "$CATLINE" | cut -d ':' -f 1)
      if [[ $META != $METACAT ]]; then
        continue;
      fi
      CATS=$(echo "$CATLINE" | cut -d ':' -f 2)
      for CAT in $CATS; do
        if [[ ! "$CAT" =~ "-" ]]; then
          continue;
        fi
        echo "        $CAT";
        RESULT=$(latest_matching_filename "$VERIFIER.????-??-??_??-??-??.results.${COMPETITION}_$CAT*.xml.bz2")
        if [ -n "$RESULT" ]; then
          echo "    <result filename='$RESULT'/>" >> $OUTPUT_FILE
        else
          echo "Result for ${VERIFIER} and ${COMPETITION}.${CAT} not found."
        fi
      done
      # Generate a table for meta category per verifier.
      OUT_META_VER=META_${METACAT}_${VERIFIER}.xml
      echo "<?xml version='1.0' ?>" > $OUT_META_VER
      echo "<table>${COLUMNSMETA}" >> $OUT_META_VER
      echo "  <union>" >> $OUT_META_VER
      for CAT in $CATS; do
        if [[ ! "$CAT" =~ "-" ]]; then
          continue;
        fi
        echo "           Meta-Category $META -- $CAT";
          FILERESULT=$(latest_matching_filename "$VERIFIER.????-??-??_??-??-??.results.${COMPETITION}_$CAT*.xml.bz2")
        if [ -e "$FILERESULT" ]; then
          echo "    <result filename='$FILERESULT'/>"  >> $OUT_META_VER;
        fi
      done
      echo "  </union>" >> $OUT_META_VER;
      echo "</table>" >> ${OUT_META_VER};
    done
    echo "  </union>" >> $OUTPUT_FILE
  done
  echo "</table>" >> $OUTPUT_FILE
done
