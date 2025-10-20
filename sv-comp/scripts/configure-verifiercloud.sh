#!/bin/bash

# Add this file (or symlink it) as ~/.competition-configure-verifiercloud.sh if you want to execute run collections on a VerifierCloud.

BENCHMARKSCRIPT="$(dirname "$0")/../../benchexec/contrib/vcloud-benchmark.py"
VERIFIERCLOUDOPTIONS="--vcloudAdditionalFiles . --vcloudClientHeap 20000 --cgroupAccess --no-ivy-cache"

OPTIONSVERIFY="--vcloudPriority HIGH $OPTIONSVERIFY"
OPTIONSVALIDATE="--vcloudPriority URGENT $OPTIONSVALIDATE"

