#!/usr/bin/env python3
import argparse
import itertools
import logging
import os

# decimal.DefaultContext.rounding = decimal.ROUND_HALF_UP
import sys
from multiprocessing import Pool
from pathlib import Path
from xml.etree import ElementTree

import coloredlogs
import pandas as pd
import yaml
import utils
from benchexec import result
from benchexec import tablegenerator

from fm_tools.competition_participation import Competition
from fm_tools.fmtoolscatalog import FmToolsCatalog
from prepare_tables.utils import XMLResultFileMetadata


# Fix status in results XML.


def parse_args(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "resultsXML",
        nargs="?",
        metavar="results-xml",
        help="XML file containing the results",
    )
    parser.add_argument(
        "violationLinterXML",
        nargs="?",
        metavar="violation-linter-xml",
        help="XML file containing validation results",
    )
    parser.add_argument(
        "correctnessLinterXML",
        nargs="?",
        metavar="correctness-linter-xml",
        help="XML file containing correctness results",
    )
    parser.add_argument(
        "--invalid-tasks",
        required=True,
        type=Path,
        help="File containing a list of tasks that were banned from the competition.",
    )
    parser.add_argument(
        "--invalid-witnesses",
        required=True,
        type=Path,
        help="File containing a list of witnesses that were banned from the validation track.",
    )
    parser.add_argument(
        "-w",
        "--witness-classification",
        required=True,
        type=Path,
        help="File containing each validation task with a verdict indicating the validity of witnesses. This database is produced by mkAnaDatabaseWitnesses.py",
    )
    parser.add_argument(
        "-t",
        "--fm-tools",
        default=Path("fm-tools/data"),
        type=Path,
        help="Path to fm-tools",
    )
    return parser.parse_args(argv)


def map_results(results_xml):
    return {run.get("name"): run for run in results_xml.findall("run")}


def generate_map(violation_linter_file, correctness_linter_file):
    m1 = map_results(violation_linter_file)
    m2 = map_results(correctness_linter_file)
    intersect = set(m1.keys()).intersection(set(m2.keys()))
    if intersect:
        with open("err.log", "a+") as fp:
            fp.write(str((intersect, violation_linter_file, correctness_linter_file)))
        logging.error(
            "Violation witness file and correctness witness file contain the same run? See 'err.log' for more information"
        )
    return m1 | m2


def is_task_excluded_in_validation_track(
    metadata: XMLResultFileMetadata, run: ElementTree.Element
) -> bool:
    # resembles table from https://sv-comp.sosy-lab.org/2025/rules.php#witnesses
    version = metadata.version
    witness = metadata.witness
    specification = run.get("propertyFile")
    category = metadata.category
    assert version in ["1.0", "2.0"], f"Unexpected version {version}"
    assert witness in ["correctness", "violation"], f"Unexpected witness {witness}"
    if witness == "correctness":
        if "ConcurrencySafety" in category:
            return True
        if "no-overflow" in specification:
            return False
        if "unreach-call" in specification:
            return any(category.endswith(u) for u in ["Arrays", "Floats", "Heap"])
        return True
    elif witness == "violation":
        if version == "1.0":
            return False
        if version == "2.0":
            if "ConcurrencySafety" in category:
                return True
            if "unreach-call" in specification or "no-overflow" in specification:
                return False
            if any(
                v in run.get("expectedVerdict") for v in ("valid-free", "valid-deref")
            ):
                return False
        return True
    else:
        raise AssertionError(
            f"Unexpected {witness}-{version} witness for specification {specification} in category {category}"
        )


def adjust_results(
    result_file,
    violation_linter_file,
    correctness_linter_file,
    invalid_tasks_file,
    invalid_witnesses_file,
    witness_classification: pd.DataFrame,
):
    if not os.path.exists(result_file):
        logging.error(f"File {result_file!r} does not exist.")
    if not os.path.exists(violation_linter_file):
        logging.error(f"File {violation_linter_file!r} does not exist.")
    if not os.path.exists(correctness_linter_file):
        logging.error(f"File {correctness_linter_file!r} does not exist.")
    result_xml = tablegenerator.parse_results_file(result_file)
    is_witnesslint = result_xml.get("toolmodule") == "benchexec.tools.witnesslint"
    # Determine whether a validator for violation or correctness witnesses was executed
    version = result_file.split("-witnesses-")[1].split("-")[0]
    assert version in ["1.0", "2.0"], f"Unexpected version {version}"
    validation_type = "violation_witness" if version == "1.0" else "VIOLATION"
    if "validate-correctness-witnesses" in result_file:
        validation_type = "correctness_witness" if version == "1.0" else "CORRECTNESS"

    metadata = XMLResultFileMetadata.from_xml(result_file)
    violation_linter_xml = tablegenerator.parse_results_file(violation_linter_file)
    correctness_linter_xml = tablegenerator.parse_results_file(correctness_linter_file)
    linter_results = generate_map(violation_linter_xml, correctness_linter_xml)

    invalid_tasks = set(
        str(invalid_tasks_file.parent / p)
        for p in invalid_tasks_file.read_text(encoding="utf-8").splitlines()
    )
    invalid_tasks = set(
        os.path.relpath(p, os.path.dirname(result_file)) for p in invalid_tasks
    )

    invalid_witnesses = set(
        witness
        for witness in invalid_witnesses_file.read_text(encoding="utf-8").splitlines()
        if not witness.startswith("#")
    )

    for run in result_xml.findall("run"):
        status = run.find('column[@title="status"]').get("value")
        is_invalid_task = run.get("name") in invalid_tasks
        is_invalid_witness = False
        if run.get("name") in linter_results:
            linter_run = linter_results[run.get("name")]
            witnesslint_witness_file_column = linter_run.find(
                'column[@title="witnesslint-witness-file"]'
            )
            if witnesslint_witness_file_column is not None:
                is_invalid_witness = (
                    witnesslint_witness_file_column.get("value") in invalid_witnesses
                )
        else:
            is_invalid_witness = True
        if (
            is_invalid_task
            or is_invalid_witness
            or is_task_excluded_in_validation_track(metadata, run)
        ):
            if is_invalid_task:
                status_prefix, result_category, witness_category = (
                    "invalid task",
                    result.CATEGORY_MISSING,
                    result.WITNESS_CATEGORY_MISSING,
                )
            elif is_invalid_witness:
                status_prefix, result_category, witness_category = (
                    "invalid witness",
                    result.CATEGORY_MISSING,
                    result.WITNESS_CATEGORY_MISSING,
                )
            else:
                status_prefix, result_category, witness_category = (
                    "unsupported witness",
                    result.CATEGORY_ERROR,
                    result.WITNESS_CATEGORY_ERROR,
                )
            run.find('column[@title="status"]').set(
                "value", f"{status_prefix} ({status})"
            )
            run.find('column[@title="category"]').set("value", result_category)
            new_column = ElementTree.Element(
                "column",
                {
                    "title": "witness-category",
                    "value": witness_category,
                },
            )
            run.append(new_column)
            continue
        category = run.find('column[@title="category"]').get("value")
        # index = ["task", "verifier", "category", "specification"]
        witness_validity = witness_classification.loc[
            (
                run.get("name"),
                metadata.verifier,
                metadata.category,
                run.get("propertyFile"),
            )
        ]
        if isinstance(witness_validity, pd.Series):
            witness_validity = witness_validity[
                f"{metadata.witness}-{metadata.version}"
            ]
        else:
            assert (
                len(witness_validity.index) == 1
            ), f"Expected exactly one entry but got {len(witness_validity.index)} for {run.get('name')} in {result_file}"
            witness_validity = witness_validity[
                f"{metadata.witness}-{metadata.version}"
            ].iloc[0]
        assert isinstance(
            witness_validity, str
        ), f"Expected a string but got {witness_validity}"
        assert witness_validity in [
            result.WITNESS_CATEGORY_CORRECT,
            result.WITNESS_CATEGORY_WRONG,
            result.WITNESS_CATEGORY_UNKNOWN,
        ], f"Expected a valid classification but got {witness_validity}"
        # No linter runs for Java so far, therefore, skip changing category of result.
        if run.get("properties") == "assert_java":
            continue
        if run.get("name") not in linter_results:
            continue
        witness_type_column = linter_run.find(
            'column[@title="witnesslint-witness-type"]'
        )
        witness_type = None
        if witness_type_column is not None:
            witness_type = witness_type_column.get("value")

        # We add a field 'witness-category' to have the validity available for table-generator.
        linter_status = linter_run.find('column[@title="status"]').get("value")
        linter_category = linter_run.find('column[@title="category"]').get("value")
        if "witness does not exist" in linter_status:
            witness_category = result.WITNESS_CATEGORY_MISSING
            # Until BenchExec suppresses executions with missing input files
            # (https://github.com/sosy-lab/benchexec/issues/785)
            # we shall drop runs for missing inputs.
            if not is_witnesslint:
                result_xml.remove(run)
                continue
        elif witness_type is not None and witness_type != validation_type:
            # Drop executions where a validator was executed for a wrong witness type
            result_xml.remove(run)
            continue
        elif "invalid witness syntax" in linter_status:
            witness_category = result.WITNESS_CATEGORY_ERROR
        elif "program does not exist" in linter_status:
            witness_category = result.WITNESS_CATEGORY_ERROR
        elif "EXCEPTION" in linter_status:
            witness_category = result.WITNESS_CATEGORY_ERROR
        elif linter_category == result.CATEGORY_ERROR:
            # All error cases should be handled explicitly above.
            witness_category = result.WITNESS_CATEGORY_ERROR
            logging.warning(
                "Unhandled ERROR case of witness category for task %s in %s with linter status %s %s and %s and %s",
                run.get("name"),
                result_file,
                linter_status,
                linter_category,
                violation_linter_file,
                correctness_linter_file,
            )
        elif linter_category == result.CATEGORY_UNKNOWN:
            # WitnessLint shall not produce unknown results,
            # rather we shall fix the result of WitnessLint (in the tool-info module)
            # to create a result that we understand.
            assert (
                False
            ), f"Unhandled UNKNOWN case of witness category for task {run.get('name')} in {result_file} and {violation_linter_file} and {correctness_linter_file}"
        else:
            # Use the witness classification.
            witness_category = witness_validity

        new_column = ElementTree.Element(
            "column",
            {
                "title": "witness-category",
                "value": witness_category,
            },
        )
        run.append(new_column)

        # We adjust the result category of the run.
        if category not in [
            result.CATEGORY_CORRECT,
            result.CATEGORY_WRONG,
        ]:
            # Categories derived from the validator result that we do not need to adjust,
            # such as ERROR and UNKNOWN.
            category_new = category
        elif witness_type_column is None:
            # We do not know the witness type.
            category_new = result.CATEGORY_UNKNOWN
        elif witness_category not in [
            result.WITNESS_CATEGORY_CORRECT,
            result.WITNESS_CATEGORY_WRONG,
        ]:
            # The witness is neither correct nor wrong.
            category_new = result.CATEGORY_UNKNOWN

        # The scoring schema is documented in Fig. 7 on page 317 in the paper:
        #   https://doi.org/10.1007/978-3-031-57256-2_15
        elif witness_category == result.WITNESS_CATEGORY_CORRECT:
            if witness_type in ("violation_witness", "VIOLATION"):
                if status.startswith("true"):
                    category_new = result.CATEGORY_WRONG
                elif status.startswith("false"):
                    category_new = result.CATEGORY_CORRECT
                else:
                    category_new = result.CATEGORY_UNKNOWN
            elif witness_type in ("correctness_witness", "CORRECTNESS"):
                if status.startswith("true"):
                    category_new = result.CATEGORY_CORRECT
                elif status.startswith("false"):
                    category_new = result.CATEGORY_WRONG
                else:
                    category_new = result.CATEGORY_UNKNOWN
        elif witness_category == result.WITNESS_CATEGORY_WRONG:
            if witness_type in ("violation_witness", "VIOLATION"):
                if status.startswith("true"):
                    category_new = result.CATEGORY_CORRECT
                elif status.startswith("false"):
                    category_new = result.CATEGORY_WRONG
                else:
                    category_new = result.CATEGORY_UNKNOWN
            elif witness_type in ("correctness_witness", "CORRECTNESS"):
                if status.startswith("true"):
                    category_new = result.CATEGORY_WRONG
                elif status.startswith("false"):
                    category_new = result.CATEGORY_CORRECT
                else:
                    category_new = result.CATEGORY_UNKNOWN
        else:
            # Leave unchanged.
            category_new = category
        run.find('column[@title="category"]').set("value", category_new)

        if not is_witnesslint:
            for column in linter_run.findall("column"):
                if column.get("title").startswith("witnesslint-"):
                    new_column = ElementTree.Element(
                        "column",
                        {
                            "title": column.get("title"),
                            "value": column.get("value"),
                        },
                    )
                    run.append(new_column)
    fixed_file = result_file + ".fixed.xml.bz2"
    logging.info(f"   Writing file: {fixed_file}")
    utils.write_xml_file(fixed_file, result_xml)


# needed for thread pool
def wrap_fix(tpl):
    (
        validator,
        verifier,
        subcategory,
        year,
        invalid_tasks_file,
        invalid_witnesses_file,
        witness_classification,
    ) = tpl
    info_tuple = (
        validator,
        verifier,
        subcategory,
        year,
        invalid_tasks_file,
        invalid_witnesses_file,
    )
    result_file = utils.find_latest_file_validator(
        validator, verifier, subcategory, Competition.SV_COMP, year=year
    )
    version = validator.split("-")[-1]
    if not result_file:
        logging.info(f"Missing result file for {info_tuple}.")
        return
    correctness_linter_file = utils.find_latest_file_validator(
        f"witnesslint-validate-correctness-witnesses-{version}",
        verifier,
        subcategory,
        Competition.SV_COMP,
        year=year,
    )
    if not correctness_linter_file:
        logging.info(f"Missing correctness witnesslint file for {info_tuple}.")
        return
    violation_linter_file = utils.find_latest_file_validator(
        f"witnesslint-validate-violation-witnesses-{version}",
        verifier,
        subcategory,
        Competition.SV_COMP,
        year=year,
    )
    if not violation_linter_file:
        logging.info(f"Missing violation witnesslint file for {info_tuple}.")
        return
    adjust_results(
        result_file,
        violation_linter_file,
        correctness_linter_file,
        invalid_tasks_file,
        invalid_witnesses_file,
        witness_classification,
    )
    logging.debug(f"{info_tuple} processed successfully!")
    return


def main():
    coloredlogs.install(fmt="%(levelname)s %(process)s %(name)s %(message)s")
    args = parse_args(sys.argv[1:])
    result_file = args.resultsXML
    violation_linter_file = args.violationLinterXML
    correctness_linter_file = args.correctnessLinterXML

    witness_classification = pd.read_csv(args.witness_classification, sep="\t")
    # Set the index to speed up the search
    witness_classification = witness_classification.set_index(
        ["task", "verifier", "category", "specification"]
    )
    # Sort the index to speed up the search even more
    witness_classification = witness_classification.sort_index()
    tools = FmToolsCatalog(args.fm_tools)

    if len(sys.argv[1:]) > 6:
        # Adjust only one file
        adjust_results(
            result_file,
            violation_linter_file,
            correctness_linter_file,
            args.invalid_tasks,
            args.invalid_witnesses,
            witness_classification,
        )
        return

    # Adjust all files of category structure
    work_list = []
    with open("benchmark-defs/category-structure.yml") as f:
        cat_def = yaml.load(f, Loader=yaml.Loader)
    year_full = cat_def["year"]
    year = str(year_full)[-2:]
    logging.info("Create runs...")
    competition = utils.competition_from_string(cat_def["competition"])
    validators = utils.validators_of_competition(
        tools, competition, year_full, include_postfix=True
    )
    verifiers = utils.verifiers_of_competition(tools, competition, year_full)
    for category in cat_def["categories"]:
        if "Overall" in category:
            continue
        work_list.extend(
            itertools.product(
                validators,
                verifiers,
                cat_def["categories"][category]["categories"],
            )
        )
    # work_list = [('witch-validate-violation-witnesses-2.0', 'cpachecker', 'unreach-call.ReachSafety-BitVectors')]
    num_runs = len(work_list)
    logging.info("Done creating %d runs.", num_runs)
    logging.info("Create fixed files...")
    with Pool(processes=os.cpu_count()) as p:
        try:
            p.map(
                wrap_fix,
                [
                    (
                        val,
                        ver,
                        cat,
                        year,
                        args.invalid_tasks,
                        args.invalid_witnesses,
                        witness_classification,
                    )
                    for val, ver, cat in work_list
                ],
            )
        except AssertionError as e:
            logging.error(e)
            sys.exit(1)
    logging.info("Done creating %d fixed files.", num_runs)


if __name__ == "__main__":
    sys.exit(main())
