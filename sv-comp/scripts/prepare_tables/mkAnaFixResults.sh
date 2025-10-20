#!/bin/bash

for i in results-verified/goblint*.xml.bz2; do 
  FILE="${i%%.bz2}"
  echo "Processing $FILE"
  bzip2 -d "$FILE.bz2"
  xmlstarlet edit -L --update "/result/@version" --value "svcomp21-0-g82e03b87" "$FILE"
  bzip2 -9 "$FILE"
	
  #input=$(bzcat "$i")
  #input=$(sed 's/error="missing results" //' <<< "$input")
  #echo "$input" | bzip2 -9 > "$i.tmp"
  #mv "$i.tmp" "$i"
done
