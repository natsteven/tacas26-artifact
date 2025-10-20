#!/usr/bin/env python3

# Generate a table definition for BenchExec's table generator.
# ../benchexec/bin/table-generator --no-diff --format html --xml <table-def>.xml

import argparse
import sys
import os
import yaml
import coloredlogs
import logging
from pathlib import Path

from fm_tools.competition_participation import Competition
from fm_tools.fmtoolscatalog import FmToolsCatalog
from prepare_tables.utils import (
    competition_from_string,
    find_latest_file_verifier,
    find_latest_file_validator,
    validators_of_competition,
)


def generate_table_def(category_structure: Path, verifier: str, tools: FmToolsCatalog):
    with open(category_structure) as f:
        cat_def = yaml.load(f, Loader=yaml.Loader)
    main_dir = category_structure.parent.parent
    logging.info("Creating table-definition entries ...")
    subcategories = []
    for category in cat_def["categories_table_order"]:
        if "." in category:
            subcategories.append(category)

    year_full = cat_def["year"]
    year = str(year_full)[-2:]
    competition = competition_from_string(cat_def["competition"])
    header = (
        '<?xml version="1.0" ?>\n'
        + '<!DOCTYPE table PUBLIC "+//IDN sosy-lab.org//DTD BenchExec table 1.0//EN" "http://www.sosy-lab.org/benchexec/table-1.0.dtd">\n'
        + "<table>\n"
    )
    columns = '    <column title="status"/>\n'
    if competition == Competition.TEST_COMP:
        columns += '    <column title="score"/>\n'
    elif competition == Competition.SV_COMP:
        columns += '    <column title="score" displayTitle="raw score"/>\n'
    else:
        raise ValueError(f"Unknown competition {competition}")
    columns += (
        '    <column title="cputime"     numberOfDigits="2" displayTitle="cpu"/>\n'
    )
    columns += (
        '    <column title="walltime"    numberOfDigits="2" displayTitle="wall"/>\n'
    )
    columns += '    <column title="memory"      numberOfDigits="2" displayTitle="mem"     displayUnit="MB" sourceUnit="B"/>\n'
    columns_no_score = '    <column title="status"/>\n'
    if competition == Competition.TEST_COMP:
        columns_no_score += (
            '    <column title="branches_covered" displayTitle="cov"/>\n'
        )
    columns_no_score += (
        '    <column title="cputime"     numberOfDigits="2" displayTitle="cpu"/>\n'
    )
    columns_no_score += (
        '    <column title="walltime"    numberOfDigits="2" displayTitle="wall"/>\n'
    )
    columns_no_score += '    <column title="memory"      numberOfDigits="2" displayTitle="mem"     displayUnit="MB" sourceUnit="B"/>\n'
    table_all = open(
        main_dir
        / "results-verified"
        / f"{verifier}.results.{competition.value}{year}.xml",
        "w",
    )
    table_all.write(header + "\n")

    table_all.write(f"  <!-- Verifier {verifier} -->\n")
    table_all.write(f'  <union title="{verifier} ...">\n')
    table_all.write(columns + "\n")

    for subcategory in subcategories:
        result_file = find_latest_file_verifier(
            verifier,
            subcategory,
            competition=competition,
            year=year,
            dir=main_dir / "results-verified",
        )
        if result_file is not None and os.path.exists(result_file):
            # TODO: if at least one '/result/run' is in XML file,
            #       else log "INFO: Empty results file found for this property and category"
            table_all.write(
                f"    <result filename='{os.path.relpath(result_file, main_dir / 'results-verified')}'/>\n"
            )
        else:
            logging.info(
                f"      No verification results found for verifier {verifier} and category {subcategory}"
            )
    table_all.write("  </union>\n")
    table_all.write("\n")
    for validation in validators_of_competition(tools, competition, year_full):
        table_all.write(f"  <!-- Validator {validation} -->\n")
        table_all.write(f'  <union title="{validation} ...">\n')
        table_all.write(columns_no_score + "\n")
        for subcategory in subcategories:
            result_file = find_latest_file_validator(
                validation,
                verifier,
                subcategory,
                competition,
                year=year,
                output=main_dir / "results-validated",
            )
            if result_file is not None and os.path.exists(result_file):
                # TODO: if at least one '/result/run' is in XML file,
                #       else log "INFO: Empty results file found for this property and category"
                table_all.write(
                    f"    <result filename='{os.path.relpath(result_file, main_dir / 'results-verified')}'/>\n"
                )
            else:
                logging.info(
                    f"      No verification results found for validator {validation} and category {subcategory}"
                )
        table_all.write("  </union>\n")
        table_all.write("\n")
    table_all.write("</table>\n")

    logging.info("Done creating table-definition files.")


def main():
    coloredlogs.install(fmt="%(levelname)s %(process)s %(name)s %(message)s")

    parser = argparse.ArgumentParser(description="Create table definitions.")
    parser.add_argument(
        "--category-structure",
        type=Path,
        required=True,
        help="YAML file defining the category structure",
    )
    parser.add_argument(
        "--fm-tools",
        type=Path,
        default=Path("fm-tools"),
        help="Path to fm-tools",
    )
    parser.add_argument("verifier", type=str, help="Verifier to generate tables for")
    args = parser.parse_args()

    generate_table_def(
        args.category_structure, args.verifier, FmToolsCatalog(args.fm_tools)
    )


if __name__ == "__main__":
    sys.exit(main())
