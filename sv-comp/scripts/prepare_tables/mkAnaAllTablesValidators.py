#!/usr/bin/env python3

# Generate a table definition for BenchExec's table generator.
# ./generate_table_def.py > table_all.xml
# ../benchexec/bin/table-generator --no-diff --format html --xml table_all.xml

import argparse
import sys
import os
import yaml
import coloredlogs
import logging
from multiprocessing import Pool
from pathlib import Path

import utils
from fm_tools.competition_participation import Competition
from fm_tools.fmtoolscatalog import FmToolsCatalog
from prepare_tables.utils import (
    validators_of_competition,
    competition_from_string,
    verifiers_of_competition,
    normalize_validator_name,
)


def wrap_get_verifiers_union(inputs):
    return get_verifiers_union(*inputs)


def get_verifiers_union(
    cat_def, fm_tools: FmToolsCatalog, validator_subcategory
) -> tuple[str, str]:
    validator, subcategory = validator_subcategory
    year_full = cat_def["year"]
    year = str(year_full)[-2:]
    competition = competition_from_string(cat_def["competition"])
    verifiers_union = ""
    for verifier in verifiers_of_competition(fm_tools, competition, year_full):
        if "C" not in fm_tools.get(verifier).input_languages:
            continue
        result_file = utils.find_latest_file_validator(
            validator,
            verifier,
            subcategory,
            Competition.SV_COMP,
            year=year,
            fixed=True,
        )
        if not result_file:
            continue
        for version in ["1.0", "2.0"]:
            correctness_linter_files = utils.find_latest_file_validator(
                f"witnesslint-validate-correctness-witnesses-{version}",
                verifier,
                subcategory,
                Competition.SV_COMP,
                year=year,
                fixed=True,
            )
            assert (
                correctness_linter_files
            ), f"WitnessLint results missing for correctness witnesses {version} for verifier {verifier} and category {subcategory}."
            violation_linter_files = utils.find_latest_file_validator(
                f"witnesslint-validate-violation-witnesses-{version}",
                verifier,
                subcategory,
                Competition.SV_COMP,
                year=year,
                fixed=True,
            )
            assert (
                violation_linter_files
            ), f"WitnessLint results missing for violation witnesses {version} for verifier {verifier} and category {subcategory}."

        if os.path.exists(result_file):
            verifiers_union += f'    <result id="{verifier}"  filename="{os.path.basename(result_file)}"/>\n'
    return validator_subcategory, verifiers_union


def generate_table_def(fm_tools: Path):
    with open("benchmark-defs/category-structure.yml") as f:
        cat_def = yaml.load(f, Loader=yaml.Loader)

    tools = FmToolsCatalog(fm_tools / "data")
    year_full = cat_def["year"]
    year = str(year_full)[-2:]
    competition = competition_from_string(cat_def["competition"])

    validators_with_postfix = validators_of_competition(
        tools, competition, year_full, include_postfix=True
    )

    logging.info("Creating table-definition entries ...")
    subcategories = []
    for category in cat_def["categories"]:
        if "Overall" in category:
            continue
        subcategories += cat_def["categories"][category]["categories"]
    worklist = (
        (cat_def, tools, (validator, subcategory))
        for validator in validators_with_postfix
        for subcategory in subcategories
    )
    with Pool(processes=os.cpu_count()) as p:
        verifier_unions = dict(p.map(wrap_get_verifiers_union, worklist))

    logging.info("Writing table definition files ...")
    header = (
        '<?xml version="1.0" ?>\n'
        + '<!DOCTYPE table PUBLIC "+//IDN sosy-lab.org//DTD BenchExec table 1.0//EN" "http://www.sosy-lab.org/benchexec/table-1.0.dtd">\n'
        + "<table>\n"
        + '  <column title="status"                         displayTitle="Status"/>\n'
        + '  <column title="score"                          displayTitle="Raw Score"/>\n'
        + '  <column title="witnesslint-witness-type"       displayTitle="Witness Type"/>\n'
        + '  <column title="cputime"     numberOfDigits="2" displayTitle="CPU"/>\n'
        + '  <column title="memory"      numberOfDigits="2" displayTitle="Mem"     displayUnit="MB" sourceUnit="B"/>\n'
    )
    validation_kinds = [
        "validate-correctness-witnesses-1.0",
        "validate-correctness-witnesses-2.0",
        "validate-violation-witnesses-1.0",
        "validate-violation-witnesses-2.0",
    ]
    tables_sub = dict()
    for subcategory in cat_def["categories_table_order"]:
        if "Overall" in subcategory:
            continue
        for kind in validation_kinds:
            tables_sub[f"{kind}.{subcategory}"] = open(
                f"results-validated/{kind}.results.{competition.value}{year}_{subcategory}.xml",
                "w",
            )
            tables_sub[f"{kind}.{subcategory}"].write(header + "\n")

    for validator in validators_with_postfix:
        if "C" not in tools.get(normalize_validator_name(validator)).input_languages:
            # TODO: Dangerous, what if validator has multiple input languages but xml is for Java?
            continue
        table_val = open(
            f"results-validated/{validator}.results.{competition.value}{year}.xml", "w"
        )
        table_val.write(header + "\n")
        table_val.write(f'  <union title="{validator}">\n')
        for category in cat_def["categories"]:
            if "Overall" in category:
                continue
            table_val_prop = open(
                f"results-validated/{validator}.results.{competition.value}{year}_{category}.xml",
                "w",
            )
            table_val_prop.write(header + "\n")
            table_val_prop.write(f'  <union title="{validator}_{category}">\n')
            # Tables for categories over all validators
            for kind in validation_kinds:
                if kind in validator or "witnesslint" in validator:
                    tables_sub[f"{kind}.{category}"].write(
                        f'  <union title="{validator}_{category}">\n'
                    )

            for subcategory in cat_def["categories"][category]["categories"]:
                for kind in validation_kinds:
                    if kind in validator or "witnesslint" in validator:
                        tables_sub[f"{kind}.{category}"].write(
                            f"    <!-- {category}.{subcategory} -->\n"
                        )
                table_val_prop.write(f"    <!-- {category}.{subcategory} -->\n")
                # Tables for subcategories
                table_val_prop_sub = open(
                    f"results-validated/{validator}.results.{competition.value}{year}_{subcategory}.xml",
                    "w",
                )
                table_val_prop_sub.write(header + "\n")
                table_val_prop_sub.write(
                    f'  <union title="{validator}_{subcategory}">\n'
                )
                # Tables for subcategories over all validators
                for kind in validation_kinds:
                    if kind in validator or "witnesslint" in validator:
                        tables_sub[f"{kind}.{subcategory}"].write(
                            f'  <union title="{validator}_{subcategory}">\n'
                        )

                table_val.write(verifier_unions[validator, subcategory])
                table_val_prop.write(verifier_unions[validator, subcategory])
                table_val_prop_sub.write(verifier_unions[validator, subcategory])
                for kind in validation_kinds:
                    if kind in validator or "witnesslint" in validator:
                        tables_sub[f"{kind}.{category}"].write(
                            verifier_unions[validator, subcategory]
                        )
                        tables_sub[f"{kind}.{subcategory}"].write(
                            verifier_unions[validator, subcategory]
                        )

                for kind in validation_kinds:
                    if kind in validator or "witnesslint" in validator:
                        tables_sub[f"{kind}.{subcategory}"].write("  </union>\n")
                table_val_prop_sub.write("  </union>\n")
                table_val_prop_sub.write("</table>\n")
                table_val_prop_sub.close()
            for kind in validation_kinds:
                if kind in validator or "witnesslint" in validator:
                    tables_sub[f"{kind}.{category}"].write("  </union>\n")
            table_val_prop.write("  </union>\n")
            table_val_prop.write("</table>\n")
            table_val_prop.close()
        table_val.write("  </union>\n")
        table_val.write("</table>\n")
        table_val.close()
    for subtable in tables_sub:
        tables_sub[subtable].write("</table>\n")
        tables_sub[subtable].close()
    logging.info("Done creating table-definition files.")


def parse_args():
    parser = argparse.ArgumentParser(description="Create tables for validators.")
    parser.add_argument(
        "--fm-tools",
        type=Path,
        default=Path("fm-tools"),
        help="Path to fm-tools",
    )
    return parser.parse_args()


def main(argv=None):
    fm_tools = parse_args().fm_tools
    assert fm_tools.is_dir(), "fm-tools needs to be a directory"
    coloredlogs.install(fmt="%(levelname)s %(process)s %(name)s %(message)s")
    generate_table_def(fm_tools)


if __name__ == "__main__":
    sys.exit(main())
