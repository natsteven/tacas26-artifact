#!/bin/bash

# Run A-Str on a json or smt2 file passed as argument
if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <file.json|file.smt2>"
  exit 1
fi

input_file="$1"

if [[ ! -f $input_file ]]; then
  echo "Error: File $input_file does not exist."
  exit 1
fi

# Run the A-Str solver
if [[ $input_file == *.smt2 ]]; then
  # Convert smt2 to json first
  temp_json="$(mktemp --suffix=.json)"
  ./util/getsmt.sh "$input_file" "$temp_json"
  if [[ ! -f $temp_json ]]; then
    echo "Error: Conversion to JSON failed."
    exit 1
  fi
  ./scripts/a-str.sh "$temp_json"
  rm "$temp_json"
else
    ./scripts/a-str.sh "$input_file"
fi