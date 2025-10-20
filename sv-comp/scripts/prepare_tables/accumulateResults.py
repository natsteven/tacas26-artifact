#!/usr/bin/env python3
from pathlib import Path

from benchexec import tablegenerator

import sys
import os
import yaml
import pandas as pd
from io import StringIO
import functools
from multiprocessing import Pool

from fm_tools.fmtoolscatalog import FmToolsCatalog
from prepare_tables.utils import (
    competition_from_string,
    find_latest_file_validator,
    validators_of_competition,
    verifiers_of_competition,
    normalize_validator_name,
)


def get_row(cat_def, tools: FmToolsCatalog, validator_category) -> str:
    validator, category = validator_category

    year_full = cat_def["year"]
    year = str(year_full)[-2:]
    competition = competition_from_string(cat_def["competition"])

    print(f"Processing validator {validator} on category {category} ...")
    total = 0
    score = 0
    correct_true = 0
    correct_false = 0
    wrong_true = 0
    wrong_false = 0
    for subcategory in cat_def["categories"][category]["categories"]:
        for verifier in verifiers_of_competition(tools, competition, year_full):
            if "C" not in tools.get(verifier).input_languages:
                continue
            fixed_file = find_latest_file_validator(
                validator, verifier, subcategory, competition, fixed=True, year=year
            )
            if not fixed_file:
                # print(
                #    "Skip",
                #    validator,
                #    verifier,
                #    subcategory,
                #    year,
                #    "since no fixed file could be found",
                # )
                continue
            run_set_result = tablegenerator.RunSetResult.create_from_xml(
                fixed_file, tablegenerator.parse_results_file(fixed_file)
            )
            run_set_result.collect_data(False)
            rows = tablegenerator.get_rows([run_set_result])
            if len(rows) == 0:
                continue
            all_column_stats = tablegenerator.compute_stats(
                rows, [run_set_result], False, False
            )
            stat = all_column_stats[0][0]
            total += stat.total.sum
            score += stat.score.sum
            correct_true += stat.correct_true.sum
            correct_false += stat.correct_false.sum
            wrong_true += stat.wrong_true.sum
            wrong_false += stat.wrong_false.sum
    return f"\n{validator}\t{category}\t{total}\t{score}\t{correct_true}\t{correct_false}\t{wrong_true}\t{wrong_false}"


def main():
    with open("benchmark-defs/category-structure.yml") as f:
        cat_def = yaml.load(f, Loader=yaml.Loader)
    table_string = "Validator\tCategory\tTasks\tScore\tCorrect true\tCorrect false\tWrong true\tWrong false"
    competition = competition_from_string(cat_def["competition"])
    year = cat_def["year"]
    tools = FmToolsCatalog(Path("fm-tools/data"))
    worklist = (
        (validator, category)
        for validator in validators_of_competition(
            tools, competition, year, include_postfix=True
        )
        if "C" in tools.get(normalize_validator_name(validator)).input_languages
        and not validator.startswith("witnesslint-validate")
        for category in cat_def["categories"]
        if "Overall" not in category
    )
    get_row_partial = functools.partial(get_row, cat_def, tools)
    with Pool(processes=os.cpu_count()) as p:
        table_string += functools.reduce(
            lambda x, y: x + y, p.map(get_row_partial, worklist), ""
        )
    html = StringIO()
    pd.read_csv(StringIO(table_string), sep="\t").to_html(buf=html, index=False)
    with open("scripts/prepare_tables/template.html", "r") as fp:
        template_text = fp.read()
    template_text = template_text.replace(
        "<!--TABLE-->",
        html.getvalue().replace(
            '<table border="1" class="dataframe">',
            '<table id="basic" class="table table-striped table-bordered" cellspacing="0" width="100%">',
        ),
    )
    with open("results-validated/validators.html", "w") as out_file:
        out_file.write(template_text)
    with open("results-validated/validators.rsf", "w") as out_file:
        out_file.write(table_string)


if __name__ == "__main__":
    sys.exit(main())
