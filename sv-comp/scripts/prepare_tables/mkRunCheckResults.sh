#!/bin/bash

# @title Make Run Check Results
# @description Processing the results produced by the run. Performs integrity checks on the xml.

FILE="$1"
#echo $FILE >&2
RESULT=""
if bzcat "$FILE" | xmlstarlet sel -t --if '/result[@error]' --output "bad" 2>/dev/null | grep -q "bad"; then
  RESULT="$RESULT Broken file (result error, results missing): $FILE\n"
fi
if [ "$RESULT" == "" ]; then
  if bzcat "$FILE" | xmlstarlet sel -t --if '/result/run[not(column)]' --output "bad" 2>/dev/null | grep -q "bad"; then
    RESULT="$RESULT Broken file (column missing): $FILE\n"
  fi
  if bzcat "$FILE" | xmlstarlet sel -t --if '/result/run/column[@title = "status" and @value = ""]' --output "bad" 2>/dev/null | grep -q "bad"; then
    RESULT="$RESULT Broken file (empty status): $FILE\n"
  fi
fi
if [ ! -z "$RESULT" ]; then
  echo "$RESULT"
fi
