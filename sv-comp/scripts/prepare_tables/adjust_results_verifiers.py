#!/usr/bin/env python3
# This file is part of BenchExec, a framework for reliable benchmarking:
# https://github.com/sosy-lab/benchexec
#
# SPDX-FileCopyrightText: 2007-2020 Dirk Beyer <https://www.sosy-lab.org>
#
# SPDX-License-Identifier: Apache-2.0

import sys
import argparse
import logging
import coloredlogs
import os
import re

from enum import Enum
from functools import cached_property
from pathlib import Path
from decimal import Decimal, InvalidOperation
from typing import Optional
from xml.etree import ElementTree
from xml.etree.ElementTree import Element

from benchexec import result
from benchexec import tablegenerator
from benchexec.util import print_decimal

import utils

sys.dont_write_bytecode = True  # Prevent creation of .pyc files


class BenchmarkRuns:
    def __init__(self, original_file, xml: Optional[Element] = None):
        self.original_file = original_file
        self.runs = (
            xml if xml is not None else tablegenerator.parse_results_file(original_file)
        )
        assert (
            self.runs.get("tool") is not None
        ), f"Did not provide a valid xml with a tool name: {self.original_file}"
        self.tool = self.runs.get("tool")

    @cached_property
    def as_dictionary(self) -> dict[str, Element]:
        """
        Represents `runs` as dictionary mapping the run name to the actual run.
        """
        runs = {}
        for run in self.runs.findall("run"):
            name = run.get("name")
            runs[name] = run
        return runs


class BenchmarkRun:
    def __init__(self, original_file, tool, run):
        self.original_file = original_file
        self.run = run
        self.tool = tool


def parse_args(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "resultsXML",
        metavar="results-xml",
        help="XML-file containing the verification results.",
    )
    parser.add_argument(
        "validatorLinterXML",
        nargs="*",
        metavar="validator-linter-xml",
        help="Any number of XML-files containing validator or linter results.",
    )
    parser.add_argument(
        "-i",
        "--invalid-tasks",
        required=True,
        type=Path,
        help="File containing a list of tasks that were banned from the competition.",
    )
    parser.add_argument(
        "--category-structure",
        default="benchmark-defs/category-structure.yml",
        type=Path,
        help="File in YAML format containing the category structure of the competition.",
    )
    return parser.parse_args(argv)


def xml_to_string(elem, qualified_name=None, public_id=None, system_id=None):
    """
    Return a pretty-printed XML string for the Element.
    Also allows setting a document type.
    """
    from xml.dom import minidom

    rough_string = ElementTree.tostring(elem, "utf-8")
    reparsed = minidom.parseString(rough_string)
    if qualified_name is not None:
        doctype = minidom.DOMImplementation().createDocumentType(
            qualified_name, public_id, system_id
        )
        reparsed.insertBefore(doctype, reparsed.documentElement)
    return reparsed.toprettyxml(indent="  ")


class WitnessLintErrors(Enum):
    WITNESS_INVALID = "witness invalid"
    WITNESS_VERSION_MISMATCH = "witness-version mismatch"
    WITNESS_TYPE_MISMATCH = "witness-type mismatch"
    WITNESS_MISSING = "witness missing"
    RESULT_INVALID = "result invalid"


def get_validator_linter_result(
    validator_or_linter_benchmark_run: BenchmarkRun,
    verification_benchmark_run: BenchmarkRun,
):
    validator_linter_run = validator_or_linter_benchmark_run.run
    verification_run = verification_benchmark_run.run
    if validator_linter_run is None:
        # If there is no run result, then this is an error of the verifier.
        return "validation run missing", result.CATEGORY_ERROR
    assert (
        validator_linter_run.find('column[@title="status"]') is not None
    ), f"Column 'status' does not exist for task {verification_run.get('name')} in validator file {validator_or_linter_benchmark_run.original_file} and verification file {verification_benchmark_run.original_file}."
    status_from_validation = validator_linter_run.find('column[@title="status"]').get(
        "value"
    )
    try:
        status_from_verification = verification_run.find('column[@title="status"]').get(
            "value"
        )
        category_from_verification = verification_run.find(
            'column[@title="category"]'
        ).get("value")
    except AttributeError:
        status_from_verification = "not found"
        category_from_verification = result.CATEGORY_MISSING

    # If the result from witness validation matches the result from verification,
    # then leave status and category as is.
    if status_from_validation == status_from_verification:
        return status_from_verification, category_from_verification
    # If the main result string (discarding parentheses) matches the main result
    # string from verification, then also leave status and category as is.
    # valid-memsafety is excluded from this check, as there, the property is necessary.
    # For memsafety, correctness of the result should already be taken care of by benchexec,
    # and it is not possible that we have mismatching properties (between verifier output
    # and expected verdict) with category=correct, we can only have a mismatching property
    # between the verifier and the validator, which we don't want to use for confirmation.
    main_status_from_verification = status_from_verification.split("(")[0]
    main_status_from_validation = status_from_validation.split("(")[0]
    property_is_memsafety = validator_linter_run.get("properties") == "valid-memsafety"
    if (
        main_status_from_verification == main_status_from_validation
        and not property_is_memsafety
    ):
        return status_from_verification, category_from_verification
    # The following three errors are reported by witness linter.
    # 1) An invalid witness counts as error of the verifier.
    if status_from_validation == "ERROR (invalid witness syntax)":
        return (
            f"{WitnessLintErrors.WITNESS_INVALID.value} ({status_from_verification})",
            result.CATEGORY_ERROR,
        )
    # 2) A missing witness counts as error of the verifier.
    if status_from_validation == "ERROR (witness does not exist)":
        return (
            f"{WitnessLintErrors.WITNESS_MISSING.value} ({status_from_verification})",
            result.CATEGORY_ERROR,
        )
    # 3) A mismatch of the witness type counts as error of the verifier.
    if status_from_validation == "ERROR (unexpected witness type)":
        return (
            f"{WitnessLintErrors.WITNESS_TYPE_MISMATCH.value} ({status_from_verification})",
            result.CATEGORY_ERROR,
        )
    # 4) A mismatch of the witness version counts as error of the verifier.
    if status_from_validation == "ERROR (unexpected witness version)":
        return (
            f"{WitnessLintErrors.WITNESS_VERSION_MISMATCH.value} ({status_from_verification})",
            result.CATEGORY_ERROR,
        )

    # Other unconfirmed results count as CATEGORY_CORRECT_UNCONFIRMED.
    # Results of categories different from result.CATEGORY_CORRECT are not overwritten.
    if category_from_verification == result.CATEGORY_CORRECT:
        return status_from_verification, result.CATEGORY_CORRECT_UNCONFIRMED

    # Anything else counts as invalid.
    return (
        f"{WitnessLintErrors.RESULT_INVALID.value} ({status_from_verification})",
        result.CATEGORY_ERROR,
    )


def get_validation_result(
    verifier: BenchmarkRun,
    validators: list[BenchmarkRuns],
    linters: list[BenchmarkRuns],
    status_from_verification,
    category_from_verification,
):
    status_wit, category_wit = None, None
    coverage_wit = Decimal(0)
    name = verifier.run.get("name")

    # For verification only, not for test-case generation
    for linter in linters:
        linter_run = linter.as_dictionary.get(name)
        if linter_run is None:
            continue
        status_wit_new, category_wit_new = get_validator_linter_result(
            BenchmarkRun(linter.original_file, linter.tool, linter_run), verifier
        )
        # Previous linter has found the witness to be good, so we do not change the verdict.
        if category_wit is not None and category_wit != result.CATEGORY_ERROR:
            continue
        status_wit, category_wit = (status_wit_new, category_wit_new)

    # If there is at least one witness linter, and all witness linters report an error on the witness,
    # then the result of the verifier must not be counted.
    if category_wit == result.CATEGORY_ERROR:
        return (
            status_wit,
            category_wit,
            status_from_verification,
            category_from_verification,
        )

    for validator in validators:
        validation_run = validator.as_dictionary.get(name)
        if validation_run is None:
            continue
        # Copy data from validator or linter run
        if verifier.run.get("properties") == "coverage-error-call":
            status_from_validation = validation_run.find('column[@title="status"]').get(
                "value"
            )
            if status_from_validation == "true":
                status_wit, category_wit = (
                    status_from_verification,
                    result.CATEGORY_CORRECT,
                )
                category_from_verification = result.CATEGORY_CORRECT
                coverage_wit = max(coverage_wit, Decimal(1))
        elif verifier.run.get("properties") == "coverage-branches":
            try:
                coverage_value = (
                    validation_run.find('column[@title="branches_covered"]')
                    .get("value")
                    .replace("%", "")
                )
            except AttributeError:
                coverage_value = 0.0
            status_wit, category_wit = (
                status_from_verification,
                result.CATEGORY_CORRECT,
            )
            category_from_verification = result.CATEGORY_CORRECT
            try:
                coverage_wit = max(coverage_wit, Decimal(coverage_value) / 100)
            except InvalidOperation:
                continue
        else:
            # For verification
            status_wit_new, category_wit_new = get_validator_linter_result(
                BenchmarkRun(
                    validator.original_file,
                    validator.tool,
                    validation_run,
                ),
                verifier,
            )
            if (
                category_wit is None
                or not category_wit.startswith(result.CATEGORY_CORRECT)
                or category_wit_new == result.CATEGORY_CORRECT
            ):
                status_wit, category_wit = (status_wit_new, category_wit_new)
    if verifier.run.get("properties") in {"coverage-error-call", "coverage-branches"}:
        # Test-Comp:
        try:
            verifier.run.find('column[@title="score"]').set(
                "value", print_decimal(coverage_wit)
            )
        except AttributeError:
            score_column = ElementTree.Element(
                "column",
                title="score",
                value=print_decimal(coverage_wit),
            )
            verifier.run.append(score_column)

    return (
        status_wit,
        category_wit,
        status_from_verification,
        category_from_verification,
    )


def get_validation_results_for_run(
    verification_run: BenchmarkRun,
    validator_sets: [BenchmarkRuns],
    linter_sets: [BenchmarkRuns],
    status_from_verification,
    category_from_verification,
):
    # Separation of YAML and GraphML linters
    graphml_linters = []
    yml_linters = []
    task_name = verification_run.run.get("name")
    # If the verification run does not have a linter run, we just add the linter's run set to both lists.
    for linter in linter_sets:
        linter_run = linter.as_dictionary.get(task_name)
        if linter_run is None:
            graphml_linters.append(linter)
            yml_linters.append(linter)
            continue
        witness_name_column = linter_run.find(
            'column[@title="witnesslint-witness-file"]'
        )
        if witness_name_column is None:
            graphml_linters.append(linter)
            yml_linters.append(linter)
            continue
        witness_name = witness_name_column.get("value")
        if witness_name is None:
            witness_name = ""
        if witness_name.endswith(".graphml"):
            graphml_linters.append(linter)
        elif witness_name.endswith(".yml"):
            yml_linters.append(linter)
        else:
            graphml_linters.append(linter)
            yml_linters.append(linter)

    # Query status for graphml validators and linters
    (
        statusGraphml,
        categoryGraphml,
        status_from_verification_graphml,
        category_from_verification_graphml,
    ) = get_validation_result(
        verification_run,
        validator_sets,
        graphml_linters,
        status_from_verification,
        category_from_verification,
    )
    # If the GraphML validators and linters confirmed the witness,
    # then we can return the result (no need to check the YAML validators and linters).
    if categoryGraphml == result.CATEGORY_CORRECT:
        return (
            statusGraphml,
            categoryGraphml,
            status_from_verification_graphml,
            category_from_verification_graphml,
        )

    # Query status for YAML validators and linters
    (
        statusYml,
        categoryYml,
        status_from_verification_yml,
        category_from_verification_yml,
    ) = get_validation_result(
        verification_run,
        validator_sets,
        yml_linters,
        status_from_verification,
        category_from_verification,
    )
    # If the YAML validators and linters confirmed the witness, then we can return the result.
    if categoryYml == result.CATEGORY_CORRECT:
        return (
            statusYml,
            categoryYml,
            status_from_verification_yml,
            category_from_verification_yml,
        )

    # If both linters rejected a witness, then return the error message of a linter.
    if (
        categoryGraphml == result.CATEGORY_ERROR
        and categoryYml == result.CATEGORY_ERROR
    ):
        for err in WitnessLintErrors:
            if statusYml is not None and statusYml.startswith(err.value):
                return (
                    statusYml,
                    categoryYml,
                    status_from_verification_yml,
                    category_from_verification_yml,
                )
            if statusGraphml is not None and statusGraphml.startswith(err.value):
                return (
                    statusGraphml,
                    categoryGraphml,
                    status_from_verification_graphml,
                    category_from_verification_graphml,
                )

    # In SV-COMP, results of categories different from result.CATEGORY_CORRECT are not overwritten later on.

    # If no validator confirmed a witness, and no linter rejected a witness,
    # then the result is just unconfirmed.
    return (
        status_from_verification,
        result.CATEGORY_CORRECT_UNCONFIRMED,
        status_from_verification_graphml,
        category_from_verification_graphml,
    )


def adjust_status_category(
    verifier_runs: BenchmarkRuns,
    validators: list[BenchmarkRuns],
    linters: list[BenchmarkRuns],
    invalid_tasks=set(),
):
    def set_status_and_category_for_run(existing_run, new_status, new_category):
        try:
            existing_run.find('column[@title="status"]').set("value", new_status)
        except AttributeError:
            status_column = ElementTree.Element(
                "column", title="status", value=new_status
            )
            existing_run.append(status_column)
        try:
            existing_run.find('column[@title="category"]').set("value", new_category)
        except AttributeError:
            category_column = ElementTree.Element(
                "column", title="category", value=new_category
            )
            existing_run.append(category_column)

    for run in verifier_runs.as_dictionary.values():
        try:
            status_from_verification = run.find('column[@title="status"]').get("value")
        except AttributeError:
            status_from_verification = "not found"
        # If a task was banned from the competition (invalid tasks),
        # then we mark it as invalid in the status and set the category to 'missing'.
        if run.get("name") in invalid_tasks:
            invalid_task_status = f"invalid task ({status_from_verification})"
            invalid_task_category = result.CATEGORY_MISSING
            set_status_and_category_for_run(
                run, invalid_task_status, invalid_task_category
            )
            continue
        # We do not overwrite the status for expected verdict 'true' for some categories of SV-COMP.
        if re.search("SV-COMP", verifier_runs.runs.get("name")) and re.search(
            "-Arrays|-Floats|-Heap|MemSafety|MemCleanup|NoDataRace|ConcurrencySafety-|Termination|-Java",
            verifier_runs.runs.get("name"),
        ):
            if run.get("expectedVerdict") == "true":
                continue
        try:
            category_from_verification = run.find('column[@title="category"]').get(
                "value"
            )
        except AttributeError:
            category_from_verification = result.CATEGORY_MISSING
        (
            statusWit,
            categoryWit,
            status_from_verification,
            category_from_verification,
        ) = get_validation_results_for_run(
            BenchmarkRun(verifier_runs.original_file, verifier_runs.tool, run),
            validators,
            linters,
            status_from_verification,
            category_from_verification,
        )
        # Overwrite status with status from validator or linter
        if (
            category_from_verification == result.CATEGORY_CORRECT
            and statusWit is not None
            and categoryWit is not None
        ):
            set_status_and_category_for_run(run, statusWit, categoryWit)


def main(argv=None):
    coloredlogs.install(fmt="%(levelname)s %(process)s %(name)s %(message)s")
    if argv is None:
        argv = sys.argv[1:]
    args = parse_args(argv)
    result_file = args.resultsXML
    validator_linter_files = args.validatorLinterXML

    if not os.path.exists(result_file) or not os.path.isfile(result_file):
        sys.exit(f"File {result_file!r} does not exist.")
    verifier_xml = tablegenerator.parse_results_file(result_file)
    assert validator_linter_files
    validator_sets = []
    linter_sets = []
    for validator_linter_file in validator_linter_files:
        if not os.path.exists(validator_linter_file) or not os.path.isfile(
            validator_linter_file
        ):
            sys.exit(f"File {validator_linter_file!r} does not exist.")
        validator_linter_xml = tablegenerator.parse_results_file(validator_linter_file)
        if validator_linter_xml.get("tool") == "witnesslint":
            linter_sets.append(
                BenchmarkRuns(validator_linter_file, xml=validator_linter_xml)
            )
        else:
            validator_sets.append(
                BenchmarkRuns(validator_linter_file, xml=validator_linter_xml)
            )

    invalid_tasks = set(
        str(args.invalid_tasks.parent / p)
        for p in args.invalid_tasks.read_text().splitlines()
    )
    invalid_tasks = set(
        os.path.relpath(p, os.path.dirname(result_file)) for p in invalid_tasks
    )

    adjust_status_category(
        BenchmarkRuns(result_file, xml=verifier_xml),
        validator_sets,
        linter_sets,
        invalid_tasks,
    )

    fixed_file = result_file + ".fixed.xml.bz2"
    logging.info(f"   Writing file: {fixed_file}")
    utils.write_xml_file(fixed_file, verifier_xml)


if __name__ == "__main__":
    sys.exit(main())
