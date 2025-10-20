#!/bin/bash

# Assemble links for the e-mails and send result e-mails
# Uses the file 'mkRunMailResults-MailText.txt' as template mail text.

source "$(dirname "$0")"/../configure.sh

VERIFIER=$1;

LETTERTEXT=$(cat "$(dirname "$0")"/../prepare_tables/mkRunMailResults-MailText.txt);

if [[ $VERIFIER == "" ]]; then
  exit;
fi

echo "Sending e-mail for $VERIFIER";
if [[ ! -e ${PATHPREFIX}/${BENCHMARKSDIR}/${VERIFIER}.xml ]]; then
  echo "No benchmark defintion found for verfier $VERIFIER.";
  exit
fi

cd "$PATHPREFIX"/"$RESULTSVERIFICATION" || exit
TMP_FILE_LETTERTEXT=$(mktemp --suffix=-lettertext.txt)
echo "${LETTERTEXT}

HTML tables:
$(echo "$VERIFIER".results."$COMPETITION".table.html.gz \
                   | sed "s/ /\n/g" | sort --reverse | sed -e "s#^\./##" -e "s/^\(.*\)\.gz$/https:\/\/$TARGETSERVER.sosy-lab.org\/$YEAR\/results\/results-verified\/\1/")
$(echo "$VERIFIER".????-??-??_??-??-??.results."$COMPETITION"_*.xml.bz2.table.html.gz \
                   | sed "s/ /\n/g" | sort --reverse | sed -e "s#^\./##" -e "s/^\(.*\)\.gz$/https:\/\/$TARGETSERVER.sosy-lab.org\/$YEAR\/results\/results-verified\/\1/")

XML data:
$(echo "$VERIFIER".????-??-??_??-??-??.results."$COMPETITION"*.xml.bz2 \
                   | sed "s/ /\n/g" | sort --reverse | sed -e "s#^\./##" -e "s/^\(.*\)$/https:\/\/$TARGETSERVER.sosy-lab.org\/$YEAR\/results\/results-verified\/\1/")

Log archives:
$(echo "$VERIFIER".????-??-??_??-??-??.logfiles.zip \
                   | sed "s/ /\n/g" | sort --reverse | sed -e "s#^\./##" -e "s/^\(.*\)$/https:\/\/$TARGETSERVER.sosy-lab.org\/$YEAR\/results\/results-verified\/\1/")
" > "$TMP_FILE_LETTERTEXT";

cd "$PATHPREFIX" || exit
ERROR=""
for FILE in "$RESULTSVERIFICATION"/"$VERIFIER".????-??-??_??-??-??.results."$COMPETITION"*.xml.bz2; do
  RESULT="$("$SCRIPT_DIR"/prepare_tables/mkRunCheckResults.sh "$FILE")"
  ERROR="${ERROR}${RESULT}"
done
for FILE in "$RESULTSVALIDATION"/*-validate-*witnesses-"$VERIFIER".????-??-??_??-??-??.results."$COMPETITION"*.xml.bz2; do
  #if [[ ! "$FILE" =~ "BitVector" ]]; then
  #  continue
  #fi
  RESULT="$("$SCRIPT_DIR"/prepare_tables/mkRunCheckResults.sh "$FILE")"
  #echo $RESULT
  ERROR="${ERROR}${RESULT}"
done
if [ -n "$ERROR" ]; then
  ERROR="\n!!! This execution run FAILED for technical reasons and the *results are invalid*.\n    Please contact the organizer.\n\n"$ERROR
fi

MEMBER=$(yq --raw-output ".competition_participations [] | select(.competition == \"$COMPETITIONNAME $YEAR\" and .track == \"$TRACK\") | .jury_member.name" "$PATHPREFIX/fm-tools/data/$VERIFIER.yml")
VERIFIERNAME=$(yq --raw-output ".name" "$PATHPREFIX/fm-tools/data/$VERIFIER.yml")
echo "Looking up e-mail address for $MEMBER."
EMAILENTRY=$(grep "$MEMBER" "$ADDRESS_BOOK")
EMAIL=${EMAILENTRY%>*}
EMAIL=${EMAIL#*<}
if [ -z "$EMAIL" ]; then
  ERROR="E-mail address not found for $MEMBER."
fi
if [[ $(yq --raw-output ".competition_participations [] | select(.competition == \"$COMPETITIONNAME $YEAR\" and .track == \"$TRACK\") | .label? []?" "$PATHPREFIX/fm-tools/data/$VERIFIER.yml") =~ "inactive" ]]; then
  echo "Not sending e-mail to contact for inactive tool $VERIFIER."
  EMAIL="$ORGANIZER_EMAIL"
  MEMBER="$ORGANIZER_NAME"
fi
CMD="cat"
if [ "${2:-}" == "--really-send-email" ]; then
  CMD="sendmail -f $ORGANIZER_EMAIL $ORGANIZER_EMAIL $RESULTS_OBSERVERS $EMAIL"
fi
echo "Sending mail to $EMAIL ... with $CMD"

sed   -e "s/___NAME___/$MEMBER/g" \
      -e "s/___EMAIL___/$EMAIL/g" \
      -e "s/___OBSERVERS___/$RESULTS_OBSERVERS/g" \
      -e "s#___VERIFIER___#$VERIFIERNAME#g" \
      -e "s/___VERIFIERXML___/$VERIFIER.xml/g" \
      -e "s#___ERROR___#$ERROR#g" \
      -e "s/___COMPETITIONNAME___/$COMPETITIONNAME/g" \
      -e "s/___YEAR___/$YEAR/g" \
      -e "s/___TARGETSERVER___/$TARGETSERVER/g" \
      -e "s/___LIMITSTEXT___/$LIMITSTEXT/g" \
      -e "s/___RESULTSLEVEL___/$RESULTSLEVEL/g" \
  "$TMP_FILE_LETTERTEXT" \
| $CMD
rm "$TMP_FILE_LETTERTEXT"

