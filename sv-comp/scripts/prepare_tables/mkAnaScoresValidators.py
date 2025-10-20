#!/usr/bin/env python3

"""
BenchExec is a framework for reliable benchmarking.
This file is part of BenchExec.

Copyright (C) 2007-2019  Dirk Beyer
All rights reserved.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import argparse
import itertools
import os
from pathlib import Path
import sys
import re
from typing import Optional, List, Tuple
from multiprocessing import Pool
from functools import partial
from decimal import Decimal
import utils
import benchexec.tablegenerator as tablegenerator
import benchexec.result as result
import yaml

import _logging as logging
from fm_tools.fmtoolscatalog import FmToolsCatalog
from fm_tools.competition_participation import Track, Competition
from prepare_tables.utils import TrackDetails, normalize_validator_name

from utils import (
    ValidationCategory,
    accumulate_data,
    combine_qplots,
    CategoryResult,
    CategoryData,
    is_tool_status_false,
    category_sum,
    round_time,
    round_energy,
    remove_witness_lint,
)

Util = tablegenerator.util

STATS_INDEX_TOTAL = 0
STATS_INDEX_CORRECT = 1
STATS_INDEX_CORRECT_TRUE = 2
STATS_INDEX_CORRECT_FALSE = 3
STATS_INDEX_CORRECT_UNCONFIRMED = 4
STATS_INDEX_CORRECT_UNCONFIRMED_TRUE = 5
STATS_INDEX_CORRECT_UNCONFIRMED_FALSE = 6
STATS_INDEX_INCORRECT = 7
STATS_INDEX_INCORRECT_TRUE = 8
STATS_INDEX_INCORRECT_FALSE = 9
STATS_INDEX_SCORE = 10

SCORE_COLUMN_NAME = "score"
""""Name (title) of the score column in run result XMLs."""
WITNESS_CATEGORY_COLUMN_NAME = "witness-category"
""""Name (title) of the column for witness-category in run result XMLs."""
WITNESS_TYPE_COLUMN_NAME = "witnesslint-witness-type"
""""Name (title) of the column for witnesslint-witness-type in run result XMLs."""

SCORE_CORRECT_FALSE = 1
SCORE_INCORRECT_FALSE = -16

FALSIFIER_PREFIX = "Falsification"

# global variables used to exchange info between methods
TABLENAME = "scoretable"
QPLOT_PATH = Path("./results-qplots")


def get_path_rsfscores(suffix: str) -> Path:
    return results_path / f"{TABLENAME}.{suffix}.rsf"


def get_path_htmlscores(suffix: str) -> Path:
    return results_path / f"{TABLENAME}.{suffix}.html"


def get_path_tabscores(suffix: str) -> Path:
    return results_path / f"{TABLENAME}.{suffix}.tsv"


def get_path_texranking(suffix: str) -> Path:
    return results_path / f"scoreranking.{suffix}.tex"


def get_path_texresults(suffix: str) -> Path:
    return results_path / f"scoreresults.{suffix}.tex"


def msg_to_output(msg):
    logging.info(msg)


def err_to_output(err):
    logging.error(err)


DATE = "????-??-??_??-??-??"


####################################
##########################################################
###### Real code begins here #######
##########################################################
####################################


def write_text(path, text):
    path = str(path)
    with open(path, "a") as f:
        f.write(text + "\n")


def remove_file(path: Path):
    if path.exists():
        path.unlink()


def read_text(path: Path) -> str:
    # Only compatible to python > 3.5
    # return path.read_text()
    with open(str(path), "r") as f:
        return f.read()


def write_to_rfs(category, validator, rows: Tuple[str, str], suffix):
    string = "\n".join(["\t".join([category, validator, r[0], r[1]]) for r in rows])
    write_text(get_path_rsfscores(suffix), string)


def does_tool_participate(
    category: str,
    tool: str,
    category_info: dict,
    default_reject=("witnesslint",),
    check_for="validators",
):
    """
    Check if a validator participates in a category.
    :@param category: The category to check.
    :@param validator: The validator to check. The name of the validator must be of the form "<validator>-validate-<type>-witnesses-<version>".
    :@param category_info: The category info to check.
    """
    # for validators only:
    assert check_for in [
        "validators",
        "verifiers",
    ], f"Invalid argument for 'check_for': {check_for}. Must be 'validators' or 'verifiers'."
    categories = category_info["categories"]
    if any(t in tool for t in default_reject):
        return False
    if category in category_info["opt_out"].get(tool, []):
        return False
    if category in category_info["opt_in"].get(tool, []):
        return True
    if category in categories:
        return tool in categories[category][check_for]
    for meta in categories:
        if category in categories[meta]["categories"]:
            return tool in categories[meta][check_for]
    return False


def get_results_XML_file(subcategory, validator, verifier, results_path, category_info):
    # Get xml results file for each validator and category
    # - if a fixed.xml file exists, we take it.
    # Otherwise, we take the default xml file.
    # If none exists, we assume the validator didn't take part in the category.
    results_file_no_fixed_string = (
        str(validator)
        + "-"
        + verifier
        + "."
        + DATE
        + ".results."
        + get_competition_with_year(category_info)
        + "_"
        + subcategory
        + ".xml.bz2"
    )
    results_file_fixed_string = results_file_no_fixed_string + ".fixed.xml.bz2"
    try:
        xml_files = list(results_path.glob(results_file_fixed_string))
        # Fixed file has to be available
        if not xml_files:
            logging.debug(
                "No results file for validator %s and category %s. Used string: %s",
                validator,
                subcategory,
                results_file_fixed_string,
            )
            if not does_tool_participate(
                subcategory, validator, category_info
            ) or not does_tool_participate(
                subcategory, verifier, category_info, check_for="verifiers"
            ):
                return None
            else:
                error = f"No fixed.xml.bz2 data for validator {validator} and category {subcategory} available for verifier {verifier}."
                raise AssertionError(error)
        if len(xml_files) > 1:
            xml_files = sorted(
                xml_files, reverse=True
            )  # sorts by date due to file name structure
        return str(xml_files[0])
    except Exception as e:
        logging.exception("Exception for %s: %s", results_file_fixed_string, e)
        return None


def handle_meta_category(
    meta_category, category_info, processed_categories, track_details: TrackDetails
):
    categories = get_categories(category_info)
    try:
        demo_categories = get_demo_categories(category_info)
    except KeyError:
        demo_categories = list()
    postfix = "-".join(
        track_details.track.value.lower().replace("validation of ", "").split()
    )
    subvalidators = [
        normalize_validator_name(v)
        for v in remove_witness_lint(categories[meta_category]["validators"])
        if v.endswith(postfix)
    ]

    subcategories = {
        sub: processed_categories[sub]
        for sub in categories[meta_category]["categories"]
        if sub not in demo_categories
        and (
            (
                processed_categories[sub].witnesses_correct
                + processed_categories[sub].witnesses_wrong
            )
            > 0
        )
    }
    subcategories_info = list(subcategories.values())
    category_amount = len(subcategories)
    tasks = sum([c.tasks for c in subcategories_info])
    witnesses_correct = sum([c.witnesses_correct for c in subcategories_info])
    witnesses_wrong = sum([c.witnesses_wrong for c in subcategories_info])

    def normalize_score(score):
        if category_amount == 0:
            return 0
        return score / category_amount * (witnesses_correct + witnesses_wrong)

    # Sum of each category's normalized score, normalized according to the number of tasks of that individual category
    sum_of_avg_possible_score = sum(
        [
            Decimal(c.possible_score) / (c.witnesses_correct + c.witnesses_wrong)
            for c in subcategories_info
            if c.possible_score != 0
        ]
    )
    possible_score = normalize_score(sum_of_avg_possible_score)

    sum_of_avg_possible_score_false = sum(
        [
            Decimal(c.possible_score_false) / (c.witnesses_correct + c.witnesses_wrong)
            for c in subcategories_info
            if c.possible_score_false != 0
        ]
    )
    possible_score_false = normalize_score(sum_of_avg_possible_score_false)

    cat_info = ValidationCategory(
        meta_category,
        tasks,
        [],
        [],
        possible_score,
        possible_score_false,
        witnesses_correct,
        witnesses_wrong,
    )

    for validator in subvalidators:
        subcategories_available = [
            c for c in subcategories_info if validator in c.results
        ]
        # if len(subcategories_available) < len(subcategories):
        #    logging.info(
        #        "Not considering validator %s for category %s because of missing sub-categories. Available sub-categories: %s",
        #        validator,
        #        meta_category,
        #        [c.name for c in subcategories_available],
        #    )
        #    continue
        relevant_results = [c.results[validator] for c in subcategories_available]

        # can't use relevant_results here because we need the number of total tasks per category
        sum_of_avg_scores = sum(
            [
                Decimal(c.results[validator].score)
                / (c.witnesses_correct + c.witnesses_wrong)
                for c in subcategories_info
                if validator in c.results.keys() and c.results[validator].score != 0
            ]
        )
        score = normalize_score(sum_of_avg_scores)

        sum_of_avg_scores_false = sum(
            [
                Decimal(c.results[validator].score_false)
                / (c.witnesses_correct + c.witnesses_wrong)
                for c in subcategories_info
                if validator in c.results.keys()
                and c.results[validator].score_false != 0
            ]
        )
        score_false = normalize_score(sum_of_avg_scores_false)

        cputime_data = accumulate_data([r.cputime for r in relevant_results])
        cpuenergy_data = accumulate_data([r.cpuenergy for r in relevant_results])

        correct_false = sum(
            [
                c.results[validator].correct_false or 0
                for c in subcategories_info
                if validator in c.results.keys()
            ]
        )
        correct_true = sum(
            [
                c.results[validator].correct_true or 0
                for c in subcategories_info
                if validator in c.results.keys()
            ]
        )
        correct_unconfirmed_false = sum(
            [
                c.results[validator].correct_unconfirmed_false or 0
                for c in subcategories_info
                if validator in c.results.keys()
            ]
        )
        correct_unconfirmed_true = sum(
            [
                c.results[validator].correct_unconfirmed_true or 0
                for c in subcategories_info
                if validator in c.results.keys()
            ]
        )
        incorrect_false = sum(
            [
                c.results[validator].incorrect_false or 0
                for c in subcategories_info
                if validator in c.results.keys()
            ]
        )
        incorrect_true = sum(
            [
                c.results[validator].incorrect_true or 0
                for c in subcategories_info
                if validator in c.results.keys()
            ]
        )

        qplot_cputime = combine_qplots(
            [
                c.results[validator].qplot_cputime
                for c in subcategories_info
                if validator in c.results.keys()
            ],
            category_amount,
        )
        qplot_cpuenergy = combine_qplots(
            [
                c.results[validator].qplot_cpuenergy
                for c in subcategories_info
                if validator in c.results.keys()
            ],
            category_amount,
        )

        cat_info.results[validator] = CategoryResult(
            score,
            score_false,
            cputime_data,
            cpuenergy_data,
            correct_false,
            correct_true,
            correct_unconfirmed_false,
            correct_unconfirmed_true,
            incorrect_false,
            incorrect_true,
            qplot_cputime,
            qplot_cpuenergy,
            None,
        )

    return cat_info


def _get_column_index(column_name: str, run_set_result) -> Optional[int]:
    """Get the index of the column with the given name in the given RunSetResult or RunResult."""
    columns = run_set_result.columns
    return next((columns.index(c) for c in columns if c.title == column_name), None)


def _get_column_values(
    column_name: str,
    run_set_result: tablegenerator.RunSetResult,
    convert_to_decimal=True,
) -> List[Decimal | str]:
    column_index = _get_column_index(column_name, run_set_result)
    if column_index is None:
        return list()
    if convert_to_decimal:
        return [Util.to_decimal(r.values[column_index]) for r in run_set_result.results]
    else:
        return [r.values[column_index] for r in run_set_result.results]


def _create_category_data(
    column_name: str, run_set_result: tablegenerator.RunSetResult
) -> CategoryData:
    correct_mask = [
        r.category == result.CATEGORY_CORRECT for r in run_set_result.results
    ]
    unconfirmed_mask = [
        r.category == result.CATEGORY_CORRECT_UNCONFIRMED
        for r in run_set_result.results
    ]
    false_results = [is_tool_status_false(r.status) for r in run_set_result.results]
    correct_false_mask = [c and f for c, f in zip(correct_mask, false_results)]
    unconfirmed_false_mask = [c and f for c, f in zip(unconfirmed_mask, false_results)]

    data_sequence = _get_column_values(column_name, run_set_result)
    assert all((d is None or isinstance(d, Decimal) for d in data_sequence))

    total = category_sum(v or 0 for v in data_sequence)
    success = category_sum(
        v or 0 for v in itertools.compress(data_sequence, correct_mask)
    )
    success_false = category_sum(
        v or 0 for v in itertools.compress(data_sequence, correct_false_mask)
    )
    unconfirmed = category_sum(
        v or 0 for v in itertools.compress(data_sequence, unconfirmed_mask)
    )
    unconfirmed_false = category_sum(
        v or 0 for v in itertools.compress(data_sequence, unconfirmed_false_mask)
    )

    return CategoryData(
        total, success, success_false, unconfirmed, unconfirmed_false, data_sequence
    )


def get_score(run_result: tablegenerator.RunResult) -> Optional[Decimal]:
    score_column_index = _get_column_index(SCORE_COLUMN_NAME, run_result)

    score = run_result.score
    if score_column_index is not None:
        # Always use explicitly given score instead of score computed by table generator,
        # if available
        listed_score = run_result.values[score_column_index]
        score = None
        if listed_score is not None:
            try:
                score = Decimal(listed_score)
            except TypeError as e:
                logging.debug(
                    "Type error while creating score for %s",
                    run_result.task_id,
                    exc_info=e,
                )
    return score


def _get_scores_data(
    run_set_result: tablegenerator.RunSetResult,
    category: str,
    validator: str,
) -> dict[str, int]:
    score, score_false = 0, 0
    correct_true, correct_false = 0, 0
    correct_unconfirmed_true, correct_unconfirmed_false = 0, 0
    incorrect_true, incorrect_false = 0, 0

    for run_result in run_set_result.results:
        run_result.score = get_score(run_result)

        if run_result.score is None:
            logging.warning(
                'Score missing for task "{0}" (category "{1}", validator "{2}"), cannot produce score-based quantile data.'.format(
                    run_result.task_id[0], category, validator
                )
            )
            continue

        score += run_result.score
        if is_tool_status_false(run_result.status):
            score_false += run_result.score
        if run_result.category == result.CATEGORY_CORRECT:
            if is_tool_status_false(run_result.status):
                correct_false += 1
            else:
                correct_true += 1
        elif run_result.category == result.CATEGORY_CORRECT_UNCONFIRMED:
            if is_tool_status_false(run_result.status):
                correct_unconfirmed_false += 1
            else:
                correct_unconfirmed_true += 1
        elif run_result.category == result.CATEGORY_WRONG:
            if is_tool_status_false(run_result.status):
                incorrect_false += 1
            else:
                incorrect_true += 1

    # expected_score = (
    # correct_false * 1
    # + correct_true * 2
    # + correct_unconfirmed_true * 0
    # + correct_unconfirmed_false * 0
    # + incorrect_false * -16
    # + incorrect_true * -32
    # )
    # assert score == expected_score
    # expected_score = (
    # correct_false * 1 + correct_unconfirmed_false * 0 + incorrect_false * -16
    # )
    # assert score_false == expected_score

    return {
        "score": score,
        "score_false": score_false,
        "correct_true": correct_true,
        "correct_false": correct_false,
        "correct_unconfirmed_true": correct_unconfirmed_true,
        "correct_unconfirmed_false": correct_unconfirmed_false,
        "incorrect_true": incorrect_true,
        "incorrect_false": incorrect_false,
    }


def get_witness_type(
    run_result: tablegenerator.RunResult, run_set_result: tablegenerator.RunSetResult
) -> str | None:
    witness_type_column_index = _get_column_index(
        WITNESS_TYPE_COLUMN_NAME, run_set_result
    )
    if witness_type_column_index is None:
        return None
    return run_result.values[witness_type_column_index]


def get_max_score(
    run_result: tablegenerator.RunResult, run_set_result: tablegenerator.RunSetResult
) -> int:
    witness_type = get_witness_type(run_result, run_set_result)
    if witness_type is None:
        return 0
    if (
        run_result.task_id.witness_category == result.WITNESS_CATEGORY_CORRECT
        and witness_type in ("violation_witness", "VIOLATION")
    ) or (
        run_result.task_id.witness_category == result.WITNESS_CATEGORY_WRONG
        and witness_type in ("correctness_witness", "CORRECTNESS")
    ):
        return result._SCORE_CORRECT_FALSE
    if (
        run_result.task_id.witness_category == result.WITNESS_CATEGORY_CORRECT
        and witness_type in ("correctness_witness", "CORRECTNESS")
    ) or (
        run_result.task_id.witness_category == result.WITNESS_CATEGORY_WRONG
        and witness_type in ("violation_witness", "VIOLATION")
    ):
        return result._SCORE_CORRECT_TRUE
    return 0


def get_category_info(run_set_result, category: str) -> Optional[ValidationCategory]:
    witnesses_correct = 0
    witnesses_wrong = 0
    for r in run_set_result.results:
        if r.task_id.witness_category == result.WITNESS_CATEGORY_CORRECT:
            witnesses_correct += 1
        if r.task_id.witness_category == result.WITNESS_CATEGORY_WRONG:
            witnesses_wrong += 1
        if r.task_id.expected_result is None:
            assert (
                r.task_id.witness_category == result.WITNESS_CATEGORY_MISSING
            ), f"The task {r.task_id.name} does not have an expected result but is valid?"

    tasks = len(run_set_result.results)

    possible_score_list = [
        (
            get_max_score(r, run_set_result),
            0,
            r.task_id.expected_result,
            r.task_id.witness_category,
        )
        for r in run_set_result.results
        if r.task_id.expected_result is not None
    ]

    possible_score_false_list = [
        (
            get_max_score(r, run_set_result),
            0,
            r.task_id.expected_result,
            r.task_id.witness_category,
        )
        for r in run_set_result.results
        if r.task_id.expected_result is not None
        and not r.task_id.expected_result.result
    ]

    return ValidationCategory(
        category,
        tasks,
        possible_score_list,
        possible_score_false_list,
        0,
        0,
        witnesses_correct,
        witnesses_wrong,
    )


def _get_qplot_data(
    run_set_result: tablegenerator.RunSetResult,
    values: List[Decimal],
    category: str,
    validator: str,
    competition: Competition,
) -> List[Tuple[float, float, str, str]]:
    """
    Return list of tuples ((not yet normalized) score, value, status, witness category).
    Each tuple represents one run result with its score, the
    corresponding value from the given value list, the run's status, and the run's witness category.
    """
    # TODO: Replace returned tuple by dict with speaking names as keys
    qplot_data = []

    if len([t for t in run_set_result.get_tasks()]) == 0:
        return qplot_data

    witness_category_column_index = _get_column_index(
        WITNESS_CATEGORY_COLUMN_NAME, run_set_result
    )
    error_msg = f'Witness category missing for category "{category}", validator "{validator}", file {run_set_result.attributes["filename"]}, cannot produce score-based quantile data.'
    assert witness_category_column_index, error_msg

    for run_result, curr_value in zip(run_set_result.results, values):
        witness_category = run_result.values[witness_category_column_index]
        if (
            run_result.category == result.CATEGORY_WRONG
            or run_result.category == result.CATEGORY_CORRECT
            or run_result.category == result.CATEGORY_CORRECT_UNCONFIRMED
            or competition != Competition.SV_COMP
        ):
            qplot_data.append(
                (
                    float(run_result.score),
                    curr_value,
                    run_result.status,
                    witness_category,
                )
            )
        elif run_result.category == result.CATEGORY_MISSING:
            logging.debug(
                'Category "missing" for task "{0}" (category "{1}", validator "{2}"), cannot produce score-based quantile value.'.format(
                    run_result.task_id[0], category, validator
                )
            )
            continue
        else:
            assert run_result.category in {
                result.CATEGORY_ERROR,
                result.CATEGORY_UNKNOWN,
            }
    return qplot_data


def get_categories(category_info):
    """Returns the defined meta-categories of the given category info"""
    return category_info["categories"]


def get_demo_categories(category_info):
    try:
        return category_info["demo_categories"]
    except KeyError:
        # no demo categories in category info
        return list()


def get_all_categories_table_order(category_info):
    return category_info["categories_table_order"]


def get_all_categories_process_order(category_info):
    return category_info["categories_process_order"]


def get_competition_with_year(category_info) -> str:
    year = str(category_info["year"])[-2:]
    competition = category_info["competition"]
    return competition + year


def normalize_base_category(
    sequence: List, cat_info_validator: ValidationCategory
) -> List:
    result_sequence = []
    category_amount = 0
    if cat_info_validator.witnesses_correct > 0:
        category_amount += 1
    if cat_info_validator.witnesses_wrong > 0:
        category_amount += 1
    if category_amount == 0:
        return result_sequence
    for score, val, status, witness_category in sequence:
        if witness_category == result.WITNESS_CATEGORY_CORRECT:
            score = score / cat_info_validator.witnesses_correct
        elif witness_category == result.WITNESS_CATEGORY_WRONG:
            score = score / cat_info_validator.witnesses_wrong
        else:
            score = 0
        result_sequence.append((score / category_amount, val, status))
    return result_sequence


def handle_base_category(
    category,
    results_path,
    category_info,
    track_details: TrackDetails,
    tools: FmToolsCatalog,
):
    # Collects results for validators
    cat_info = ValidationCategory(category, 0, [], [], 0, 0, 0, 0)
    # Collects category counts
    cat_info_counts = ValidationCategory(category, 0, [], [], 0, 0, 0, 0)
    for validator in utils.get_competition_tools(
        tools, track_details, include_witness_lint=False
    ):
        cat_info_validator = ValidationCategory(category, 0, [], [], 0, 0, 0, 0)
        verification_track = (
            Track.Test_Generation
            if track_details.competition == Competition.TEST_COMP
            else Track.Verification
        )
        for verifier in utils.get_competition_tools(
            tools,
            TrackDetails(
                track_details.competition, verification_track, track_details.year
            ),
        ):
            results_file = get_results_XML_file(
                category,
                validator_with_suffix(validator, track_details),
                verifier,
                results_path,
                category_info,
            )
            if results_file is None:
                continue
            # load results
            run_set_result = tablegenerator.RunSetResult.create_from_xml(
                results_file, tablegenerator.parse_results_file(results_file)
            )
            run_set_result.collect_data(False)

            try:
                cat_info_verifier = get_category_info(run_set_result, category)
            except Exception as e:
                # Multiprocessing does not always propagate exceptions
                # Therefore, we use this safeguard to see undesired behavior in the logs.
                logging.exception(
                    "Exception while processing category %s for validator %s and verifier %s: %s",
                    category,
                    validator,
                    verifier,
                    e,
                )
                raise AssertionError("Error while processing category") from e
            cat_info_validator += cat_info_verifier

            # Collect data points (score, cputime, status) for generating quantile plots.
            score_data = _get_scores_data(run_set_result, category, validator)
            cputime = _create_category_data("cputime", run_set_result)
            cpuenergy = _create_category_data("cpuenergy", run_set_result)

            if not cputime.sequence:
                logging.debug(
                    "CPU time missing for {0}, {1}".format(validator, category)
                )
            if not cpuenergy.sequence:
                logging.debug(
                    "CPU energy missing for {0}, {1}".format(validator, category)
                )

            get_qplot = partial(
                _get_qplot_data,
                run_set_result=run_set_result,
                category=category,
                validator=validator,
                competition=track_details.competition,
            )

            qplot_data_cputime = get_qplot(values=cputime.sequence)
            qplot_data_cpuenergy = get_qplot(values=cpuenergy.sequence)

            category_result = CategoryResult(
                cputime=cputime,
                qplot_cputime=qplot_data_cputime,
                cpuenergy=cpuenergy,
                qplot_cpuenergy=qplot_data_cpuenergy,
                results_file=results_file,
                **score_data,
            )  # expands to the individual score parameters
            if validator not in cat_info.results:
                cat_info.results[validator] = category_result
            else:
                cat_info.results[validator] += category_result
        if cat_info_validator.tasks > 0:
            # If the number of tasks is >0 then we can use the counts made for this validator.
            if cat_info_counts.witnesses_correct + cat_info_counts.witnesses_wrong > 0:
                assert (
                    cat_info_validator.witnesses_wrong
                    + cat_info_validator.witnesses_correct
                    == cat_info_counts.witnesses_correct
                    + cat_info_counts.witnesses_wrong
                ), validator
            cat_info_counts = cat_info_validator

            cat_info.results[validator].qplot_cputime = normalize_base_category(
                cat_info.results[validator].qplot_cputime, cat_info_validator
            )
            cat_info.results[validator].qplot_cpuenergy = normalize_base_category(
                cat_info.results[validator].qplot_cpuenergy, cat_info_validator
            )

            cat_info.results[validator].score = sum(
                score for score, _, _ in cat_info.results[validator].qplot_cputime
            ) * (
                cat_info_validator.witnesses_correct
                + cat_info_validator.witnesses_wrong
            )

            cat_info_counts.possible_score_list = normalize_base_category(
                cat_info_counts.possible_score_list, cat_info_validator
            )
            cat_info_counts.possible_score = sum(
                score for score, _, _ in cat_info_counts.possible_score_list
            ) * (cat_info_counts.witnesses_correct + cat_info_counts.witnesses_wrong)

            cat_info_counts.possible_score_false_list = normalize_base_category(
                cat_info_counts.possible_score_false_list, cat_info_validator
            )
            cat_info_counts.possible_score_false = sum(
                score for score, _, _ in cat_info_counts.possible_score_false_list
            ) * (cat_info_counts.witnesses_correct + cat_info_counts.witnesses_wrong)

    # Take the validator results from cat_info and the category counts from cat_info_counts.
    return cat_info + cat_info_counts


def get_best(
    category: ValidationCategory,
    track_details: TrackDetails,
    tools: FmToolsCatalog,
    is_falsification: bool = False,
):
    def is_considered(validator: str):
        return (
            tools[validator]
            .competition_participations.competition(
                track_details.competition, track_details.year
            )
            .competes_in(track_details.track)
            and not utils.is_hors_concours(
                tools,
                validator,
                track_details.year,
                track_details.competition,
                track_details.track,
            )
            and (category.witnesses_correct + category.witnesses_wrong) > 0
        )

    # put None instead of leaving the tool out if the score is not positive
    # to still give medals to tools that have a positive score.
    # 0 or fewer points should still be counted to the at least 3 required participants for a medal.
    competitors = [
        (v.split("-validate-")[0], r)
        for v, r in category.results.items()
        if is_considered(v.split("-validate-")[0])
    ]
    winners_with_non_positive_score = len(
        [(c, r) for c, r in competitors if r.score <= 0]
    )
    competitors = [(c, r) for c, r in competitors if r.score > 0]
    if is_falsification:
        result = [
            name
            for name, result in sorted(
                competitors,
                key=lambda x: (
                    x[1].score_false,
                    (
                        (1 / Decimal(x[1].cputime.success_false))
                        if x[1].cputime.success_false
                        else 0
                    ),
                ),
                reverse=True,
            )[0:3]
        ]
    else:
        result = [
            name
            for name, result in sorted(
                competitors,
                key=lambda x: (
                    x[1].score,
                    (1 / Decimal(x[1].cputime.success)) if x[1].cputime.success else 0,
                ),
                reverse=True,
            )[0:3]
        ]
    if len(result) < 3:
        result += [None] * winners_with_non_positive_score
    return result[:3]


def prepare_qplot_csv(
    qplot: list, processed_category: ValidationCategory, competition: Competition
) -> Optional[List[Tuple]]:
    category_tasks = (
        processed_category.witnesses_correct + processed_category.witnesses_wrong
    )
    if not qplot:
        return None

    x_and_y_list = list()
    if processed_category.name.startswith(FALSIFIER_PREFIX):
        qplot_data = [(s, c, st) for (s, c, st) in qplot if is_tool_status_false(st)]
    else:
        qplot_data = qplot

    if competition == Competition.SV_COMP:
        # Left-most data-point in plot is at the sum of all negative scores
        index = sum(
            [float(score) * category_tasks for score, _, _ in qplot_data if score < 0]
        )
        # Data points for positive scores, sort them by value
        qplot_ordered = [(score, value) for score, value, _ in qplot_data if score > 0]
        qplot_ordered.sort(key=lambda entry: entry[1])
        for score, value in qplot_ordered:
            index += float(score) * category_tasks
            x_and_y_list.append((index, value))
    return x_and_y_list


def write_csv(
    path: Path,
    qplot_data: list,
    processed_category: ValidationCategory,
    competition: Competition,
) -> None:
    qplot_x_and_y_values = prepare_qplot_csv(
        qplot_data, processed_category, competition
    )
    if qplot_x_and_y_values:
        if path.exists():
            path.unlink()
        if not path.parent.exists():
            os.makedirs(str(path.parent))
        csv = "\n".join([str(x) + "\t" + str(y) for x, y in qplot_x_and_y_values])
        write_text(path, csv)


def _prepare_for_rfs(value: Decimal) -> str:
    return str(round(value, 9) if value else value)


def _get_html_table_cell(content: Optional[str], measure: str, rank_class: str) -> str:
    if content is not None and content != "":
        return (
            "<td class='value"
            + rank_class
            + "'>"
            + content
            + "&nbsp;"
            + measure
            + "</td>"
        )
    else:
        return "<td></td>"


def validator_with_suffix(validator: str, track_details: TrackDetails):
    witness_kind, witnesses, witness_version = (
        track_details.track.value[len("Validation of ") :].lower().split()
    )
    return f"{validator}-validate-{witness_kind}-{witnesses}-{witness_version}"


def dump_output_files(
    processed_categories,
    track_details: TrackDetails,
    tools: FmToolsCatalog,
    category_info,
):
    witness_kind, _, witness_version = (
        track_details.track.value[len("Validation of ") :].lower().split()
    )
    short_year = str(track_details.year)[-2:]

    # consider only one kind of validators supporting the C language
    # there is currently no validation track for Java
    validators = utils.get_competition_tools(
        tools, track_details, include_witness_lint=False, filter_language={"C"}
    )
    validator_html, validator_tab = utils.get_tool_html_and_tab(
        tools, validators, track_details.competition, track_details.year
    )
    post_fix = f"{witness_kind}-{witness_version}"
    # prepare for export
    processed_categories = {
        k: v for (k, v) in processed_categories.items() if v.results
    }
    final_category_ranking_counter = 0
    html_string = (
        """
<hr/>
<h2>Table of All Results</h2>

<p>
In every table cell for competition results,
we list the points in the first row and the CPU time (rounded to two significant digits) for successful runs in the second row.
</p>

<p>
The entry '&ndash;' means that the competition candidate was not executed in the category.<br/>
The definition of the scoring schema can be found in the literature
[<a href='https://doi.org/10.1007/978-3-031-57256-2_15'>Proc. TACAS 2024</a>, Fig. 7, page 317]
and the <a href="../../benchmarks.php">categories</a> are defined on the respective SV-COMP web page.
</p>

<p>
<input type='checkbox' id='hide-base-categories' onclick="$('.sub').toggle()"><label id='hide-base-categories-label' for='hide-base-categories'>Hide base categories</label>
</p>
"""
        + "<table id='scoretable'>\n"
        + "<thead>\n"
        + "\t<tr class='head'>\n"
        + validator_html
        + "\n\t</tr>\n"
        + "</thead>\n<tbody>"
        + utils.get_member_lines(validators, tools, track_details)
    )
    html_ranking_string = """
<hr />
<h2><a id="plots">Ranking by Category (with Score-Based Quantile Plots)</a></h2>

<table id='ranktable'>
<tr>
"""
    tab_string = ""
    tex_ranking_string = "\\\\[-\\normalbaselineskip]" + "\n"

    meta_categories = get_categories(category_info)

    # some categories are excluded from correctness witness validation and have no results (exclude them)
    categories_table_order = get_all_categories_table_order(category_info)
    categories_table_order = [
        c for c in categories_table_order if c in set(processed_categories.keys())
    ]

    for category in categories_table_order:
        tasks_total = processed_categories[category].tasks
        witnesses_correct = processed_categories[category].witnesses_correct
        witnesses_wrong = processed_categories[category].witnesses_wrong
        if witnesses_correct + witnesses_wrong == 0 or category.startswith(
            FALSIFIER_PREFIX
        ):
            continue
        possible_score = round(processed_categories[category].possible_score)
        best_validators = get_best(processed_categories[category], track_details, tools)
        score_tab = category + "\t" + str(witnesses_correct + witnesses_wrong) + "\t"
        cputime_success_tab = "CPU Time\t\t"
        cputime_success_true_tab = "CPU Time (true-tasks)\t\t"
        cputime_success_false_tab = "CPU Time (false-tasks)\t\t"
        cpuenergy_success_tab = "CPU Energy\t\t"
        correct_true_tab = "correct true\t\t"
        correct_false_tab = "correct false\t\t"
        unconfirmed_true_tab = "unconfirmed true\t\t"
        unconfirmed_false_tab = "unconfirmed false\t\t"
        incorrect_true_tab = "incorrect true\t\t"
        incorrect_false_tab = "incorrect false\t\t"

        categoryname = category
        if category not in meta_categories:
            categoryname = category.split(".")[1]
        category_link = categoryname
        category_file = f"validate-{witness_kind}-witnesses-{witness_version}.results.{track_details.competition.value}{short_year}_{category}.table.html"
        if os.path.exists(f"results-validated/{category_file}") or os.path.exists(
            f"results-validated/{category_file}.gz"
        ):
            category_link = f"<a href='{category_file}'>{categoryname}</a>"
        score_html = (
            "\t<td class='category-name'>"
            + category_link
            + "<br />"
            + f"<span class='stats'>{str(witnesses_correct + witnesses_wrong)} valid tasks"
            + f" ({str(witnesses_correct)} correct, {str(witnesses_wrong)} wrong, {str(tasks_total - (witnesses_correct + witnesses_wrong))} void)"
        )
        if possible_score:
            score_html += ", max. score: " + str(possible_score)
        quantile_link = ""
        quantile_file = f"quantilePlot-{category}.{post_fix}.svg"
        if os.path.exists(f"results-validated/{quantile_file}"):
            quantile_link = f"<a href='{quantile_file}'><img class='tinyplot' src='{quantile_file}' alt='Quantile-Plot' /></a>"
        score_html += "</span></td>\n" + f"<td class='tinyplot'>{quantile_link}</td>\n"
        cputime_success_html = "\t<td>CPU time</td><td></td>"
        cpuenergy_success_html = "\t<td>CPU energy</td><td></td>"

        write_text(
            get_path_rsfscores(suffix=post_fix),
            categoryname
            + "\tTASKSTOTAL\t"
            + str(processed_categories[category].tasks)
            + "\n"
            + categoryname
            + "\tMAXSCORE\t"
            + str(possible_score),
        )

        results = processed_categories[category].results
        for validator in validators:
            if validator not in results.keys():
                score = ""
                cputime_success = ""
                cputime_success_true = ""
                cputime_success_false = ""
                cpuenergy_success = ""
                correct_true = ""
                correct_false = ""
                unconfirmed_true = ""
                unconfirmed_false = ""
                incorrect_true = ""
                incorrect_false = ""
            else:
                if category.startswith(FALSIFIER_PREFIX):
                    # Compute score taking into account only correct and incorrect false
                    score = results[validator].score_false
                    # assert round(score) == round(results[validator].correct_false * 1 + results[validator].incorrect_false * -16)
                    cputime_success = results[validator].cputime.success_false
                    cputime_success_true = None
                    cputime_success_false = cputime_success
                    cpuenergy_success = results[validator].cpuenergy.success_false
                else:
                    score = results[validator].score
                    # assert round(score) == round(results[validator].correct_false * 1 + results[validator].correct_true * 2 \
                    #                             + results[validator].incorrect_false * -16 + results[validator].incorrect_true * -32)
                    cputime_success = results[validator].cputime.success
                    cputime_success_true = results[validator].cputime.success_true
                    cputime_success_false = results[validator].cputime.success_false
                    cpuenergy_success = results[validator].cpuenergy.success

                rfs_rows = [
                    ("SCORE", _prepare_for_rfs(score)),
                    ("CPUTIMESUCCESS", _prepare_for_rfs(cputime_success)),
                    ("CPUTIMESUCCESSTRUE", _prepare_for_rfs(cputime_success_true)),
                    ("CPUTIMESUCCESSFALSE", _prepare_for_rfs(cputime_success_false)),
                    ("CPUENERGYSUCCESS", _prepare_for_rfs(cpuenergy_success)),
                ]
                write_to_rfs(categoryname, validator, rfs_rows, suffix=post_fix)

                score = round(score)
                if score is None:
                    score = ""

                correct_true = results[validator].correct_true
                correct_false = results[validator].correct_false
                unconfirmed_true = results[validator].correct_unconfirmed_true
                unconfirmed_false = results[validator].correct_unconfirmed_false
                incorrect_true = results[validator].incorrect_true
                incorrect_false = results[validator].incorrect_false

            rank_class = ""
            if (
                category in meta_categories["Overall"]["categories"]
                or category.endswith("Overall")
            ) and len(best_validators) >= 3:
                if validator == best_validators[0]:
                    rank_class = " gold"
                elif validator == best_validators[1]:
                    rank_class = " silver"
                elif validator == best_validators[2]:
                    rank_class = " bronze"

            correct_true_tab += str(correct_true) + "\t"
            correct_false_tab += str(correct_false) + "\t"
            unconfirmed_true_tab += str(unconfirmed_true) + "\t"
            unconfirmed_false_tab += str(unconfirmed_false) + "\t"
            incorrect_true_tab += str(incorrect_true) + "\t"
            incorrect_false_tab += str(incorrect_false) + "\t"

            score_tab += str(score) + "\t"
            cputime_success_tab += str(cputime_success) + "\t"
            cputime_success_true_tab += str(cputime_success_true) + "\t"
            cputime_success_false_tab += str(cputime_success_false) + "\t"
            cpuenergy_success_tab += str(cpuenergy_success) + "\t"

            cputime_success = round_time(cputime_success)
            cputime_success_true = round_time(cputime_success_true)
            cputime_success_false = round_time(cputime_success_false)
            cpuenergy_success = round_energy(cpuenergy_success)

            score_link = str(score)
            if score is not None and score != "":
                url = f"{validator_with_suffix(validator, track_details)}.results.{track_details.competition.value}{short_year}_{category}.table.html"
                if "Overall" in category:
                    url = f"{validator_with_suffix(validator, track_details)}.results.{track_details.competition.value}{short_year}.table.html"
                score_link = f"<a href='{url}'>" + score_link + "</a>"
            score_html += f"<td class='value{rank_class}{"" if score != "" else " empty"}'>{score_link}</td>"
            cputime_success_html += _get_html_table_cell(
                cputime_success, "s", rank_class
            )
            cpuenergy_success_html += _get_html_table_cell(
                cpuenergy_success, "J", rank_class
            )

            # CSV file for Quantile Plot
            if score is not None and score != "":
                cputime_path = QPLOT_PATH / Path(
                    f"QPLOT.{category}.{validator}.quantile-plot.{post_fix}.csv"
                )

                write_csv(
                    cputime_path,
                    results[validator].qplot_cputime,
                    processed_categories[category],
                    track_details.competition,
                )
                cpuenergy_path = QPLOT_PATH / Path(
                    f"QPLOT.{category}.{validator}.quantile-plot.{post_fix}.csv"
                )

                write_csv(
                    cpuenergy_path,
                    results[validator].qplot_cpuenergy,
                    processed_categories[category],
                    track_details.competition,
                )

        # end for validator

        tab_string += (
            "\n".join(
                [
                    score_tab,
                    cputime_success_tab,
                    cputime_success_true_tab,
                    cputime_success_false_tab,
                    cpuenergy_success_tab,
                    correct_true_tab,
                    correct_false_tab,
                    unconfirmed_true_tab,
                    unconfirmed_false_tab,
                    incorrect_true_tab,
                    incorrect_false_tab,
                ]
            )
            + "\n"
        )

        if category in meta_categories["Overall"]["categories"] or category.endswith(
            "Overall"
        ):
            trprefix = "main"
        else:
            trprefix = "sub"
        html_string += (
            "\n".join(
                [
                    "\t<tr class='" + trprefix + " score' id='" + category + "'>",
                    score_html,
                    "\t</tr>",
                    "\t<tr class='" + trprefix + " cputime'>",
                    cputime_success_html,
                    "\t</tr>",
                ]
            )
            + "\n"
        )
        sizeclass = ""
        if category == "Overall":
            sizeclass = " colspan='2'"
        if trprefix == "main" and len(best_validators) >= 3:
            html_ranking_string += (
                "    <td class='rank'"
                + sizeclass
                + ">\n"
                + f"      <span class='title'>{category_link}</span>"
                + "<br />\n"
                + "        <span class='rank gold'  >1. "
                + utils.get_tool_link(tools, best_validators[0])
                + "</span> <br />\n"
                + "        <span class='rank silver'>2. "
                + utils.get_tool_link(tools, best_validators[1])
                + "</span> <br />\n"
                + "        <span class='rank bronze'>3. "
                + utils.get_tool_link(tools, best_validators[2])
                + "</span> <br />\n"
                + f"        {quantile_link.replace('tinyplot', 'plot')}\n"
                + "    </td>\n"
            )
        # we want a line break after three categories when printing the category ranking above
        # the detailed table.
        if (
            final_category_ranking_counter % 3 == 0
            and final_category_ranking_counter > 0
        ):
            html_ranking_string += "  </tr>\n" + "  <tr>\n"
        if category in meta_categories:
            final_category_ranking_counter += 1
        # Dump ranking table
        if category in meta_categories["Overall"]["categories"] or category.endswith(
            "Overall"
        ):
            tex_ranking_string += (
                "\\hline"
                + "\n"
                + "\\rankcategory{"
                + category
                + "}&&&&& \\placeholderrank{}\\\\"
                + "\n"
            )

            # used if category has less than three participants
            empty = CategoryData(
                Decimal(0), Decimal(0), Decimal(0), Decimal(0), Decimal(0)
            )
            category_result_empty = CategoryResult(
                Decimal(0), Decimal(0), empty, empty, 0, 0, 0, 0, 0, 0, [], [], ""
            )
            for rank, validator in enumerate(best_validators):
                result = results[validator] if validator else category_result_empty
                validator = validator if validator else "no more participants"
                score_tex = str(round(result.score))
                cputime = result.cputime.success
                count_correct = result.correct_true + result.correct_false
                count_incorrect_false = result.incorrect_false
                count_incorrect_true = result.incorrect_true
                if category.startswith(FALSIFIER_PREFIX):
                    score_tex = str(round(result.score_false))
                    cputime = result.cputime.success_false
                    count_correct = result.correct_false
                    count_incorrect_false = result.incorrect_false
                    count_incorrect_true = ""

                validator_tex = "\\ranktool{\\" + re.sub("[-0-9]", "", validator) + "}"
                if rank == 0:
                    score_tex = "\\bfseries " + score_tex + ""
                    validator_tex = "\\win{" + validator_tex + "}"
                tex_ranking_string += (
                    ""
                    + str(rank + 1)
                    + " & "
                    + validator_tex
                    + " & "
                    + score_tex
                    + " & "
                    + str(round_time(cputime / 3600))
                    + " & "
                    + str(count_correct)
                    + " & "
                    + str(count_incorrect_false if count_incorrect_false != 0 else "")
                    + " & {\\bfseries "
                    + str(count_incorrect_true if count_incorrect_true != 0 else "")
                    + "} "
                    + "\\\\"
                    + "\n"
                )

    # end for category
    tab_string += validator_tab + "\n"
    html_string += (
        "\t<tr class='head'>\n" + validator_html + "\n\t</tr>\n" + "</tbody></table>\n"
    )
    html_ranking_string += """
  </tr>
</table>
"""

    # Result table in TeX
    tex_results_header_string = (
        "\\\\[-\\normalbaselineskip]"
        + """
  \\begin{minipage}[b]{25mm}
  {\\normalsize\\bfseries Participant}\\\\
  {}
  \\end{minipage}
  \\colspace{}
"""
    )
    write_text(get_path_texresults(post_fix), tex_results_header_string)
    # Header for results table
    for category in categories_table_order:
        if category not in meta_categories["Overall"][
            "categories"
        ] and not category.endswith("Overall"):
            continue
        tasks_total = processed_categories[category].tasks
        if category.startswith(FALSIFIER_PREFIX):
            possible_score = round(processed_categories[category].possible_score_false)
        else:
            possible_score = round(processed_categories[category].possible_score)
        tex_results_header_string = (
            "& \\colspace{}"
            + "\\up{\\bfseries "
            + str(category)
            + "} "
            + "\\up{"
            + str(possible_score)
            + " points}"
            + "\\up{"
            + str(tasks_total)
            + " tasks}"
            + "\\colspace{}"
        )
        write_text(get_path_texresults(suffix=post_fix), tex_results_header_string)
    write_text(get_path_texresults(suffix=post_fix), "\\\\")

    # Body rows for results table
    validators = [x for x in validators if x is not None]
    for validator in validators:
        tex_results_stringscore = (
            "\\hlineresults"
            + "\n"
            + "{\\bfseries\\scshape \\"
            + re.sub("[-0-9]", "", validator)
            + "} \\spaceholder"
        )
        for category in categories_table_order:
            if category.startswith(FALSIFIER_PREFIX):
                best_validators = get_best(
                    processed_categories[category],
                    track_details,
                    tools,
                    is_falsification=True,
                )
            else:
                best_validators = get_best(
                    processed_categories[category],
                    track_details,
                    tools,
                    is_falsification=False,
                )
            if category not in meta_categories["Overall"][
                "categories"
            ] and not category.endswith("Overall"):
                continue
            results = processed_categories[category].results
            if validator not in results.keys():
                score = "\\none"
            else:
                if category.startswith(FALSIFIER_PREFIX):
                    score = results[validator].score_false
                else:
                    score = results[validator].score
                score = str(round(score))
                if len(best_validators) >= 3:
                    if validator == best_validators[0]:
                        score = "\\gold{" + score + "}"
                    elif validator == best_validators[1]:
                        score = "\\silver{" + score + "}"
                    elif validator == best_validators[2]:
                        score = "\\bronze{" + score + "}"
            tex_results_stringscore += " & " + score
        tex_results_stringscore += "\\\\[-0.2ex]"
        write_text(get_path_texresults(suffix=post_fix), tex_results_stringscore)

    write_text(get_path_tabscores(suffix=post_fix), tab_string)
    write_text(get_path_htmlscores(suffix=post_fix), html_ranking_string)
    write_text(get_path_htmlscores(suffix=post_fix), html_string)
    write_text(get_path_texranking(suffix=post_fix), tex_ranking_string)


def handle_category(
    category,
    results_path,
    category_info,
    tools: FmToolsCatalog,
    track_details: TrackDetails,
    processed_categories=None,
):
    msg_to_output("Processing category " + str(category) + ".")
    if category in get_categories(category_info):
        info = handle_meta_category(
            category, category_info, processed_categories, track_details
        )
    else:
        info = handle_base_category(
            category, results_path, category_info, track_details, tools
        )
    if not info:
        return category, ValidationCategory(category, 0, [], [], 0, 0, 0, 0)
    logging.info("Category " + category + " done.")
    return category, info


def concatenate_dict(dict1, dict2):
    return dict(list(dict1.items()) + list(dict2.items()))


def handle_categories_parallel(
    category_names,
    results_path,
    category_info,
    tools: FmToolsCatalog,
    track_details: TrackDetails,
    processed_categories=None,
):
    # Use enough processes such that all categories can be processed in parallel
    with Pool(int(os.cpu_count())) as parallel:
        # with Pool(1) as parallel:
        handle_category_with_info_set = partial(
            handle_category,
            results_path=results_path,
            category_info=category_info,
            tools=tools,
            track_details=track_details,
            processed_categories=processed_categories,
        )
        result_categories = parallel.map(handle_category_with_info_set, category_names)
        return dict(result_categories)


def parse(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--category",
        required=False,
        default="benchmark-defs/category-structure.yml",
        help="path to categories.yml",
    )
    parser.add_argument(
        "--results_path",
        required=False,
        type=Path,
        default="./results-validated",
        help="path to validation-run results",
    )
    parser.add_argument(
        "--verbose",
        required=False,
        default=False,
        action="store_true",
        help="verbose output",
    )
    parser.add_argument(
        "--witness",
        required=True,
        choices=["violation", "correctness"],
        help="which kind of witness to process (correctness, violation)",
    )
    parser.add_argument(
        "--witness-version",
        required=True,
        choices=["1.0", "2.0"],
        help="which version of witness to process (1.0, 2.0)",
    )
    parser.add_argument(
        "--fm-tools",
        default=Path("fm-tools/data"),
        type=Path,
        help="where to find the fm-tools directory",
    )
    args = parser.parse_args(argv)

    args.category = Path(args.category)

    if not args.category.exists:
        raise FileNotFoundError(f"Category file {args.category} does not exist")
    if not args.results_path.exists or not args.results_path.is_dir():
        raise FileNotFoundError(f"Results directory {args.results_path} does not exist")
    return args


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    args = parse(argv)
    if args.verbose:
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO
    logging.init(log_level, name="mkAnaScoresValidators")

    tools = FmToolsCatalog(args.fm_tools)

    witness_kind = args.witness
    assert witness_kind in (
        "violation",
        "correctness",
    ), f"Invalid witness kind: {witness_kind}"
    witness_version = args.witness_version
    assert witness_version in (
        "1.0",
        "2.0",
    ), f"Invalid witness version: {witness_version}"

    suffix = f"{witness_kind}-{witness_version}"
    track = {
        "violation-1.0": Track.Validation_Violation_1_0,
        "violation-2.0": Track.Validation_Violation_2_0,
        "correctness-1.0": Track.Validation_Correct_1_0,
        "correctness-2.0": Track.Validation_Correct_2_0,
    }[suffix]

    global results_path
    results_path = args.results_path
    categories_yml = args.category

    with open(categories_yml) as inp:
        try:
            ctgry_info = yaml.load(inp, Loader=yaml.FullLoader)
        except yaml.YAMLError as e:
            logging.error(e)
            sys.exit(1)

    meta_categories = {
        c: k for c, k in get_categories(ctgry_info).items() if "Java" not in c
    }
    demo_categories = get_demo_categories(ctgry_info)
    categories_process_order = [
        c for c in get_all_categories_process_order(ctgry_info) if "Java" not in c
    ]

    base_categories = [
        category
        for category in categories_process_order
        if category not in meta_categories
    ]
    base_categories_for_metas = [
        base_cat for base_cat in base_categories if base_cat not in demo_categories
    ]
    base_categories_for_metas = [base_cat for base_cat in base_categories_for_metas]

    track_details = TrackDetails(
        utils.competition_from_string(ctgry_info["competition"]),
        track,
        ctgry_info["year"],
    )

    meta_categories = [
        category
        for category in categories_process_order
        if category in meta_categories and not category.endswith("Overall")
    ]

    # First handle base categories (on the results of which the meta categories depend)
    processed_categories = handle_categories_parallel(
        base_categories, results_path, ctgry_info, tools, track_details
    )
    msg_to_output("Base categories done.")

    # Second meta categories
    for category in meta_categories:
        processed_categories = concatenate_dict(
            processed_categories,
            dict(
                [
                    handle_category(
                        category,
                        results_path,
                        ctgry_info,
                        tools,
                        track_details,
                        processed_categories,
                    )
                ]
            ),
        )
    msg_to_output("Meta categories done.")
    # Third 'Overall' categories consisting of some meta- and some base categories
    # Since 'Overall' is a meta category, it is already very fast and no parallelization is needed.
    processed_categories = concatenate_dict(
        processed_categories,
        dict(
            [
                handle_category(
                    "Overall",
                    results_path,
                    ctgry_info,
                    tools,
                    track_details,
                    processed_categories,
                )
            ]
        ),
    )
    msg_to_output("Overall done.")

    msg_to_output("Dumping TSV and HTML.")
    remove_file(get_path_htmlscores(suffix))
    remove_file(get_path_tabscores(suffix))
    remove_file(get_path_rsfscores(suffix))
    remove_file(get_path_texranking(suffix))
    remove_file(get_path_texresults(suffix))
    dump_output_files(processed_categories, track_details, tools, ctgry_info)
    msg_to_output("Finished.")


if __name__ == "__main__":
    sys.exit(main())
