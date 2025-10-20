#!/bin/bash

# @title Create Witness Store
# @phase Run
# @description Creates the wirness and test suite story by calling the python script mkRunWitnessStore.py.
# TODO: what does the python script do?

source $(dirname "$0")/../configure.sh

cd ${PATHPREFIX}

date -Iseconds;
nice python3 $(dirname "$0")/mkRunWitnessStore.py ./fileByHash
date -Iseconds;

echo "Prepare maps ...";
set +e -x
zip --quiet -r -u "$HASHDIR_BASENAME.zip" "$HASHDIR_BASENAME"
date -Iseconds;
zip --quiet -r -u witnessInfoByHash.zip witnessInfoByHash
date -Iseconds;
zip --quiet -r -u witnessListByProgramHashJSON.zip witnessListByProgramHashJSON
date -Iseconds;

echo "Copy witness store to web server ...";
for ARCHIVE in ${PATHPREFIX}/*.zip; do
  rsync -txp --inplace ${ARCHIVE} www-comp.sosy.ifi.lmu.de:/srv/web/data/${TARGETDIR}/${YEAR}/results/
  date -Iseconds;
done
set -e +x
date -Iseconds;

