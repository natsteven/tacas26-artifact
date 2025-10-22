#!/usr/bin/env python3

# Generate HTML pages for tools

# This file is part of fm-tools
# https://gitlab.com/sosy-lab/benchmarking/fm-tools
# SPDX-FileCopyrightText: 2024 Dirk Beyer <https://www.sosy-lab.org>
#
# SPDX-License-Identifier: Apache-2.0


import pathlib
import sys

import markdown
import yaml
from jinja2 import Environment, FileSystemLoader


def get_documents(doc_dir, tool_id, file_type):
    for tool_file in sorted(doc_dir.glob(f"{tool_id}*.{file_type}"), reverse=True):
        yield pathlib.PurePath(tool_file).name


def main(script_dir):
    data_dir = script_dir.parent / "data"
    presentations_dir = script_dir.parent / "presentations"
    posters_dir = script_dir.parent / "posters"
    logos_dir = script_dir.parent / "logos"
    website_dir = script_dir.parent / "website"
    env = Environment(
        loader=FileSystemLoader(script_dir / "webpage"),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    with open(data_dir / "schema.yml") as stream:
        schema_data = yaml.safe_load(stream)

    # Tools
    all_tool_data = {}
    for tool_file in data_dir.glob("*.yml"):
        if str(tool_file).endswith("data/schema.yml"):
            continue
        with open(tool_file) as stream:
            tool_data = yaml.safe_load(stream)
        tool_id = pathlib.PurePath(tool_file).name.split(".")[0]
        tool_data["presentations"] = list(
            get_documents(presentations_dir, tool_id, "pdf")
        )
        tool_data["posters"] = list(get_documents(posters_dir, tool_id, "pdf"))
        tool_data["logos"] = list(get_documents(logos_dir, tool_id, "svg"))
        all_tool_data[tool_data["name"]] = tool_data
    all_tool_data_sorted = []
    for key in sorted(all_tool_data, key=lambda x: (str.lower(x), x)):
        all_tool_data_sorted.append(all_tool_data[key])
    template = env.get_template("index.html")
    with open(website_dir / "index.html", "w") as file:
        file.write(template.render(tool_data=all_tool_data_sorted))

    # Techniques
    techniques = {}
    technique_descriptions = {}
    technique_values = schema_data["properties"]["techniques"]["items"]["oneOf"]
    for technique_value in technique_values:
        desc = technique_value["description"]
        technique_descriptions[technique_value["const"]] = desc
    for tool in all_tool_data_sorted:
        for technique in tool["techniques"]:
            if technique not in techniques:
                techniques[technique] = {}
                techniques[technique]["tools"] = []
            techniques[technique]["tools"].append(tool["name"])
            desc = technique_descriptions[technique]
            techniques[technique]["description"] = markdown.markdown(desc)
    techniques_sorted = {}
    for key in sorted(techniques):
        techniques_sorted[key] = techniques[key]
    template = env.get_template("techniques.html")
    with open(website_dir / "techniques.html", "w") as file:
        file.write(template.render(techniques=techniques_sorted))

    # Competitions
    competitions = {}
    for tool in all_tool_data_sorted:
        if "competition_participations" in tool:
            for competition in tool["competition_participations"]:
                comp = f"{competition['competition']} ({competition['track']})"
                if comp not in competitions:
                    competitions[comp] = []
                if competition["jury_member"]["name"] == "Hors Concours":
                    competitions[comp].append(tool["name"] + " (hc)")
                else:
                    competitions[comp].append(tool["name"])
    competitions_sorted = {}
    for key in sorted(competitions, key=(lambda x: len(x)), reverse=False):
        competitions_sorted[key] = competitions[key]
    template = env.get_template("competitions.html")
    with open(website_dir / "competitions.html", "w") as file:
        file.write(template.render(competitions=competitions_sorted))

    # Frameworks
    frameworks = {}
    framework_descriptions = {}
    framework_values = schema_data["properties"]["frameworks_solvers"]["items"]["oneOf"]
    for framework_value in framework_values:
        desc = framework_value["description"]
        framework_descriptions[framework_value["const"]] = desc
    for tool in all_tool_data_sorted:
        for framework in tool["frameworks_solvers"]:
            if framework not in frameworks:
                frameworks[framework] = {}
                frameworks[framework]["tools"] = []
            frameworks[framework]["tools"].append(tool["name"])
            desc = framework_descriptions[framework]
            frameworks[framework]["description"] = markdown.markdown(desc)
    frameworks_sorted = {}
    for key in sorted(frameworks, reverse=False):
        frameworks_sorted[key] = frameworks[key]
    template = env.get_template("frameworks.html")
    with open(website_dir / "frameworks.html", "w") as file:
        file.write(template.render(frameworks=frameworks_sorted))

    # Input Languages
    input_languages = {}
    for tool in all_tool_data_sorted:
        for input_language in tool["input_languages"]:
            if input_language not in input_languages:
                input_languages[input_language] = []
            input_languages[input_language].append(tool["name"])
    template = env.get_template("input_languages.html")
    with open(website_dir / "input_languages.html", "w") as file:
        file.write(template.render(input_languages=input_languages))


if __name__ == "__main__":
    script_dir = pathlib.Path(__file__).parent
    sys.exit(main(script_dir))
