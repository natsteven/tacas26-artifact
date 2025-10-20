#!/usr/bin/env python3

from datetime import datetime
import argparse
from pathlib import Path
import bz2
import xml.etree.ElementTree as ET
from collections import defaultdict
import os
import sys

sys.dont_write_bytecode = True  # Prevent creation of .pyc files

"""
for each subcategory c, and for each verifier v:
    create a BenchExec results XML file for subcategory c and verifier 'virtual-best",
    from the given input files `v.*c.*.xml.bz2`,
    which contains the best result (correct status, min. CPU time)

Usage: python3 virtual_best_verifiers.py --in-dir <input_dir> --out-dir <output_dir> -t <tool1> -t <tool2>
"""


def parse_args(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--in-dir",
        "-i",
        metavar="in_dir",
        required=True,
        help="Directory containing result files (*.fixed.xml.bz2).",
    )
    parser.add_argument(
        "--out-dir",
        "-o",
        metavar="out_dir",
        required=True,
        help="Directory to put the new result files.",
    )
    parser.add_argument(
        "--tool",
        "-t",
        action="append",
        metavar="tool",
        help="Tool to consider (can be repeated)",
    )
    return parser.parse_args(argv)


# The list of allowed columns
ALLOWED_COLUMNS = {"cputime", "memory", "status", "walltime", "category"}


def parse_benchexec_results(xml_content):
    """
    Parse the XML content of a BenchExec result file.
    Collate data by the 'name' and 'properties' attributes of the <run> tag,
    and select the lowest CPU time for correct categories. Include non-correct runs with no columns if necessary.
    """
    print("Parsing XML content...")
    # Parse the XML content
    root = ET.fromstring(xml_content)

    # Get the benchmarkname (the tool name)
    benchmarkname = root.get("benchmarkname")

    # Dictionary to store data by 'name' and 'properties'
    results = defaultdict(
        lambda: {
            "cputime": float("inf"),
            "run_element": None,
            "benchmarkname": benchmarkname,
            "any_run_element": None,  # Track any run in case no correct category exists
        }
    )

    # Iterate over all <run> tags
    for run in root.findall("run"):
        name = run.get("name")
        properties = run.get("properties")
        key = (name, properties)
        category = None
        cputime = None

        # Find the relevant <column> tags inside <run>
        for column in run.findall("column"):
            title = column.get("title")
            if title == "category":
                category = column.get("value")
            if title == "cputime":
                try:
                    # Convert the cputime string (e.g., '1.695473894s') to a float
                    cputime = float(column.get("value").replace("s", ""))
                except ValueError as e:
                    # This should never happen, as long as Benchexec output well-formed values
                    print(
                        f"Failed to set value: could not parse {column.get('value')} due to the following error: {e}"
                    )
                    cputime = None

        # Store the first encountered run for each key (if no correct category exists)
        if results[key]["any_run_element"] is None:
            results[key]["any_run_element"] = run

        # Only consider runs with correct categories
        if category == "correct" and cputime is not None:
            # Keep the run with the lowest CPU time for each (name, properties)
            if cputime < results[key]["cputime"]:
                results[key]["cputime"] = cputime
                results[key]["run_element"] = run

    return results, root.get("memlimit"), root.get("timelimit"), root.get("cpuCores")


def filter_columns(run_element):
    """
    Filter the columns in the <run> element to keep only specific columns (cputime, memory, status, walltime, category).
    """
    for column in list(run_element.findall("column")):
        if column.get("title") not in ALLOWED_COLUMNS:
            run_element.remove(column)


def create_collated_xml(results, benchmarkname, memlimit, timelimit, cpuCores):
    """
    Create a new XML tree from the collated results.
    Add a new <column> for the tool name (benchmarkname), and set the appropriate
    memlimit, timelimit, and cpuCores in the <result> attributes.
    """
    print(f"Creating collated XML for tool: {benchmarkname}...")

    # Create the root <result> element with attributes for the benchmark and limits
    root = ET.Element(
        "result",
        attrib={
            "benchmarkname": "virtual-best",
            "tool": "Virtual Best",
            "version": "SV-COMP'25",
            "date": str(datetime.now()),
            "memlimit": memlimit if memlimit else "",
            "timelimit": timelimit if timelimit else "",
            "cpuCores": cpuCores if cpuCores else "",
        },
    )

    # Add <run> elements from the collated results, and append the tool name as a new column
    for key, data in results.items():
        run_element = data["run_element"]

        # If no "correct" run is found, use the first encountered run (without any columns)
        if run_element is None and data["any_run_element"] is not None:
            any_run_element = data["any_run_element"]
            # Remove all <column> elements
            for column in any_run_element.findall("column"):
                any_run_element.remove(column)
            root.append(any_run_element)

        if run_element is not None:
            filter_columns(run_element)
            # Create a new <column> for the tool name, if it's a correct run
            if data["cputime"] != float("inf"):
                tool_column = ET.Element(
                    "column", attrib={"title": "tool", "value": data["benchmarkname"]}
                )
                # Append the tool column to the <run> element
                run_element.append(tool_column)
            # Append the <run> element to the root
            root.append(run_element)

    return root


def select_for_virtual_best(xml_content):
    """
    Returns 'True' for any tool we wish to include in the virtual-best selection
    (e.g., has positive scores, no overwhelming wrong results, is active, etc.)
    Right now we select all tools, this function is only here for easier future development.
    """
    return True


def process_files(input_dir, output_dir, tools=None, fixed_only=False):
    """
    Process the folder containing .xml.bz2 files, parse them, and collate results.
    Generate separate XMLs based on the file suffix.
    If tools is None, consider all tools. Otherwise consider only tools within `tools`.
    """
    print(f"Using folder: {input_dir}")
    # Dictionary to collect results by suffix
    # This will map suffixes to dictionaries which map keys to 'cputime', 'run_element', 'benchmarkname', and 'any_run_element'.
    #  - run_element is the full <run ..> .. </run> element if the category of the run is 'correct', in which case 'cputime' is set to a value lower than inf.
    #  - benchmarkame is the tool name
    #  - any_run_element is the full <run ..> .. </run> element, which is set event when category is not 'correct'. In this case cputime is inf. This is useful for including a placeholder <run> even in the case when no tool solves a task.
    collated_results_by_suffix = defaultdict(
        lambda: defaultdict(
            lambda: {
                "cputime": float("inf"),
                "run_element": None,
                "benchmarkname": None,
                "any_run_element": None,
            }
        )
    )

    # Variables to store memlimit, timelimit, and cpuCores (taken from any of the files)
    memlimit, timelimit, cpuCores = None, None, None

    pattern = f"*{'fixed' if fixed_only else ''}.xml.bz2"
    xmls = list(map(str, Path(input_dir).glob(pattern)))
    if tools and len(tools) > 0:
        xmls = list(
            filter(lambda xml: os.path.basename(xml).split(".")[0] in tools, xmls)
        )

    all_xmls = len(xmls)
    for i, file in enumerate(xmls):
        print(f"{i} / {all_xmls} Processing file: {file}")
        # Extract the suffix from the filename
        suffix = file.split(".results.")[1].split(".xml.bz2")[0]
        print(f"Processing suffix: {suffix}")

        # Extract the .xml.bz2 file content
        with open(file, "rb") as file_ref:
            # Decompress the .bz2 content
            with bz2.BZ2File(file_ref) as xml_file:
                xml_content = xml_file.read().decode("utf-8")

                if not select_for_virtual_best(xml_content):
                    continue

                # Parse the Benchexec results and also retrieve limits
                results, file_memlimit, file_timelimit, file_cpuCores = (
                    parse_benchexec_results(xml_content)
                )

                # Set memlimit, timelimit, and cpuCores if not already set
                if not memlimit:
                    memlimit, timelimit, cpuCores = (
                        file_memlimit,
                        file_timelimit,
                        file_cpuCores,
                    )
                else:
                    assert (memlimit, timelimit, cpuCores) == (
                        file_memlimit,
                        file_timelimit,
                        file_cpuCores,
                    ), "Differing resource limits, aborting."

                # Collate results by suffix
                for key, data in results.items():
                    if data["cputime"] < collated_results_by_suffix[suffix][key][
                        "cputime"
                    ] or (
                        data["cputime"] == float("inf")
                        and collated_results_by_suffix[suffix][key]["cputime"]
                        == float("inf")
                    ):
                        collated_results_by_suffix[suffix][key] = data

    # Create and write separate XMLs for each suffix
    for suffix, results in collated_results_by_suffix.items():
        output_xml_path = os.path.join(output_dir, f"virtualbest_{suffix}.xml")
        print(f"Creating output XML for suffix: {suffix}")

        # Create the final collated XML tree for this suffix
        collated_xml_tree = create_collated_xml(
            results, "virtual-best", memlimit, timelimit, cpuCores
        )

        # Write the output XML with the appropriate header and DTD declaration
        print(f"Writing collated results to {output_xml_path}")
        with open(output_xml_path, "wb") as f:
            f.write(b'<?xml version="1.0" encoding="utf-8"?>\n')
            f.write(
                b"<!DOCTYPE result PUBLIC '+//IDN sosy-lab.org//DTD BenchExec result 3.0//EN'\n"
            )
            f.write(b"  'https://www.sosy-lab.org/benchexec/result-3.0.dtd'>\n")
            tree = ET.ElementTree(collated_xml_tree)
            tree.write(f, encoding="utf-8", xml_declaration=False)


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    args = parse_args(argv)
    in_dir = args.in_dir
    out_dir = args.out_dir
    tools = args.tool
    process_files(in_dir, out_dir, tools, fixed_only=True)


if __name__ == "__main__":
    sys.exit(main())
