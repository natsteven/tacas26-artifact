#!/usr/bin/env python3

import argparse
import itertools
from pathlib import Path
import sys
from typing import Iterable
import utils


def to_path(v: str) -> Path:
    if not (v := Path(v)).exists():
        raise ValueError(f"File or directory doesn't exist: {str(v)}")
    return v


def parse(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--results-dir-participants",
        default="results-verified",
        help="directory that contains participant runs",
    )
    parser.add_argument(
        "--results-dir-validators",
        default="results-validated",
        help="directory that contains validator runs",
    )
    parser.add_argument(
        "--category-info",
        default="benchmark-defs/category-structure.yml",
        help="category structure to check results against",
    )

    args = parser.parse_args(argv)
    args.results_dir_participants = to_path(args.results_dir_participants)
    args.results_dir_validators = to_path(args.results_dir_validators)
    args.category_info = to_path(args.category_info)
    args.category_info = utils.parse_yaml(args.category_info)

    return args


def competition_name(category_info) -> str:
    year = str(category_info["year"])[-2:]
    return category_info["competition"] + year


def verifier_results_pattern(verifier, competition, category) -> str:
    return f"{verifier}.????-??-??_??-??-??.results.{competition}_{category}.xml.bz2"


def validator_results_pattern(
    validator, witness_type, verifier, competition, category
) -> str:
    if witness_type:
        witness_type = f"{witness_type}-"  # add the missing '-'
    else:
        witness_type = ""
    return f"{validator}-validate-{witness_type}witnesses-{verifier}.????-??-??_??-??-??.results.{competition}_{category}.xml.bz2"


def check_participant_runs(results_dir, category_info) -> Iterable[str]:
    competition = competition_name(category_info)
    for info in category_info["categories"].values():
        expected_verifiers = info["verifiers"]
        for base_category in (c for c in info["categories"] if "." in c):
            for verifier in expected_verifiers:
                expected_results_pattern = verifier_results_pattern(
                    verifier, competition, base_category
                )
                existing_results = results_dir.glob(expected_results_pattern)
                if not any(existing_results):
                    yield f"Result missing for {verifier} and {base_category}"


def check_validator_runs(results_dir, category_info) -> Iterable[str]:
    competition = competition_name(category_info)
    for info in category_info["categories"].values():
        try:
            expected_validators = info["validators"]
        except KeyError:
            continue  # no validation runs for category
        expected_verifiers = info["verifiers"]
        for base_category in (c for c in info["categories"] if "." in c):
            for validator in expected_validators:
                if validator.endswith("-violation"):
                    witness_type = "violation"
                    validator = validator[: -len("-violation")]
                elif validator.endswith("-correctness"):
                    witness_type = "correctness"
                    validator = validator[: -len("-correctness")]
                else:
                    witness_type = None
                for verifier in expected_verifiers:
                    expected_results_pattern = validator_results_pattern(
                        validator, witness_type, verifier, competition, base_category
                    )
                    existing_results = results_dir.glob(expected_results_pattern)
                    if not any(existing_results):
                        yield f"Result missing for {validator}-{witness_type}, {verifier} and {base_category}"


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    args = parse(argv)

    errors = check_participant_runs(args.results_dir_participants, args.category_info)
    errors = itertools.chain(
        errors, check_validator_runs(args.results_dir_validators, args.category_info)
    )

    success = True
    for msg in errors:
        print(msg)
        success = False
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
