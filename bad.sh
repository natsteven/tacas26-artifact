#!/bin/bash

for bench in automatark matching real woorpje; do
    ./remove_bad.sh "bad-$bench-filenames.txt" "util/$bench-filenames.txt"
done