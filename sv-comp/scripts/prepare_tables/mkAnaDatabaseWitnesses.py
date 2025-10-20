#!/usr/bin/env python3
# decimal.DefaultContext.rounding = decimal.ROUND_HALF_UP

from typing import Union, Optional
import pandas as pd
import argparse

from tqdm import tqdm
import _logging as logging

from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass

import utils
from benchexec import tablegenerator
from benchexec import result
from multiprocessing import Pool
from xml.etree.ElementTree import Element
from os import cpu_count

from prepare_tables.utils import XMLResultFileMetadata

XML_PROPERTY = "propertyFile"
XML_EXPECTED_VERDICT = "expectedVerdict"
XML_CATEGORY = "category"
XML_STATUS = "status"
XML_TASK_NAME = "name"
XML_WITNESS_TYPE = "witnesslint-witness-type"

WITNESS_VERSION_1 = "1.0"
WITNESS_VERSION_2 = "2.0"

COLUMN_CATEGORY = "category"
COLUMN_TASK = "task"
COLUMN_VERIFIER = "verifier"
COLUMN_SPECIFICATION = "specification"
COLUMN_EXPECTED = "expected"
COLUMN_WITNESS_EXPECTED = "witnessExpected"
COLUMN_WITNESS_TYPE = "witnessType"
COLUMN_WITNESS_TYPE_1 = f"{COLUMN_WITNESS_TYPE}-1.0"
COLUMN_WITNESS_TYPE_2 = f"{COLUMN_WITNESS_TYPE}-2.0"

WITNESSLINT_CORRECTNESS_TYPES = ("CORRECTNESS", "correctness_witness")
WITNESSLINT_VIOLATION_TYPES = ("VIOLATION", "violation_witness")


@dataclass
class TaskMetadata:
    task: str  # the path to the yaml file in sv-benchmarks/
    category: str  # the category of the task determined by benchexec
    status: str  # the result of the verifier
    expected: str  # expected verdict of the input program regarding specification
    specification: str  # path to property file
    file_metadata: XMLResultFileMetadata  # metadata for a result xml file
    witness_expected: Optional[str] = None  # whether the witness shall be rejected
    witness_type_v1: Optional[str] = None  # violation_witness or correctness_witness
    witness_type_v2: Optional[str] = None  # violation_witness or correctness_witness

    @staticmethod
    def _find_witness_type(file_metadata: XMLResultFileMetadata, run: Element):
        witness_type_v1 = None
        witness_type_v2 = None
        status = run.find(f"column[@title='{XML_STATUS}']").get("value")
        if file_metadata.validator == "witnesslint" and status == result.RESULT_DONE:
            witness_type = run.find(f"column[@title='{XML_WITNESS_TYPE}']").get("value")
            if file_metadata.version == WITNESS_VERSION_1:
                witness_type_v1 = witness_type
            elif file_metadata.version == WITNESS_VERSION_2:
                witness_type_v2 = witness_type
        return witness_type_v1, witness_type_v2

    @staticmethod
    def _handle_witnessmap(
        run: Element, file_metadata: XMLResultFileMetadata
    ) -> "TaskMetadata":
        category = run.find(f"column[@title='{XML_CATEGORY}']").get("value")
        status = run.find(f"column[@title='{XML_STATUS}']").get("value")

        # task definitions of witness benchmarks contain additional information
        run_name = run.get(XML_TASK_NAME)
        task_path = file_metadata.path.parent / run_name
        task_definition = utils.parse_yaml(task_path)

        xml_spec = run.get(XML_PROPERTY)
        xml_spec_path = file_metadata.path.parent / xml_spec

        if "additional_information" not in task_definition:
            logging.error(
                f"Field 'additional_information' not in task '{task_path}' from results in '{file_metadata.path}'."
            )

        # sanity checks for the task definition
        assert (
            task_definition["additional_information"]["task_type"] == "validation"
        ), "Task type is not validation."
        assert (
            "verification" in task_definition["additional_information"]
        ), "Verification information missing."

        # find the expected verdict for the current property file
        for prop in task_definition["additional_information"]["verification"]:
            task_def_spec_path = task_path.parent / prop["property_file"]
            if xml_spec_path.resolve() == task_def_spec_path.resolve():
                expected = prop["expected_verdict"]
                break
        else:
            # entered if list is empty or no matching property file was found
            raise AssertionError(
                f"Property file {xml_spec} not found in task definition."
            )

        witness_type_v1, witness_type_v2 = TaskMetadata._find_witness_type(
            file_metadata, run
        )

        return TaskMetadata(
            task=run_name,
            category=category,
            status=status,
            expected=expected,
            specification=xml_spec,
            file_metadata=file_metadata,
            witness_expected=run.get(XML_EXPECTED_VERDICT),
            witness_type_v1=witness_type_v1,
            witness_type_v2=witness_type_v2,
        )

    @staticmethod
    def _run_to_task_metadata(
        run: Element, file_metadata: XMLResultFileMetadata
    ) -> "TaskMetadata":
        if file_metadata.verifier == "witnessmap":
            return TaskMetadata._handle_witnessmap(run, file_metadata)
        witness_type_v1, witness_type_v2 = TaskMetadata._find_witness_type(
            file_metadata, run
        )
        return TaskMetadata(
            task=run.get(XML_TASK_NAME),
            category=run.find(f"column[@title='{XML_CATEGORY}']").get("value"),
            status=run.find(f"column[@title='{XML_STATUS}']").get("value"),
            expected=run.get(XML_EXPECTED_VERDICT),
            specification=run.get(XML_PROPERTY),
            file_metadata=file_metadata,
            witness_type_v1=witness_type_v1,
            witness_type_v2=witness_type_v2,
        )

    @staticmethod
    def from_xml_result_file_metadata(
        file_metadata: XMLResultFileMetadata,
    ) -> list["TaskMetadata"]:
        """Expand a file metadata into a list of task metadata."""
        path = file_metadata.path
        run_set = tablegenerator.parse_results_file(str(path))
        tasks = []
        for run in run_set.findall("run"):
            tasks.append(TaskMetadata._run_to_task_metadata(run, file_metadata))
        return tasks


def prepare_database(tasks: list[TaskMetadata]) -> pd.DataFrame:
    """Prepare the database from a list of task metadata."""
    result = defaultdict(lambda: {})
    witness_kind_v1 = dict()
    witness_kind_v2 = dict()
    for task in tasks:
        unique_task = (
            task.file_metadata.category,
            task.task,
            task.file_metadata.verifier,
            task.specification,
            task.expected,
            task.witness_expected,
        )
        validator = (
            task.file_metadata.validator,
            task.file_metadata.witness,
            task.file_metadata.version,
        )
        result[unique_task][validator] = task.status
        if task.witness_type_v1 is not None:
            witness_kind_v1[unique_task] = task.witness_type_v1
        if task.witness_type_v2 is not None:
            witness_kind_v2[unique_task] = task.witness_type_v2
    plain_dicts = []
    for r in result:
        reduced_to_plain_dict = {
            COLUMN_CATEGORY: r[0],
            COLUMN_TASK: r[1],
            COLUMN_VERIFIER: r[2],
            COLUMN_SPECIFICATION: r[3],
            COLUMN_EXPECTED: r[4],
            COLUMN_WITNESS_TYPE_1: witness_kind_v1.get(r, ""),
            COLUMN_WITNESS_TYPE_2: witness_kind_v2.get(r, ""),
            COLUMN_WITNESS_EXPECTED: r[5] if r[5] is not None else "",
        }
        for validator in result[r]:
            reduced_to_plain_dict |= {
                f"{validator[0]}-{validator[1]}-{validator[2]}": result[r][validator]
            }
        plain_dicts.append(reduced_to_plain_dict)
    return pd.DataFrame(plain_dicts)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "results_validated", type=Path, default=Path("../../results_validated/")
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging.")
    parser.add_argument("--database", type=Path, help="Path to the database.")
    parser.add_argument(
        "--output",
        type=Path,
        help="Path to the output CSV files.",
        default=Path("results-validated"),
    )
    return parser.parse_args()


def _classify_task(row, columns: list[str], witness_kind: str) -> dict[str, str]:
    kinds = ("correctness-1.0", "correctness-2.0", "violation-1.0", "violation-2.0")
    assert (
        witness_kind in kinds
    ), f"Invalid witness kind {witness_kind} (must be one of {kinds})."
    validator_expected_witness, version = witness_kind.split("-")

    expected_verdict = str(row[COLUMN_EXPECTED]).lower()

    # handle witnessmap
    if row["verifier"] == "witnessmap":
        if row[COLUMN_WITNESS_EXPECTED] in ("", "-"):
            logging.warning(
                "Found witnessmap task (%s) without expected verdict.", row[COLUMN_TASK]
            )
            return {
                witness_kind: result.WITNESS_CATEGORY_UNKNOWN,
                f"voting-{witness_kind}": "-:-",
            }
        if str(row[COLUMN_WITNESS_EXPECTED]).lower() != str(expected_verdict).lower():
            # if the witness verdict does not match the expected verdict, the task is invalid
            return {
                witness_kind: result.WITNESS_CATEGORY_WRONG,
                f"voting-{witness_kind}": "-:-",
            }
        return {
            witness_kind: result.WITNESS_CATEGORY_CORRECT,
            f"voting-{witness_kind}": "-:-",
        }
    else:
        if row[COLUMN_WITNESS_EXPECTED] not in (
            "",
            "-",
        ):  # pandas reads empty cells as "-"
            raise ValueError(
                f"Unexpected witness verdict ({row[COLUMN_WITNESS_EXPECTED]}) for non-witnessmap task ({row[COLUMN_VERIFIER]})."
            )

    if row[f"{COLUMN_WITNESS_TYPE}-{version}"] in WITNESSLINT_CORRECTNESS_TYPES:
        if validator_expected_witness == "violation":
            return {
                witness_kind: result.WITNESS_CATEGORY_UNKNOWN,
                f"voting-{witness_kind}": "-:-",
            }
        if expected_verdict.startswith(result.RESULT_FALSE_PROP):
            return {
                witness_kind: result.WITNESS_CATEGORY_WRONG,
                f"voting-{witness_kind}": "-:-",
            }
    elif row[f"{COLUMN_WITNESS_TYPE}-{version}"] in WITNESSLINT_VIOLATION_TYPES:
        if validator_expected_witness == "correctness":
            return {
                witness_kind: result.WITNESS_CATEGORY_UNKNOWN,
                f"voting-{witness_kind}": "-:-",
            }
        if expected_verdict.startswith(result.RESULT_TRUE_PROP):
            return {
                witness_kind: result.WITNESS_CATEGORY_WRONG,
                f"voting-{witness_kind}": "-:-",
            }
    else:
        return {
            witness_kind: result.WITNESS_CATEGORY_UNKNOWN,
            f"voting-{witness_kind}": "-:-",
        }
    # the witness matches the expected verdict (valid*)
    opposite_verdict = (
        result.RESULT_FALSE_PROP
        if expected_verdict == result.RESULT_TRUE_PROP
        else result.RESULT_TRUE_PROP
    )
    for c in columns:
        if not isinstance(row[c], str):
            logging.error(f"Expected string, got {type(row[c])} for {c} in {row[c]}")
            raise AssertionError("Expected string.")
    confirmed = len([1 for c in columns if row[c].startswith(expected_verdict)])
    rejected = len([1 for c in columns if row[c].startswith(opposite_verdict)])
    if confirmed + rejected >= 2:
        if confirmed >= 3 * rejected:
            # 75% of the validators agree on the expected verdict, so we classify the task as valid
            return {
                witness_kind: result.WITNESS_CATEGORY_CORRECT,
                f"voting-{witness_kind}": f"{confirmed}:{rejected}",
            }
        if rejected >= 3 * confirmed:
            # 75% of the validators agree on the opposite verdict, so we classify the task as invalid
            return {
                witness_kind: result.WITNESS_CATEGORY_WRONG,
                f"voting-{witness_kind}": f"{confirmed}:{rejected}",
            }
    # if we have less than 2 validators or no majority
    # producing a valid validation verdict, we cannot make a decision
    return {
        witness_kind: result.WITNESS_CATEGORY_UNKNOWN,
        f"voting-{witness_kind}": f"{confirmed}:{rejected}",
    }


def valid_tasks(dataframe_or_database: Union[pd.DataFrame, Path]):
    assert len(WITNESS_VERSION_1) == len(
        WITNESS_VERSION_2
    ), "Versions must have same length."
    df = dataframe_or_database
    if isinstance(df, Path):
        df = pd.read_csv(df)
    columns = df.columns
    witnesses = defaultdict(lambda: [])
    for c in columns:
        if "correctness" in c:
            if WITNESS_VERSION_1 in c:
                kind = "correctness-1.0"
            else:
                kind = "correctness-2.0"
            witnesses[kind].append(c)
        if "violation" in c:
            if WITNESS_VERSION_1 in c:
                kind = "violation-1.0"
            else:
                kind = "violation-2.0"
            witnesses[kind].append(c)
    for k in witnesses:
        df[k] = df.apply(lambda row: _classify_task(row, witnesses[k], k)[k], axis=1)
        df[f"voting-{k}"] = df.apply(
            lambda row: _classify_task(row, witnesses[k], k)[f"voting-{k}"], axis=1
        )
    return df


def main():
    args = parse_args()
    debug = bool(args.debug)
    log_level = logging.DEBUG if debug else logging.INFO
    logging.init(log_level, "check-witness-validity")
    results_validated = args.results_validated
    logging.info(f"Reading results from {results_validated}")
    xml_files = list(XMLResultFileMetadata.from_results_validated(results_validated))
    if len(xml_files) == 0:
        logging.error(f"No files found in {results_validated}. Exiting.")
        return
    logging.info(f"Found {len(xml_files)} files. Creating tasks...")
    tasks = []
    if args.database is None:
        if debug:
            logging.info("Running in debug mode. Expanding tasks sequentially.")
            for fm in tqdm(xml_files):
                tasks.extend(TaskMetadata.from_xml_result_file_metadata(fm))
        else:
            logging.info("Running in production mode. Expanding tasks in parallel.")
            with Pool(max(1, cpu_count() - 2)) as p:
                tasks = list(
                    tqdm(
                        p.imap(TaskMetadata.from_xml_result_file_metadata, xml_files),
                        total=len(xml_files),
                    )
                )
            tasks = [t for sublist in tasks for t in sublist]
        df = prepare_database(tasks)
        logging.info(f"Found {len(tasks)} tasks. Creating CSV...")
        database_path = args.output / "witness-database.csv"
        df.to_csv(database_path, index=False, sep="\t")
        logging.info("Database written to %s", database_path)
        logging.info("Done creating database.")
    else:
        logging.info(f"Reading database from {args.database}")
        df = pd.read_csv(args.database, sep="\t")
    df = df.fillna("-")
    logging.info("Classify tasks...")
    valid = valid_tasks(df)
    classification_path = args.output / "witness-classification.csv"
    valid.to_csv(classification_path, index=False, sep="\t")
    logging.info("Classification written to %s", classification_path)
    logging.info("Done creating witness classification.")


if __name__ == "__main__":
    main()
