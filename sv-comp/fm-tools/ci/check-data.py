#!/usr/bin/env python3
import argparse
import logging
import sys
from collections import Counter
from pathlib import Path

import _ciutil as ciutil
import httpx
import jsonschema
import yaml


def _load_yaml(path: Path):
    with open(path, "r") as file:
        return yaml.safe_load(file)


def _check_gitlab_handle(handle: str, tool_name: str, client: httpx.Client):
    url = "https://gitlab.com/api/v4/users"
    if handle.startswith("https://gitlab.com/"):
        handle = handle[len("https://gitlab.com/") :]
    params = {"username": handle}

    response = client.get(url, params=params)

    if response.status_code != 200:
        logging.error(
            f"{tool_name}: Bad request response status. Expected 200, got '{response.status_code}'."
        )
        return False
    data = response.json()
    if not data:
        logging.error(f"{tool_name}: Could not find gitlab handle '{handle}'.")
        return False
    return True


def check_handles(yaml_data, tool_name: str):
    try:
        client = httpx.Client(http2=True)
        handles = yaml_data["fmtools_entry_maintainers"]
        if not handles:
            logging.error("No 'fmtools_entry_maintainers' found.")
            return False
        success = True
        for handle in yaml_data["fmtools_entry_maintainers"]:
            success &= _check_gitlab_handle(handle, tool_name, client)
        return success
    finally:
        client.close()


def validate_no_repetitions_in_techniques(yaml_data, tool_name):
    count = Counter(yaml_data["techniques"])
    success = True
    for k, v in count.items():
        if v > 1:
            ciutil.error(f"{tool_name}: Repeated entry {k} in 'techniques'.")
            success = False
    return success


def _request_benchmark_def(benchmark_url: str, client: httpx.Client):
    try:
        r = client.get(benchmark_url, headers={"User-Agent": "Mozilla/5.0"})
        return (r.status_code == 200, r.text)
    except httpx.RequestError:
        return (False, None)
    except httpx.HTTPStatusError:
        return (False, None)


def check_require_doi(yaml_data, tool: str):
    participations = yaml_data["competition_participations"]
    for participation in participations:
        if int(participation["competition"].split(" ")[1]) >= 2024:
            for version in yaml_data["versions"]:
                if version["version"] == participation["tool_version"]:
                    if "url" in version:
                        ciutil.error(
                            f"{tool}: From 2024 all tools must upload their tools to zenodo.org and provide an DOI instead of an URL. The URL tag is forbidden."
                        )
                        return False
                    if "doi" not in version:
                        ciutil.error(
                            f"{tool}: From 2024 all tools must upload their tools to zenodo.org and provide an DOI instead of an URL."
                        )
                        return False
    return True


def check_participation(yaml_data, tool: str, year: int):
    participations = yaml_data["competition_participations"]
    for participation in participations:
        if participation["competition"].endswith(f"{year}"):
            competition = participation["competition"].split(" ")[0]
            for version in yaml_data["versions"]:
                if version["version"] == participation["tool_version"]:
                    ciutil.info(
                        f"{tool}: Found version '{participation['tool_version']}' for competition '{competition} {year}'."
                    )
                    return True
            ciutil.error(
                f"{tool}: The tool listed a participation for {competition} {year} but the version {participation['tool_version']} is not listed in the versions."
            )
            return False
    ciutil.info(f"{tool} does not participate in {year}")
    return True


def validate_property_order(yaml_data, tool_path: Path, schema: dict) -> bool:
    expected_order = [
        "id",
        "name",
        "input_languages",
        "project_url",
        "repository_url",
        "spdx_license_identifier",
        "benchexec_toolinfo_module",
        "fmtools_format_version",
        "fmtools_entry_maintainers",
        "maintainers",
        "versions",
        "competition_participations",
        "techniques",
        "frameworks_solvers",
        "literature",
    ]

    all_expected_keys = set(expected_order)
    all_schema_keys = set(schema["properties"].keys())
    all_schema_keys.remove("licenses")
    all_schema_keys.remove("description")
    all_schema_keys.remove("used_actors")

    if all_schema_keys != all_expected_keys:
        ciutil.error(
            f"{tool_path}: Schema contains more keys than listed in expected order: {all_schema_keys.difference(all_expected_keys)} OR {all_expected_keys.difference(all_schema_keys)}."
        )

    yaml_keys = list(yaml_data.keys())
    required_keys = frozenset(schema["required"])

    missing_properties = [prop for prop in required_keys if prop not in yaml_keys]
    extra_properties = set(yaml_keys) - set(schema["properties"].keys())

    validated = True

    if missing_properties:
        ciutil.error(f"{tool_path}: Properties {missing_properties} missing.")
        validated = False
    if extra_properties:
        ciutil.error(f"{tool_path}: Properties {extra_properties} must be removed.")
        validated = False

    required_order = [key for key in expected_order if key in required_keys]
    required_keys_in_order = [key for key in yaml_keys if key in required_keys]
    if (
        required_keys_in_order != required_order
        and not missing_properties
        and not extra_properties
    ):
        ciutil.error(
            f"{tool_path}: Properties must follow the given order {expected_order}"
        )
        validated = False

    return validated


def main(args):
    try:
        if args.schema.samefile(args.fm_data):
            ciutil.info(
                f"{args.schema} and {args.fm_data} are the same file."
                " Skipping this check."
            )
            return
        schema = _load_yaml(args.schema)
        yaml_data = _load_yaml(args.fm_data)
        status = validate_property_order(yaml_data, args.fm_data, schema)
        # we assume that all competition names match the regex `(SV-COMP|Test-Comp) 20[2-9][0-9]$`
        validator = jsonschema.validators.validator_for(schema)(schema)
        errors = sorted(validator.iter_errors(yaml_data), key=lambda e: e.path)
        if len(errors) > 0:
            ciutil.error(f"{args.fm_data} does not match the schema:")
            for error in errors:
                ciutil.error(str(error) + "\n", label="    VALIDATION ERROR")
            status = False
        status &= validate_no_repetitions_in_techniques(yaml_data, args.fm_data)
        status &= check_participation(yaml_data, args.fm_data, args.year)
        status &= check_require_doi(yaml_data, args.fm_data)
        status &= check_handles(yaml_data, args.fm_data)
        if status:
            ciutil.info(f"{args.fm_data} matches the schema.")
            sys.exit(0)
        sys.exit(1)
    except jsonschema.exceptions.SchemaError as e:
        ciutil.error(
            f"The provided schema is wrong. Please notify one of the maintainers of the repository. {e=}"
        )
    sys.exit(1)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format=None)
    parser = argparse.ArgumentParser(description="Validate YAML definitions of tools.")
    parser.add_argument(
        "--schema",
        type=Path,
        default=Path("fm-tools/data/schema.yml"),
        required=True,
        help="Path to the JSON schema file",
    )
    parser.add_argument(
        "--fm-data", type=Path, required=True, help="Path to the YAML tool file"
    )
    parser.add_argument(
        "--year", type=int, required=True, help="Competition year (e.g., 2024)"
    )
    args = parser.parse_args()
    main(args)
