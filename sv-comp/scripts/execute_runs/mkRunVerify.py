#!/usr/bin/env python3

import argparse
import sys
import subprocess


def parse(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--job-number",
        type=int,
        default=0,
        help="job number of this verifier run. Should be provided in case of concurrent executions and be set to a different value for each execution.",
    )
    parser.add_argument(
        "verifier",
        help="Verifier to run. Must be 'ALL' or correspond to a verifier name provided in directory 'benchmarks/'.",
    )

    args = parser.parse_args(argv)
    if args.verifier != "ALL":
        args.verifier = args.verifier.lower()

    return args


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    args = parse(argv)
    cmd = ["scripts/mkRunVerify.sh", args.verifier]
    if args.job_number is not None:
        cmd.append(str(args.job_number))
    process = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True
    )
    try:
        for p in process.stdout:
            print(p, end="")
    finally:
        process.stdout.close()


if __name__ == "__main__":
    sys.exit(main())
