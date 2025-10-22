#!/bin/bash

bad="$1"
logs_file="$2"
# times_file="$3"

# based on filenames, remove files from logs and times files
readarray -t bad_benches < "$bad"
if [[ ! -f "$logs_file" ]]; then
    echo "Logs file $logs_file does not exist."
    exit 1
fi
# if [[ ! -f "$bad" ]]; then
#     echo "Bad file $bad does not exist."
#     exit 1
# fi

for bench in "${bad_benches[@]}"; do
    sed -i "/${bench%.smt2}/d" "$logs_file"
    sed -i "/${bench%.smt2}/d" "$times_file"
done

