#!/bin/bash

BASEDIR=$(dirname "$0")/../..
CATEGORY_STRUCTURE="$BASEDIR/benchmark-defs/category-structure.yml"
YEAR=$(yq --raw-output '.year' "$CATEGORY_STRUCTURE")
COMPETITIONNAME=$(yq --raw-output '.competition' "$CATEGORY_STRUCTURE")
ADDRESS_BOOK=~/.competition-address-book.txt

yq --raw-output --slurp "map( .competition_participations[]? | select( .competition==\"$COMPETITIONNAME $YEAR\" and (.label | index(\"inactive\") | not) ) .jury_member.name ) []" "$BASEDIR"/fm-tools/data/*.yml \
  | while IFS=$'\n' read -r MEMBERNAME; do
  grep "$MEMBERNAME" "$ADDRESS_BOOK" || echo "Error: E-mail address not found for '$MEMBERNAME'."
done | sort -u

