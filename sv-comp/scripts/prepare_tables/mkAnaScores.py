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
import re
import sys
from decimal import Decimal
from functools import partial
from multiprocessing import Pool
from pathlib import Path
from typing import Optional, List, Tuple

import utils
import benchexec.result as result
import benchexec.tablegenerator as tablegenerator
import yaml

from prepare_tables.utils import get_tool_html_and_tab, TrackDetails

from fm_tools.competition_participation import Competition, string_to_Competition, Track
from fm_tools.fmtoolscatalog import FmToolsCatalog

import _logging as logging
from utils import (
    round_time,
    round_energy,
    VerificationCategory,
    accumulate_data,
    combine_qplots,
    CategoryResult,
    is_tool_status_false,
    CategoryData,
    category_sum,
    get_member_lines,
    get_tool_link,
    competition_from_string,
)
from utils import get_competition_tools


sys.path.append(str(Path(__file__).parent.parent.resolve() / "test"))

Util = tablegenerator.util

SCORE_COLUMN_NAME = "score"
""""Name (title) of the score column in run result XMLs."""


FALSIFIER_PREFIX = "Falsification"

# global variables used to exchange info between methods
TABLENAME = None
HTMLSCORES = None
TABSCORES = None
RSFSCORES = None
TEXRANKING = None
TEXRESULTS = None
QPLOT_PATH = None


def msg_to_output(msg):
    print(msg)


def err_to_output(err):
    print(err)


DATE = "????-??-??_??-??-??"

####################################
####################################
###### Real code begins here #######
####################################
####################################


def write_text(path, text):
    # Only compatible to python > 3.5
    # path.write_text(text)
    with open(str(path), "a") as f:
        f.write(text + "\n")


def read_text(path):
    # Only compatible to python > 3.5
    # return path.read_text()
    with open(str(path), "r") as f:
        return f.read()


def write_to_rfs(category, verifier, rows: List[Tuple[str, str]]):
    string = "\n".join(["\t".join([category, verifier, r[0], r[1]]) for r in rows])
    write_text(RSFSCORES, string)


def get_results_XML_file(
    category, verifier, results_path, competition: Competition, year: int
):
    # Get xml results file for each verifier and category
    # - if a fixed.xml file exists, we take it.
    # Otherwise, we take the default xml file.
    # If none exists, we assume the verifier didn't take part in the category.
    results_file_no_merged_string = (
        str(verifier)
        + "."
        + DATE
        + ".results."
        + competition.value
        + str(year)[-2:]
        + "_"
        + category
        + ".xml.bz2"
    )
    results_file_merged_string = results_file_no_merged_string + ".fixed.xml.bz2"
    try:
        xml_files = list(results_path.glob(results_file_merged_string))
        if not xml_files:
            logging.debug(
                "No results file '*.fixed.*' with validator info for tool %s and category %s. Trying to use original results XML.",
                verifier,
                category,
            )
            xml_files = list(results_path.glob(results_file_no_merged_string))
        if len(xml_files) > 1:
            xml_files = sorted(
                xml_files, reverse=True
            )  # sorts by date due to file name structure
        if not xml_files:
            logging.debug(
                "No results file for verifier %s and category %s. Used string: %s",
                verifier,
                category,
                results_file_merged_string,
            )
            return None
        return str(xml_files[0])
    except Exception as e:
        logging.exception("Exception for %s: %s", results_file_merged_string, e)
        return None


def handle_meta_category(meta_category, category_info, processed_categories):
    categories = get_categories(category_info)
    try:
        demo_categories = get_demo_categories(category_info)
    except KeyError:
        demo_categories = list()
    subverifiers = [
        v
        for v in categories[meta_category]["verifiers"]
        if meta_category not in category_info["validation_only"]
    ]

    subcategories = {
        sub: processed_categories[sub]
        for sub in [
            c
            for c in categories[meta_category]["categories"]
            if c not in category_info["validation_only"]
        ]
        if sub not in demo_categories
        and (
            processed_categories[sub].tasks_true + processed_categories[sub].tasks_false
        )
        != 0
    }
    subcategories_info = list(subcategories.values())
    category_amount = len(subcategories)
    tasks_total = sum([c.tasks for c in subcategories_info])
    tasks_true = sum([c.tasks_true for c in subcategories_info])
    tasks_false = sum([c.tasks_false for c in subcategories_info])
    if meta_category == "FalsificationOverall":
        tasks_true -= 91
        tasks_false -= 176

    def normalize_score(score):
        return score / category_amount * (tasks_true + tasks_false)

    # TODO: Eliminate once property Termination is part of FalsficationOverall.
    def normalize_score_false(score):
        if meta_category == "SoftwareSystems":
            return score / (category_amount - 1) * (tasks_true + tasks_false - 267)
        return normalize_score(score)

    # Comment this assert if you want to allow empty categories
    assert not [
        n for n, c in subcategories.items() if (c.tasks_true + c.tasks_false) == 0
    ], "Empty categories for meta category %s: %s" % (
        meta_category,
        [n for n, c in subcategories.items() if (c.tasks_true + c.tasks_false) == 0],
    )

    # Sum of each category's normalized score, normalized according to the number of tasks of that individual category
    possible_score = sum(
        [
            Decimal(c.possible_score) / (c.tasks_true + c.tasks_false)
            for c in subcategories_info
            if (c.tasks_true + c.tasks_false) != 0
        ]
    )
    possible_score = normalize_score(possible_score)  # 3.05 * 100 / 2

    # TODO: Eliminate special case once property Termination is part of FalsficationOverall.
    # (1) Sum up
    possible_score_false = 0
    for name, cat in subcategories.items():
        tasks_in_subcategory = cat.tasks_true + cat.tasks_false
        if name in "SoftwareSystems":
            tasks_in_subcategory -= 267
        if (tasks_in_subcategory) != 0:
            possible_score_false += (
                Decimal(cat.possible_score_false) / tasks_in_subcategory
            )
    # (1) Normalize
    possible_score_false = normalize_score_false(possible_score_false)

    cat_info = VerificationCategory(
        meta_category,
        tasks_total,
        tasks_true,
        tasks_false,
        possible_score,
        possible_score_false,
    )

    for verifier in subverifiers:
        subcategories_available = [
            c
            for c in subcategories_info
            if verifier in c.results and c not in demo_categories
        ]
        if len(subcategories_available) < len(subcategories):
            logging.info(
                "Not considering verifier %s for category %s because of missing sub-categories. Available sub-categories: %s",
                verifier,
                meta_category,
                [c.name for c in subcategories_available],
            )
            continue
        relevant_results = [c.results[verifier] for c in subcategories_available]

        # can't use relevant_results here because we need the number of total tasks per category
        sum_of_avg_scores = sum(
            [
                Decimal(c.results[verifier].score) / (c.tasks_true + c.tasks_false)
                for c in subcategories_info
                if verifier in c.results.keys() and (c.tasks_true + c.tasks_false) != 0
            ]
        )
        score = normalize_score(sum_of_avg_scores)

        sum_of_avg_scores_false = 0
        for name, cat in subcategories.items():
            tasks_in_subcategory = cat.tasks_true + cat.tasks_false
            if name in "SoftwareSystems":
                tasks_in_subcategory -= 267
            if verifier in cat.results.keys() and tasks_in_subcategory != 0:
                sum_of_avg_scores_false += Decimal(
                    cat.results[verifier].score_false
                ) / (tasks_in_subcategory)
        score_false = normalize_score_false(sum_of_avg_scores_false)

        cputime_data = accumulate_data([r.cputime for r in relevant_results])
        cpuenergy_data = accumulate_data([r.cpuenergy for r in relevant_results])

        correct_false = sum(
            [
                c.results[verifier].correct_false or 0
                for c in subcategories_info
                if verifier in c.results.keys()
            ]
        )
        correct_true = sum(
            [
                c.results[verifier].correct_true or 0
                for c in subcategories_info
                if verifier in c.results.keys()
            ]
        )
        correct_unconfirmed_false = sum(
            [
                c.results[verifier].correct_unconfirmed_false or 0
                for c in subcategories_info
                if verifier in c.results.keys()
            ]
        )
        correct_unconfirmed_true = sum(
            [
                c.results[verifier].correct_unconfirmed_true or 0
                for c in subcategories_info
                if verifier in c.results.keys()
            ]
        )
        incorrect_false = sum(
            [
                c.results[verifier].incorrect_false or 0
                for c in subcategories_info
                if verifier in c.results.keys()
            ]
        )
        incorrect_true = sum(
            [
                c.results[verifier].incorrect_true or 0
                for c in subcategories_info
                if verifier in c.results.keys()
            ]
        )

        qplot_cputime = combine_qplots(
            [
                c.results[verifier].qplot_cputime
                for c in subcategories_info
                if verifier in c.results.keys()
            ],
            category_amount,
        )
        qplot_cpuenergy = combine_qplots(
            [
                c.results[verifier].qplot_cpuenergy
                for c in subcategories_info
                if verifier in c.results.keys()
            ],
            category_amount,
        )

        cat_info.results[verifier] = CategoryResult(
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
    column_name: str, run_set_result: tablegenerator.RunSetResult
) -> List[Decimal]:
    column_index = _get_column_index(column_name, run_set_result)
    if column_index is None:
        return list()

    return [Util.to_decimal(r.values[column_index]) for r in run_set_result.results]


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


def get_score(
    run_result: tablegenerator.RunResult, competition: Competition
) -> Optional[Decimal]:
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
    if score is None:
        if competition == Competition.SV_COMP:
            return None
        else:
            score = Decimal(0.0)

    return score


def _get_scores_data(
    run_set_result: tablegenerator.RunSetResult,
    category: str,
    verifier: str,
    competition: Competition,
) -> dict[str, Decimal]:
    score, score_false = 0, 0
    correct_true, correct_false = 0, 0
    correct_unconfirmed_true, correct_unconfirmed_false = 0, 0
    incorrect_true, incorrect_false = 0, 0

    for run_result in run_set_result.results:
        run_result.score = get_score(run_result, competition)

        if run_result.score is None:
            logging.warning(
                'Score missing for task "{0}" (category "{1}", verifier "{2}"), cannot produce score-based quantile data.'.format(
                    run_result.task_id[0], category, verifier
                )
            )
            continue

        score += run_result.score
        if (
            is_tool_status_false(run_result.status)
            and category
            != "termination.SoftwareSystems-DeviceDriversLinux64-Termination"
        ):
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

    expected_score = (
        correct_false * 1
        + correct_true * 2
        + correct_unconfirmed_true * 0
        + correct_unconfirmed_false * 0
        + incorrect_false * -16
        + incorrect_true * -32
    )
    assert competition != Competition.SV_COMP or score == expected_score
    expected_score = (
        correct_false * 1 + correct_unconfirmed_false * 0 + incorrect_false * -16
    )
    if category != "termination.SoftwareSystems-DeviceDriversLinux64-Termination":
        assert competition != Competition.SV_COMP or score_false == expected_score

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


def get_category_info(
    run_set_result: tablegenerator.RunSetResult, category: str
) -> Optional[VerificationCategory]:
    rows = tablegenerator.get_rows([run_set_result])
    score_column_index = _get_column_index(SCORE_COLUMN_NAME, run_set_result)
    tasks_total = len(rows)

    count_true = 0
    count_false = 0
    possible_score = 0  # We use 0 instead of None because this avoids many special cases for algorithmic computations later on.
    possible_score_false = 0

    if score_column_index is None:
        logging.debug("Computing our own score for %s", category)
        # No explicit score column given => calculate scores and counts.
        # Using scores computed by table generator is not possible,
        # since we need to exclude the invalid tasks (with category 'missing').
        for run_result in run_set_result.results:
            if run_result.category != result.CATEGORY_MISSING:
                if run_result.task_id.expected_result.result:
                    count_true += 1
                else:
                    count_false += 1
        possible_score = (
            count_true * result._SCORE_CORRECT_TRUE
            + count_false * result._SCORE_CORRECT_FALSE
        )
        possible_score_false = count_false * result._SCORE_CORRECT_FALSE
        if category == "termination.SoftwareSystems-DeviceDriversLinux64-Termination":
            possible_score_false = 0
    # else:
    # Test-Comp, for example, has a score column, and we cannot say what the maximal score is.

    # For Test-Comp, we cannot distinguish between true and false, so by convention, all are counted as true.
    if ".results.Test-Comp25_coverage-" in run_set_result.attributes["filename"][0]:
        count_true = tasks_total

    if count_true + count_false == 0:
        logging.debug(
            "No valid tasks for category %s, returning no category info", category
        )
        return None
    return VerificationCategory(
        category,
        tasks_total,
        count_true,
        count_false,
        possible_score,
        possible_score_false,
    )


def _get_qplot_data(
    run_set_result: tablegenerator.RunSetResult,
    values: List[Decimal],
    tasks_total_valid: int,
    category: str,
    verifier: str,
    competition: Competition,
) -> List[Tuple[float, float, str]]:
    """
    Return list of tuples (normalized_score, value, status).
    Each tuple represents one run result with its score, the
    corresponding value from the given value list, and the run's status.
    """
    # TODO: Replace returned tuple by dict with speaking names as keys

    qplot_data = []
    for run_result, curr_value in zip(run_set_result.results, values):
        if (
            run_result.category == result.CATEGORY_WRONG
            or run_result.category == result.CATEGORY_CORRECT
            or run_result.category == result.CATEGORY_CORRECT_UNCONFIRMED
            or competition != Competition.SV_COMP
        ):
            qplot_data.append(
                (
                    float(run_result.score) / tasks_total_valid,
                    curr_value,
                    run_result.status,
                )
            )
        elif run_result.category == result.CATEGORY_MISSING:
            if not run_result.status.startswith("invalid task ("):
                logging.warning(
                    'Result category missing for status "{0}" and task "{1}" (category "{2}", verifier "{3}"), cannot produce score-based quantile data.'.format(
                        run_result.status, run_result.task_id[0], category, verifier
                    )
                )
        else:
            assert run_result.category in {
                result.CATEGORY_ERROR,
                result.CATEGORY_UNKNOWN,
                "aborted",
            }, f"Unexpected category '{run_result.category}'"
    return qplot_data


def get_categories(category_info):
    """Returns the defined meta-categories of the given category info"""
    return {
        c: category_info["categories"][c]
        for c in category_info["categories"]
        if all(k not in c for k in category_info["validation_only"])
    }


def get_demo_categories(category_info):
    try:
        return category_info["demo_categories"]
    except KeyError:
        # no demo categories in category info
        return list()


def get_all_categories_table_order(category_info):
    return [
        c
        for c in category_info["categories_table_order"]
        if c not in category_info["validation_only"]
    ]


def get_all_categories_process_order(category_info):
    return [
        c
        for c in category_info["categories_process_order"]
        if c not in category_info["validation_only"]
    ]


def handle_base_category(
    category, results_path, track_details: TrackDetails, fm_tools: FmToolsCatalog
):
    cat_info = None
    for verifier in get_competition_tools(fm_tools, track_details):
        results_file = get_results_XML_file(
            category,
            verifier,
            results_path,
            track_details.competition,
            track_details.year,
        )
        if results_file is None:
            continue
        # print(verifier)
        # load results
        run_set_result = tablegenerator.RunSetResult.create_from_xml(
            results_file, tablegenerator.parse_results_file(results_file)
        )
        run_set_result.collect_data(False)

        if cat_info is None or cat_info.tasks == 0:
            cat_info = get_category_info(run_set_result, category)
            if cat_info is None:
                logging.debug("No tasks in category %s for %s", category, verifier)
                continue

        # Collect data points (score, cputime, status) for generating quantile plots.
        score_data = _get_scores_data(
            run_set_result, category, verifier, track_details.competition
        )
        cputime = _create_category_data("cputime", run_set_result)
        cpuenergy = _create_category_data("cpuenergy", run_set_result)

        if not cputime.sequence:
            logging.debug("CPU time missing for {0}, {1}".format(verifier, category))
        if not cpuenergy.sequence:
            logging.debug("CPU energy missing for {0}, {1}".format(verifier, category))

        get_qplot = partial(
            _get_qplot_data,
            run_set_result=run_set_result,
            tasks_total_valid=cat_info.tasks_true + cat_info.tasks_false,
            category=category,
            verifier=verifier,
            competition=track_details.competition,
        )

        qplot_data_cputime = get_qplot(values=cputime.sequence)
        qplot_data_cpuenergy = get_qplot(values=cpuenergy.sequence)

        cat_info.results[verifier] = CategoryResult(
            cputime=cputime,
            qplot_cputime=qplot_data_cputime,
            cpuenergy=cpuenergy,
            qplot_cpuenergy=qplot_data_cpuenergy,
            results_file=results_file,
            **score_data,
        )  # expands to the individual score parameters
    return cat_info


def get_best(
    category,
    category_info,
    fm_tools_catalog: FmToolsCatalog,
    is_falsification: bool = False,
):
    year = int(category_info["year"])
    competition = string_to_Competition(category_info["competition"])
    track = (
        Track.Verification
        if competition == Competition.SV_COMP
        else Track.Test_Generation
    )
    competitors = [
        (v, r)
        for v, r in category.results.items()
        if not utils.is_hors_concours(fm_tools_catalog, v, year, competition, track)
        and not is_opt_out(category.name, verifier=v, category_info=category_info)
        and (category.tasks_true + category.tasks_false) != 0
    ]
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
    if (
        len(result) < 3
        and len(result) > 0
        and category.name not in get_demo_categories(category_info)
    ):
        logging.warning(
            "Less than three verifiers in category %s. Verifiers: %s",
            category.name,
            [v for v, r in competitors],
        )
    while len(result) < 3:
        result.append(None)
    return result


def is_opt_out(category, verifier, category_info):
    # The OPT_OUT has higher dominance than the OPT_IN (i.e. if a verifier, category is on the OPT_OUT,
    # it doesn't matter whether the same pair is on the OPT_IN - it is not displayed)
    if "opt_out" not in category_info or not category_info["opt_out"]:
        return False  # there are no opt outs at all, so the queried one can't be one
    opt_out = category_info["opt_out"]
    return verifier in opt_out and category in opt_out[verifier]


def prepare_qplot_csv(
    qplot: list, processed_category: VerificationCategory, competition: Competition
) -> Optional[List[Tuple]]:
    category_tasks = processed_category.tasks_true + processed_category.tasks_false
    if not qplot:
        return None

    x_and_y_list = list()
    if processed_category.name.startswith(FALSIFIER_PREFIX):
        qplot_data = [
            (s, c, st)
            for (s, c, st) in qplot
            if is_tool_status_false(st)
            and processed_category.name
            != "termination.SoftwareSystems-DeviceDriversLinux64-Termination"
        ]
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
    else:
        # Left-most data-point is zero for Test-Comp
        index = 0.0
        score_accum = 0.0
        # Data points for score/coverage
        qplot_ordered = [(score, value) for score, value, _ in qplot_data if score >= 0]
        qplot_ordered.sort(key=lambda entry: -entry[0])
        for score, value in qplot_ordered:
            index += 1.0
            score_accum += float(score) * category_tasks
            x_and_y_list.append((score_accum, index))

    return x_and_y_list


def write_csv(
    path: Path,
    qplot_data: list,
    processed_category: VerificationCategory,
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


def dump_output_files(
    processed_categories,
    category_info,
    track_details: TrackDetails,
    fm_tools_catalog: FmToolsCatalog,
):
    verifiers = get_competition_tools(fm_tools_catalog, track_details)
    verifier_without_witnessmap = [v for v in verifiers if v != "witnessmap"]
    verifier_html, verifier_tab = get_tool_html_and_tab(
        fm_tools_catalog,
        verifier_without_witnessmap,
        track_details.competition,
        track_details.year,
    )
    html_string = (
        """
<hr/>
<h2>Table of All Results</h2>

<p>
In every table cell for competition results,
we list the points in the first row and the CPU time (rounded to two significant digits) for successful runs in the second row.
</p>

<p>
The entry '&ndash;' means that the competition candidate opted-out in the category.<br/>
The definition of the <a href="../../rules.php#scores">scoring schema</a>
and the <a href="../../benchmarks.php">categories</a> is given on the respective SV-COMP web pages.
</p>

<p>
<input type='checkbox' id='hide-base-categories' onclick="$('.sub').toggle()"><label id='hide-base-categories-label' for='hide-base-categories'>Hide base categories</label>
</p>
"""
        + "<table id='scoretable'>\n"
        + "<thead>\n"
        + "\t<tr class='head'>\n"
        + verifier_html
        + "\n\t</tr>\n"
        + "</thead>\n<tbody>"
        + get_member_lines(
            verifier_without_witnessmap,
            fm_tools_catalog,
            track_details,
        )
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
    demo_categories = get_demo_categories(category_info)
    categories_table_order = get_all_categories_table_order(category_info)

    for category in categories_table_order:
        tasks_total = processed_categories[category].tasks
        tasks_true = processed_categories[category].tasks_true
        tasks_false = processed_categories[category].tasks_false
        if tasks_true + tasks_false == 0:
            continue
        if category.startswith(FALSIFIER_PREFIX):
            possible_score = round(processed_categories[category].possible_score_false)
            best_verifiers = get_best(
                processed_categories[category],
                category_info,
                fm_tools_catalog,
                is_falsification=True,
            )
        else:
            possible_score = round(processed_categories[category].possible_score)
            best_verifiers = get_best(
                processed_categories[category], category_info, fm_tools_catalog
            )
        score_tab = category + "\t" + str(tasks_true + tasks_false) + "\t"
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
        if category in meta_categories:
            prefix = "META_"
        else:
            prefix = ""
            categoryname = category.split(".")[1]
        filename = prefix + category

        score_html = (
            f"\t<td class='category-name'><a href='{filename}.table.html'>{categoryname}</a><br />"
            + f"<span class='stats'>{str(tasks_true + tasks_false)} valid tasks"
        )
        if track_details.competition == Competition.SV_COMP:
            score_html += f" ({str(tasks_true)} true, {str(tasks_false)} false, {str(tasks_total - (tasks_true + tasks_false))} void)"
        if possible_score:
            score_html += ", max. score: " + str(possible_score)
        quantile_link = ""
        quantile_file = f"quantilePlot-{category}.svg"
        if os.path.exists(f"results-verified/{quantile_file}"):
            quantile_link = f"<a href='{quantile_file}'><img class='tinyplot' src='{quantile_file}' alt='Quantile-Plot' /></a>"
        score_html += f"</span></td>\n<td class='tinyplot'>{quantile_link}</td>\n"
        cputime_success_html = "\t<td>CPU time</td><td></td>"
        cpuenergy_success_html = "\t<td>CPU energy</td><td></td>"

        write_text(
            RSFSCORES,
            categoryname
            + "\tTASKSTOTAL\t"
            + str(processed_categories[category].tasks)
            + "\n"
            + categoryname
            + "\tTASKSTRUE\t"
            + str(processed_categories[category].tasks_true)
            + "\n"
            + categoryname
            + "\tTASKSFALSE\t"
            + str(processed_categories[category].tasks_false)
            + "\n"
            + categoryname
            + "\tMAXSCORE\t"
            + str(possible_score),
        )

        results = processed_categories[category].results
        for verifier in verifier_without_witnessmap:
            if verifier not in results.keys() or is_opt_out(
                category, verifier, category_info
            ):
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
                    score = results[verifier].score_false
                    # assert round(score) == round(results[verifier].correct_false * 1 + results[verifier].incorrect_false * -16)
                    cputime_success = results[verifier].cputime.success_false
                    cputime_success_true = None
                    cputime_success_false = cputime_success
                    cpuenergy_success = results[verifier].cpuenergy.success_false
                else:
                    score = results[verifier].score
                    # assert round(score) == round(results[verifier].correct_false * 1 + results[verifier].correct_true * 2 \
                    #                             + results[verifier].incorrect_false * -16 + results[verifier].incorrect_true * -32)
                    cputime_success = results[verifier].cputime.success
                    cputime_success_true = results[verifier].cputime.success_true
                    cputime_success_false = results[verifier].cputime.success_false
                    cpuenergy_success = results[verifier].cpuenergy.success

                correct_true = results[verifier].correct_true
                correct_false = results[verifier].correct_false
                unconfirmed_true = results[verifier].correct_unconfirmed_true
                unconfirmed_false = results[verifier].correct_unconfirmed_false
                incorrect_true = results[verifier].incorrect_true
                incorrect_false = results[verifier].incorrect_false

                rfs_rows = [
                    ("SCORE", _prepare_for_rfs(score)),
                    ("CPUTIMESUCCESS", _prepare_for_rfs(cputime_success)),
                    ("CPUTIMESUCCESSTRUE", _prepare_for_rfs(cputime_success_true)),
                    ("CPUTIMESUCCESSFALSE", _prepare_for_rfs(cputime_success_false)),
                    ("CPUENERGYSUCCESS", _prepare_for_rfs(cpuenergy_success)),
                    ("CORRECTTRUE", _prepare_for_rfs(correct_true)),
                    ("CORRECTFALSE", _prepare_for_rfs(correct_false)),
                    ("UNCONFIRMEDTRUE", _prepare_for_rfs(unconfirmed_true)),
                    ("UNCONFIRMEDFALSE", _prepare_for_rfs(unconfirmed_false)),
                    ("INCORRECTTRUE", _prepare_for_rfs(incorrect_true)),
                    ("INCORRECTFALSE", _prepare_for_rfs(incorrect_false)),
                ]
                write_to_rfs(categoryname, verifier, rfs_rows)

                score = round(score)
                if score is None:
                    score = ""

            rank_class = ""
            if category in meta_categories["Overall"][
                "categories"
            ] or category.endswith("Overall"):
                if verifier == best_verifiers[0]:
                    rank_class = " gold"
                elif verifier == best_verifiers[1]:
                    rank_class = " silver"
                elif verifier == best_verifiers[2]:
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
                results_file = results[verifier].results_file
                if results_file:
                    score_link = f"<a href='{os.path.basename(results_file)}.table.html'>{score_link}</a>"
                else:
                    score_link = (
                        f"<a href='{filename}_{verifier}.table.html'>{score_link}</a>"
                    )
            score_html += (
                "<td class='value"
                + rank_class
                + ("" if score != "" else " empty")
                + "'>"
                + score_link
                + (
                    "<sup>Demo</sup>"
                    if score != "" and category in demo_categories
                    else ""
                )
                + "</td>"
            )
            cputime_success_html += _get_html_table_cell(
                cputime_success, "s", rank_class
            )
            cpuenergy_success_html += _get_html_table_cell(
                cpuenergy_success, "J", rank_class
            )

            # CSV file for Quantile Plot
            if score is not None and score != "":
                cputime_path = QPLOT_PATH / Path(
                    f"QPLOT.{category}.{verifier}.quantile-plot.csv"
                )

                write_csv(
                    cputime_path,
                    results[verifier].qplot_cputime,
                    processed_categories[category],
                    track_details.competition,
                )
                cpuenergy_path = QPLOT_PATH / Path(
                    f"QPLOT.{category}.{verifier}.quantile-plot-cpuenergy.csv"
                )

                write_csv(
                    cpuenergy_path,
                    results[verifier].qplot_cpuenergy,
                    processed_categories[category],
                    track_details.competition,
                )

        # end for verifier

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
        if trprefix == "main":
            html_ranking_string += (
                "    <td class='rank'"
                + sizeclass
                + ">\n"
                + "      <span class='title'><a href="
                + filename
                + ".table.html>"
                + categoryname
                + "</a></span><br />\n"
                + "        <span class='rank gold'  >1. "
                + get_tool_link(fm_tools_catalog, best_verifiers[0])
                + "</span> <br />\n"
                + "        <span class='rank silver'>2. "
                + get_tool_link(fm_tools_catalog, best_verifiers[1])
                + "</span> <br />\n"
                + "        <span class='rank bronze'>3. "
                + get_tool_link(fm_tools_catalog, best_verifiers[2])
                + "</span> <br />\n"
                + "        <a href='quantilePlot-"
                + categoryname.replace(".", "-")
                + ".svg'><img class='plot' src='quantilePlot-"
                + categoryname.replace(".", "-")
                + ".svg' alt='Quantile-Plot' /></a>\n"
                + "    </td>\n"
            )
            if categoryname in ["ConcurrencySafety", "SoftwareSystems", "Overall"]:
                html_ranking_string += "  </tr>\n" + "  <tr>\n"
        # Dump ranking table
        if category in meta_categories["Overall"]["categories"] or category.endswith(
            "Overall"
        ):
            if category.startswith(FALSIFIER_PREFIX):
                possible_score = round(
                    processed_categories[category].possible_score_false
                )
            else:
                possible_score = round(processed_categories[category].possible_score)
            tex_ranking_string += (
                "\\hline"
                + "\n"
                + "\\rankcategory{"
                + category
                + " \\normalfont\\scriptsize("
                + str(
                    processed_categories[category].tasks_true
                    + processed_categories[category].tasks_false
                )
                + " tasks, max.~score "
                + str(possible_score)
                + ")}\\\\"
                + "\n"
            )
            for rank in range(0, 3):
                verifier = best_verifiers[rank]
                result = results[verifier]
                score_tex = str(round(result.score))
                cputime = result.cputime.success
                count_correct = result.correct_true + result.correct_false
                count_unconfirmed = (
                    result.correct_unconfirmed_true + result.correct_unconfirmed_false
                )
                count_incorrect_false = result.incorrect_false
                count_incorrect_true = result.incorrect_true
                if category.startswith(FALSIFIER_PREFIX):
                    score_tex = str(round(result.score_false))
                    cputime = result.cputime.success_false
                    count_correct = result.correct_false
                    count_unconfirmed = result.correct_unconfirmed_false
                    count_incorrect_false = result.incorrect_false
                    count_incorrect_true = ""

                verifier_tex = "\\ranktool{\\" + re.sub("[-0-9]", "", verifier) + "}"
                if rank == 0:
                    score_tex = "\\bfseries " + score_tex + ""
                    verifier_tex = "\\win{" + verifier_tex + "}"
                tex_ranking_string += (
                    ""
                    + str(rank + 1)
                    + " & "
                    + verifier_tex
                    + " & "
                    + score_tex
                    + " & "
                    + str(round_time(cputime / 3600))
                    # + " & "
                    # + str(round_energy(cpuenergy / 3600000))
                    + " & "
                    + str(count_correct)
                    + " & "
                    + str(count_unconfirmed)
                    + " & "
                    + str(count_incorrect_false if count_incorrect_false != 0 else "")
                    + " & {\\bfseries "
                    + str(count_incorrect_true if count_incorrect_true != 0 else "")
                    + "} "
                    + "\\\\"
                    + "\n"
                )

    # end for category
    tab_string += verifier_tab + "\n"
    html_string += (
        "\t<tr class='head'>\n" + verifier_html + "\n\t</tr>\n" + "</tbody></table>\n"
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
    write_text(TEXRESULTS, tex_results_header_string)
    # Header for results table
    for category in categories_table_order:
        if category not in meta_categories["Overall"][
            "categories"
        ] and not category.endswith("Overall"):
            continue
        if category.startswith(FALSIFIER_PREFIX):
            possible_score = round(processed_categories[category].possible_score_false)
            best_verifiers = get_best(
                processed_categories[category],
                category_info,
                fm_tools_catalog,
                is_falsification=True,
            )
        else:
            possible_score = round(processed_categories[category].possible_score)
            best_verifiers = get_best(
                processed_categories[category], category_info, fm_tools_catalog
            )
        tex_results_header_string = (
            "& \\colspace{}"
            + "\\up{\\bfseries "
            + str(category)
            + "} "
            + "\\up{"
            + str(
                processed_categories[category].tasks_true
                + processed_categories[category].tasks_false
            )
            + " tasks}"
            + "\\,"
            + "\\up{max.~score "
            + str(possible_score)
            + "}"
            + "\\colspace{}"
        )
        write_text(TEXRESULTS, tex_results_header_string)
    write_text(TEXRESULTS, "\\\\")

    # Body rows for results table
    for verifier in verifiers:
        tex_results_stringscore = (
            "\\hlineresults"
            + "\n"
            + "{\\bfseries\\scshape \\"
            + re.sub("[-0-9]", "", verifier)
            + "} \\spaceholder"
        )
        for category in categories_table_order:
            if category.startswith(FALSIFIER_PREFIX):
                best_verifiers = get_best(
                    processed_categories[category],
                    category_info,
                    fm_tools_catalog,
                    is_falsification=True,
                )
            else:
                best_verifiers = get_best(
                    processed_categories[category], category_info, fm_tools_catalog
                )
            if category not in meta_categories["Overall"][
                "categories"
            ] and not category.endswith("Overall"):
                continue
            results = processed_categories[category].results
            if verifier not in results.keys() or is_opt_out(
                category, verifier, category_info
            ):
                score = "\\none"
            else:
                if category.startswith(FALSIFIER_PREFIX):
                    score = results[verifier].score_false
                else:
                    score = results[verifier].score
                score = str(round(score))
                if verifier == best_verifiers[0]:
                    score = "\\gold{" + score + "}"
                elif verifier == best_verifiers[1]:
                    score = "\\silver{" + score + "}"
                elif verifier == best_verifiers[2]:
                    score = "\\bronze{" + score + "}"
            tex_results_stringscore += " & " + score
        tex_results_stringscore += "\\\\[-0.2ex]"
        write_text(TEXRESULTS, tex_results_stringscore)

    write_text(TABSCORES, tab_string)
    write_text(HTMLSCORES, html_ranking_string)
    write_text(HTMLSCORES, html_string)
    write_text(TEXRANKING, tex_ranking_string)


def handle_category(
    category,
    results_path,
    category_info,
    track_details: TrackDetails,
    fm_tools: FmToolsCatalog,
    processed_categories=None,
):
    msg_to_output("Processing category " + str(category) + ".")
    if category in get_categories(category_info):
        info = handle_meta_category(category, category_info, processed_categories)
    else:
        info = handle_base_category(category, results_path, track_details, fm_tools)
    if not info:
        return category, VerificationCategory(category, 0, 0, 0, 0, 0)
    print("Category " + category + " done.")
    return category, info


def concatenate_dict(dict1, dict2):
    return dict(list(dict1.items()) + list(dict2.items()))


def handle_categories_parallel(
    category_names,
    results_path,
    category_info,
    track_details: TrackDetails,
    fm_tools: FmToolsCatalog,
    processed_categories=None,
):
    # Use enough processes such that all categories can be processed in parallel
    with Pool(1) as parallel:
        # with Pool(1) as parallel:
        handle_category_with_info_set = partial(
            handle_category,
            results_path=results_path,
            category_info=category_info,
            processed_categories=processed_categories,
            track_details=track_details,
            fm_tools=fm_tools,
        )
        result_categories = parallel.map(handle_category_with_info_set, category_names)
        return dict(result_categories)


def parse(argv):
    parser = argparse.ArgumentParser()
    base_path = Path(__file__).parent.parent.parent
    parser.add_argument(
        "--category",
        required=False,
        type=Path,
        default=base_path / "benchmark-defs" / "category-structure.yml",
        help="path to categories.yml",
    )
    parser.add_argument(
        "--results-path",
        required=False,
        type=Path,
        default=base_path / "results-verified",
        help="path to verification-run results",
    )
    parser.add_argument(
        "--verbose",
        required=False,
        default=False,
        action="store_true",
        help="verbose output",
    )
    parser.add_argument(
        "--fm-tools",
        required=False,
        type=Path,
        default=base_path / "fm-tools" / "data",
        help="Path to a checkout of the fm-tools repository",
    )
    args = parser.parse_args(argv)

    if not args.category.exists:
        raise FileNotFoundError(
            f"VerificationCategory file {args.category} does not exist"
        )
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
    logging.init(log_level, name="mkAnaScores")

    results_path = args.results_path
    categories_yml = args.category
    fm_tools_catalog = FmToolsCatalog(args.fm_tools)

    global TABLENAME, HTMLSCORES, TABSCORES, RSFSCORES, TEXRANKING, TEXRESULTS, QPLOT_PATH
    TABLENAME = "scoretable"
    # TABLENAME  = "AhT8IeQuoo"
    HTMLSCORES = results_path / Path(TABLENAME + ".html")
    TABSCORES = results_path / Path(TABLENAME + ".tsv")
    RSFSCORES = results_path / Path(TABLENAME + ".rsf")
    TEXRANKING = results_path / "scoreranking.tex"
    TEXRESULTS = results_path / "scoreresults.tex"
    QPLOT_PATH = results_path / ".." / "results-qplots"

    # rename_to_old_if_exists(RSFSCORES)
    # rename_to_old_if_exists(TABSCORES)
    # rename_to_old_if_exists(HTMLSCORES)
    # rename_to_old_if_exists(TEXRANKING)
    # rename_to_old_if_exists(TEXRESULTS)
    RSFSCORES.unlink(missing_ok=True)
    TABSCORES.unlink(missing_ok=True)
    HTMLSCORES.unlink(missing_ok=True)
    TEXRANKING.unlink(missing_ok=True)
    TEXRESULTS.unlink(missing_ok=True)

    with open(categories_yml) as inp:
        try:
            ctgry_info = yaml.load(inp, Loader=yaml.FullLoader)
        except yaml.YAMLError as e:
            print(e)
            sys.exit(1)

    meta_categories = get_categories(ctgry_info)
    categories_process_order = get_all_categories_process_order(ctgry_info)

    base_categories = [
        category
        for category in categories_process_order
        if category not in meta_categories
    ]

    meta_categories = [
        category
        for category in categories_process_order
        if category in meta_categories and not category.endswith("Overall")
    ]

    competition = competition_from_string(ctgry_info["competition"])
    track = (
        Track.Test_Generation
        if competition == Competition.TEST_COMP
        else Track.Verification
    )
    track_details = TrackDetails(competition, track, ctgry_info["year"])

    # First handle base categories (on the results of which the meta categories depend)
    processed_categories = handle_categories_parallel(
        base_categories, results_path, ctgry_info, track_details, fm_tools_catalog
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
                        track_details,
                        fm_tools_catalog,
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
                    track_details,
                    fm_tools_catalog,
                    processed_categories,
                )
            ]
        ),
    )
    msg_to_output("Overall done.")
    if competition == Competition.SV_COMP:
        processed_categories = concatenate_dict(
            processed_categories,
            dict(
                [
                    handle_category(
                        "FalsificationOverall",
                        results_path,
                        ctgry_info,
                        track_details,
                        fm_tools_catalog,
                        processed_categories,
                    )
                ]
            ),
        )
        msg_to_output("FalsifierOverall done.")
        processed_categories = concatenate_dict(
            processed_categories,
            dict(
                [
                    handle_category(
                        "JavaOverall",
                        results_path,
                        ctgry_info,
                        track_details,
                        fm_tools_catalog,
                        processed_categories,
                    )
                ]
            ),
        )
        msg_to_output("JavaOverall done.")

    msg_to_output("Dumping TSV and HTML.")
    dump_output_files(processed_categories, ctgry_info, track_details, fm_tools_catalog)
    msg_to_output("Finished.")

    """
  # Print CPU times total
  cputime_competition = 0
  for category in processed_categories.keys():
      cputime_category = 0
      for verifier in get_verifiers(category_info):
          results = processed_categories[category].results
          if verifier not in results.keys():
              continue
          cputime_category    += results[verifier].cputime.total
          print(category, verifier, round(results[verifier].cputime.total/3600))
      print(category, round(cputime_category/3600))
  """


if __name__ == "__main__":
    sys.exit(main())
