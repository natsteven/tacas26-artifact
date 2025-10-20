#!/usr/bin/env python3

import argparse
import concurrent.futures
import itertools
import math
import re
from pathlib import Path
import sys
from typing import Dict, Iterable, Optional, Sequence
import benchexec.tablegenerator as tablegenerator
import _logging as logging

from benchexec.tablegenerator import util


def is_time_column(column_name: str) -> bool:
    return re.fullmatch(r".*time", column_name) is not None


def _get_column_index(column_name: str, run_set_result) -> Optional[int]:
    """Get the index of the column with the given name in the given RunSetResult or RunResult."""
    columns = run_set_result.columns
    return next((columns.index(c) for c in columns if c.title == column_name), None)


def _get_column_values(
    column_name: str, run_set_result: tablegenerator.RunSetResult
) -> Iterable[float]:
    column_index = _get_column_index(column_name, run_set_result)
    if column_index is None:
        return list()

    return (
        util.to_decimal(r.values[column_index]) or 0 for r in run_set_result.results
    )


def _get_time_column_values(sum_values: float) -> str:
    seconds = float(sum_values)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    time_str = []

    def to_time_str(value, unit):
        time_str.append(str(math.floor(value)) + unit)

    if days > 0:
        to_time_str(days, "d")
    if hours > 0:
        to_time_str(hours, "h")
    if minutes > 0:
        to_time_str(minutes, "min")
    if seconds > 0:
        to_time_str(seconds, "s")
    return ", ".join(time_str)


def _print_values(columns_and_values: Dict[str, float]) -> None:
    for column, value in columns_and_values.items():
        if is_time_column(column):
            print_value = _get_time_column_values(value)
        else:
            print_value = str(value)
        print(column + ":", print_value)


def _snip_for_logging(lst, threshold=50):
    if len(lst) > threshold:
        half = int(threshold / 2)
        return str(lst[:half]) + "... snip ..." + str(lst[-half + 1 :])
    return str(lst)


def analyze_run_set_results(
    results_file: Path, column_names: Sequence[str]
) -> dict[str, float]:
    arg_parser = tablegenerator.create_argument_parser()
    table_generator_options = arg_parser.parse_args([])
    run_set_results = tablegenerator.load_result(
        str(results_file), table_generator_options
    )
    summary = {
        column: sum(_get_column_values(column, run_set_results))
        for column in column_names
    }
    summary["Runs"] = len(run_set_results.results)
    return summary


def main(results_dirs: Sequence[Path], column_names: Sequence[str]) -> int:
    results_files = []
    for results_dir in results_dirs:
        logging.debug("Considering directory %s", results_dir)
        dir_results_files = [
            d
            for d in results_dir.glob("*.xml*")
            if re.match(
                r".+\.results\.[a-zA-Z0-9_\-]+\.[a-zA-Z0-9_\-]+\.xml\.bz2$", d.name
            )
        ]
        logging.debug(
            "Considering the following results files (%s): %s",
            len(dir_results_files),
            _snip_for_logging(dir_results_files),
        )
        results_files += dir_results_files

    with concurrent.futures.ProcessPoolExecutor(
        max_workers=tablegenerator.get_max_worker_count(),
        mp_context=tablegenerator.get_preferred_mp_context(),
    ) as parallel:
        run_set_results = list(
            parallel.map(
                analyze_run_set_results, results_files, itertools.repeat(column_names)
            )
        )

    collected_values = {
        column: sum(r.get(column) for r in run_set_results)
        for column in (["Runs"] + column_names)
    }
    collected_values["file_count"] = len(run_set_results)

    _print_values(collected_values)
    return 0


if __name__ == "__main__":
    logging.init(logging.DEBUG, name="collect_aggregate_data")
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--column-names",
        dest="column_names",
        default="cputime,walltime,cpuenergy",
        help="Columns to collect statistics for."
        + "We can only collect statistics for columns with float- or integer values."
        + "Columns should be given as a comma-separated-list.",
    )
    parser.add_argument("results_directory", nargs="+")

    args = parser.parse_args()
    args.column_names = [name.strip() for name in args.column_names.split(",")]
    args.results_directory = [Path(d) for d in args.results_directory]

    sys.exit(main(args.results_directory, args.column_names))
