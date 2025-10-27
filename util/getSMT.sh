#!/bin/bash

if [[ $# < 1 || $# > 2 ]]; then
    echo "Usage: $0 <directory or file path> [optional: output path]"
    exit 1
fi

java -cp smt-lib-gen.jar edu.boisestate.cs.MainJSON $@
