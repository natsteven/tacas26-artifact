#!/usr/bin/env python3

# Check DOIs

# This file is part of fm-tools
# https://gitlab.com/sosy-lab/benchmarking/fm-tools
# SPDX-FileCopyrightText: 2024 Dirk Beyer <https://www.sosy-lab.org>
#
# SPDX-License-Identifier: Apache-2.0


import pathlib
import re
import sys

import httpx
import yaml


def get_dois(data_dir):
    for yaml_file in data_dir.glob("*.yml"):
        with open(yaml_file) as stream:
            yaml_data = yaml.safe_load(stream)
        if str(yaml_file).endswith("data/schema.yml"):
            descriptions = yaml_data["properties"]["techniques"]["items"]["oneOf"]
            descriptions += yaml_data["properties"]["techniques"]["items"]["oneOf"]
            for technique_value in descriptions:
                for line in technique_value["description"].split("\n"):
                    if "doi.org" in line:
                        yield re.sub(r".*doi.org/(.*)\)", r"\1", line)
            continue
        if "literature" not in yaml_data:
            continue
        for ver in yaml_data["versions"]:
            if "doi" in ver:
                yield ver["doi"]
        for lit in yaml_data["literature"]:
            yield lit["doi"]


def main(data_dir):
    success = True
    client = httpx.Client(http2=True)
    for doi in get_dois(data_dir):
        response = client.get(f"https://doi.org/{doi}")
        if response.status_code != 302:
            success = False
            print(f"Error with DOI '{doi}'; try https://doi.org/{doi}.")
    if not success:
        exit(1)


if __name__ == "__main__":
    data_dir = pathlib.Path(__file__).parent.parent / "data"
    sys.exit(main(data_dir))
