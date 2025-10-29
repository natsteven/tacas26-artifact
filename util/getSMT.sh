#!/bin/bash

if [[ $# < 1 || $# > 2 ]]; then
    echo "Usage: $0 <directory or file path> [optional: output path]"
    exit 1
fi

java -cp A-Str/tools/smtlib-converter.jar edu.boisestate.cs.MainJSON $@
