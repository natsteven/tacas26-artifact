# This file is part of BenchExec, a framework for reliable benchmarking:
# https://github.com/sosy-lab/benchexec
#
# SPDX-FileCopyrightText: 2007-2020 Dirk Beyer <https://www.sosy-lab.org>
#
# SPDX-License-Identifier: Apache-2.0

import copy
import os.path
import pathlib
import sys
import unittest
import xml.etree.ElementTree as ET  # noqa: What's wrong with ET?
from functools import cached_property
from xml.etree.ElementTree import Element

from prepare_tables import adjust_results_verifiers
from benchexec import result
from benchexec import tablegenerator

from prepare_tables.adjust_results_verifiers import BenchmarkRuns, BenchmarkRun

sys.dont_write_bytecode = True  # prevent creation of .pyc files

test_data = {
    "verifier_correct": os.path.join(
        os.path.dirname(__file__),
        "test_adjust_results_verifiers/test_data",
        "verifier_correct.xml",
    ),
    "verifier_wrong": os.path.join(
        os.path.dirname(__file__),
        "test_adjust_results_verifiers/test_data",
        "verifier_wrong.xml",
    ),
    "verifier_correct_overflow_mismatching_property": os.path.join(
        os.path.dirname(__file__),
        "test_adjust_results_verifiers/test_data",
        "verifier_correct_overflow_mismatching_property.xml",
    ),
    "verifier_correct_deref": os.path.join(
        os.path.dirname(__file__),
        "test_adjust_results_verifiers/test_data",
        "verifier_correct_deref.xml",
    ),
    "verifier_correct_deref_mismatching_property": os.path.join(
        os.path.dirname(__file__),
        "test_adjust_results_verifiers/test_data",
        "verifier_correct_deref_mismatching_property.xml",
    ),
    "verifier_no_data": os.path.join(
        os.path.dirname(__file__),
        "test_adjust_results_verifiers/test_data",
        "verifier_no_data.xml",
    ),
    "verifier_error": os.path.join(
        os.path.dirname(__file__),
        "test_adjust_results_verifiers/test_data",
        "verifier_error.xml",
    ),
    "validator_confirm": os.path.join(
        os.path.dirname(__file__),
        "test_adjust_results_verifiers/test_data",
        "validator_confirm.xml",
    ),
    "validator_deref_false": os.path.join(
        os.path.dirname(__file__),
        "test_adjust_results_verifiers/test_data",
        "validator_deref_false.xml",
    ),
    "validator_overflow_false": os.path.join(
        os.path.dirname(__file__),
        "test_adjust_results_verifiers/test_data",
        "validator_overflow_false.xml",
    ),
    "validator_reject": os.path.join(
        os.path.dirname(__file__),
        "test_adjust_results_verifiers/test_data",
        "validator_reject.xml",
    ),
    "validator_timeout": os.path.join(
        os.path.dirname(__file__),
        "test_adjust_results_verifiers/test_data",
        "validator_timeout.xml",
    ),
    "validator_out_of_memory": os.path.join(
        os.path.dirname(__file__),
        "test_adjust_results_verifiers/test_data",
        "validator_out_of_memory.xml",
    ),
    "validator_no_data": os.path.join(
        os.path.dirname(__file__),
        "test_adjust_results_verifiers/test_data",
        "validator_no_data.xml",
    ),
    "linter_done": os.path.join(
        os.path.dirname(__file__),
        "test_adjust_results_verifiers/test_data",
        "linter_done.xml",
    ),
    "linter_error": os.path.join(
        os.path.dirname(__file__),
        "test_adjust_results_verifiers/test_data",
        "linter_error.xml",
    ),
    "linter_no_data": os.path.join(
        os.path.dirname(__file__),
        "test_adjust_results_verifiers/test_data",
        "linter_no_data.xml",
    ),
}

verifier_xml = os.path.join(
    os.path.dirname(__file__), "test_adjust_results_verifiers/mock_results.xml"
)
verifier_xml_parsed = ET.parse(verifier_xml).getroot()  # noqa S314, the XML is trusted
verifier_benchmark_runs = BenchmarkRuns(verifier_xml, verifier_xml_parsed)

validator_xml_1 = os.path.join(
    os.path.dirname(__file__), "test_adjust_results_verifiers/mock_witness_1.xml"
)
validator_xml_parsed_1 = ET.parse(  # noqa S314, the XML is trusted
    validator_xml_1
).getroot()
validator_benchmark_runs_1 = BenchmarkRuns(validator_xml_1, validator_xml_parsed_1)

validator_xml_2 = os.path.join(
    os.path.dirname(__file__), "test_adjust_results_verifiers/mock_witness_2.xml"
)
validator_xml_parsed_2 = ET.parse(  # noqa S314, the XML is trusted
    validator_xml_2
).getroot()
validator_benchmark_runs_2 = BenchmarkRuns(validator_xml_2, validator_xml_parsed_2)

empty_benchmark_run = BenchmarkRun("", "", None)

tasks = [
    "../sv-benchmarks/c/array-examples/sanfoundry_24-1.yml",
    "../sv-benchmarks/c/array-examples/data_structures_set_multi_proc_trivial_ground.yml",
    "../sv-benchmarks/c/array-patterns/array28_pattern.yml",
    "../sv-benchmarks/c/reducercommutativity/rangesum05.yml",
    "../sv-benchmarks/c/array-fpi/indp4f.yml",
]


class MockedBenchmarkRuns(BenchmarkRuns):
    def __init__(self, mock: dict[str, Element]):
        super().__init__(validator_xml_1)
        self._mock = mock

    @cached_property
    def as_dictionary(self) -> dict[str, Element]:
        return self._mock


def mock_validator() -> BenchmarkRuns:
    # never insert the already parsed xml here as it will be modified by subsequent calls.
    # this method needs to generate a new copy of the xml every time it is called.
    return MockedBenchmarkRuns(
        copy.deepcopy(
            validator_benchmark_runs_1.as_dictionary
            | validator_benchmark_runs_2.as_dictionary
        )
    )


def mock_get_verification_result(name) -> BenchmarkRun:
    return BenchmarkRun(
        verifier_xml, "test", verifier_xml_parsed.find(f"run[@name='{name}']")
    )


def mock_validator_run(name) -> BenchmarkRun:
    validator = mock_validator().as_dictionary.get(name)
    # assert validator is not None, "Validator run must exist"
    return BenchmarkRun(validator_xml_1, "test", validator)


def element_trees_equal(et1, et2):
    if len(et1) != len(et2) or et1.tag != et2.tag or et1.attrib != et2.attrib:
        return False
    return all(element_trees_equal(child1, child2) for child1, child2 in zip(et1, et2))


def prepare_files(test_case):
    validator_files = list(
        map(
            lambda prepend: os.path.join("test_adjust_results_verifiers", prepend),
            test_case["validators"],
        )
    )
    validators = []
    for validator_file in validator_files:
        if not os.path.exists(validator_file) or not os.path.isfile(validator_file):
            sys.exit(f"File {validator_file!r} does not exist.")
        validators.append(BenchmarkRuns(validator_file))

    linter_files = list(
        map(
            lambda prepend: os.path.join("test_adjust_results_verifiers", prepend),
            [test_case["linter"]],
        )
    )
    linters = []
    for linter_file in linter_files:
        if not os.path.exists(linter_file) or not os.path.isfile(linter_file):
            sys.exit(f"File {linter_file!r} does not exist.")
        linters.append(BenchmarkRuns(linter_file))

    # parse result files
    verifier_file = os.path.join("test_adjust_results_verifiers", test_case["verifier"])
    result_xml = tablegenerator.parse_results_file(verifier_file)
    adjust_results_verifiers.adjust_status_category(
        BenchmarkRuns(verifier_file, result_xml), validators, linters
    )
    return result_xml


class TestMergeBenchmarkSets(unittest.TestCase):
    def test_only_elem(self):
        new_results = adjust_results_verifiers.xml_to_string(verifier_xml_parsed)
        new_witness_1 = adjust_results_verifiers.xml_to_string(validator_xml_parsed_1)
        new_witness_2 = adjust_results_verifiers.xml_to_string(validator_xml_parsed_2)
        self.assertTrue(
            element_trees_equal(
                ET.fromstring(new_results),
                verifier_xml_parsed,  # noqa S314, the XML is trusted
            )
        )
        self.assertTrue(
            element_trees_equal(
                ET.fromstring(new_witness_1),  # noqa S314, the XML is trusted
                validator_xml_parsed_1,
            )
        )
        self.assertTrue(
            element_trees_equal(
                ET.fromstring(new_witness_2),  # noqa S314, the XML is trusted
                validator_xml_parsed_2,
            )
        )

    def test_set_doctype(self):
        qualified_name = "result"
        public_id = "+//IDN sosy-lab.org//DTD BenchExec result 1.18//EN"
        system_id = "https://www.sosy-lab.org/benchexec/result-1.18.dtd"
        new_results = adjust_results_verifiers.xml_to_string(
            verifier_xml_parsed, qualified_name, public_id, system_id
        )
        new_witness_1 = adjust_results_verifiers.xml_to_string(
            validator_xml_parsed_1, qualified_name, public_id, system_id
        )
        new_witness_2 = adjust_results_verifiers.xml_to_string(
            validator_xml_parsed_2, qualified_name, public_id, system_id
        )
        self.assertTrue(
            element_trees_equal(
                verifier_xml_parsed,
                ET.fromstring(new_results),  # noqa S314, the XML is trusted
            )
        )
        self.assertTrue(
            element_trees_equal(
                validator_xml_parsed_1,
                ET.fromstring(new_witness_1),  # noqa S314, the XML is trusted
            )
        )
        self.assertTrue(
            element_trees_equal(
                validator_xml_parsed_2,
                ET.fromstring(new_witness_2),  # noqa S314, the XML is trusted
            )
        )
        for xml in [new_results, new_witness_1, new_witness_2]:
            self.assertListEqual(
                [line.strip() for line in xml.splitlines()[1:4]],
                [
                    f"<!DOCTYPE {qualified_name}",
                    f"PUBLIC '{public_id}'",
                    f"'{system_id}'>",
                ],
            )

    def test_getWitnesses(self):
        validator_1 = BenchmarkRuns(validator_xml_1).as_dictionary
        validator_2 = BenchmarkRuns(validator_xml_2).as_dictionary
        self.assertEqual(3, len(validator_1))
        self.assertEqual(2, len(validator_2))
        self.assertSetEqual(
            {
                "../sv-benchmarks/c/array-examples/sanfoundry_24-1.yml",
                "../sv-benchmarks/c/array-examples/data_structures_set_multi_proc_trivial_ground.yml",
                "../sv-benchmarks/c/array-patterns/array28_pattern.yml",
            },
            set(validator_1.keys()),
        )
        self.assertSetEqual(
            {
                "../sv-benchmarks/c/reducercommutativity/rangesum05.yml",
                "../sv-benchmarks/c/array-fpi/indp4f.yml",
            },
            set(validator_2.keys()),
        )

    def test_getWitnessResult_no_witness(self):
        self.assertEqual(
            ("validation run missing", result.CATEGORY_ERROR),
            adjust_results_verifiers.get_validator_linter_result(
                empty_benchmark_run, empty_benchmark_run
            ),
        )
        self.assertEqual(
            ("validation run missing", result.CATEGORY_ERROR),
            adjust_results_verifiers.get_validator_linter_result(
                empty_benchmark_run,
                BenchmarkRun("", "", verifier_xml_parsed.find("run")),
            ),
        )

    def test_getWitnessResult_no_verification_result(self):
        for file in tasks[:-1]:
            tuple_result = adjust_results_verifiers.get_validator_linter_result(
                mock_validator_run(file), empty_benchmark_run
            )
            self.assertTrue(
                ("result invalid (not found)", result.CATEGORY_ERROR) == tuple_result
                or ("witness invalid (not found)", result.CATEGORY_ERROR)
                == tuple_result
            )
        self.assertEqual(
            ("witness invalid (not found)", result.CATEGORY_ERROR),
            adjust_results_verifiers.get_validator_linter_result(
                mock_validator_run(tasks[-1]), empty_benchmark_run
            ),
        )

    def test_getWitnessResult(self):
        expected_results = [
            ("true", result.CATEGORY_CORRECT_UNCONFIRMED),
            ("result invalid (TIMEOUT)", result.CATEGORY_ERROR),
            ("result invalid (false(unreach-call))", result.CATEGORY_ERROR),
            ("false(unreach-call)", result.CATEGORY_CORRECT),
            ("witness invalid (false(unreach-call))", result.CATEGORY_ERROR),
        ]
        for expected, file in zip(expected_results, tasks):
            self.assertEqual(
                expected,
                adjust_results_verifiers.get_validator_linter_result(
                    mock_validator_run(file), mock_get_verification_result(file)
                ),
            )

    def test_getValidationResult_single_witness(self):
        expected_results = [
            ("true", result.CATEGORY_CORRECT_UNCONFIRMED),
            ("result invalid (TIMEOUT)", result.CATEGORY_ERROR),
            ("result invalid (false(unreach-call))", result.CATEGORY_ERROR),
            ("false(unreach-call)", result.CATEGORY_CORRECT),
            ("witness invalid (false(unreach-call))", result.CATEGORY_ERROR),
        ]
        for expected, file in zip(expected_results, tasks):
            benchmark_run = mock_get_verification_result(file)
            run = benchmark_run.run
            status_from_verification = run.find('column[@title="status"]').get("value")
            category_from_verification = run.find('column[@title="category"]').get(
                "value"
            )
            actual = adjust_results_verifiers.get_validation_result(
                benchmark_run,
                [mock_validator()],
                [mock_validator()],
                status_from_verification,
                category_from_verification,
            )
            self.assertEqual(expected, actual[:2])
            self.assertEqual(
                (status_from_verification, category_from_verification), actual[2:]
            )

    def test_getValidationResult_multiple_witnesses(self):
        # we modify an arbitrary witness xml to contain these verdicts
        fake_linter_verdicts = [
            ("ERROR (invalid witness syntax)", result.CATEGORY_ERROR),
            ("ERROR (anything else)", result.CATEGORY_ERROR),
            ("done", result.RESULT_DONE),
            ("done", result.RESULT_DONE),
            ("ERROR (unexpected witness type)", result.CATEGORY_ERROR),
        ]
        fake_validator_verdicts = [
            ("ERROR (invalid witness syntax)", result.CATEGORY_ERROR),
            ("ERROR (invalid witness file)", result.CATEGORY_ERROR),
            ("false (unreach-call)", result.CATEGORY_WRONG),
            ("true", result.CATEGORY_WRONG),
            ("false (unreach-call)", result.CATEGORY_CORRECT),
        ]
        expected_verdicts = [
            ("witness invalid (true)", result.CATEGORY_ERROR),
            ("result invalid (TIMEOUT)", result.CATEGORY_ERROR),
            ("result invalid (false(unreach-call))", result.CATEGORY_ERROR),
            ("false(unreach-call)", result.CATEGORY_CORRECT_UNCONFIRMED),
            ("witness-type mismatch (false(unreach-call))", result.CATEGORY_ERROR),
        ]
        for expected, task, fake_witness_results, fake_linter_results in zip(
            expected_verdicts, tasks, fake_validator_verdicts, fake_linter_verdicts
        ):
            linter_benchmark_runs = mock_validator()
            linter_run = linter_benchmark_runs.as_dictionary.get(task)
            linter_run.find('column[@title="status"]').set(
                "value", fake_linter_results[0]
            )
            linter_run.find('column[@title="category"]').set(
                "value", fake_linter_results[1]
            )
            verification_run = mock_get_verification_result(task).run
            status_from_verification = verification_run.find(
                'column[@title="status"]'
            ).get("value")
            category_from_verification = verification_run.find(
                'column[@title="category"]'
            ).get("value")
            fake_runs = mock_validator()
            validator_run = fake_runs.as_dictionary.get(task)
            validator_run.find('column[@title="status"]').set(
                "value", fake_witness_results[0]
            )
            validator_run.find('column[@title="category"]').set(
                "value", fake_witness_results[1]
            )
            actual = adjust_results_verifiers.get_validation_result(
                BenchmarkRun(task, "test", verification_run),
                [MockedBenchmarkRuns({task: validator_run})],
                [MockedBenchmarkRuns({task: linter_run})],
                status_from_verification,
                category_from_verification,
            )
            debug_dict = {
                "expected": expected,
                "task": task,
                "fake_witness_results": fake_witness_results,
                "fake_linter_results": fake_linter_results,
                "status_from_verification": status_from_verification,
                "category_from_verification": category_from_verification,
                "actual": actual,
            }
            self.assertEqual(expected, actual[:2], debug_dict)
            self.assertEqual(
                (status_from_verification, category_from_verification),
                actual[2:],
                debug_dict,
            )

    def test_getValidationResult_coverage_error_call(self):
        expected_results = [
            (None, None),
            (None, None),
            ("false(unreach-call)", result.CATEGORY_CORRECT),
            (None, None),
            (None, None),
        ]
        for expected, file in zip(expected_results, tasks):
            run = copy.deepcopy(mock_get_verification_result(file)).run
            run.set("properties", "coverage-error-call")
            status_from_verification = run.find('column[@title="status"]').get("value")
            category_from_verification = run.find('column[@title="category"]').get(
                "value"
            )
            actual = adjust_results_verifiers.get_validation_result(
                BenchmarkRun(file, "test", run),
                [mock_validator()],
                [],
                status_from_verification,
                category_from_verification,
            )
            self.assertEqual(expected, actual[:2])
            self.assertEqual(status_from_verification, actual[2])
            if file == "../sv-benchmarks/c/array-patterns/array28_pattern.yml":
                self.assertEqual(result.CATEGORY_CORRECT, actual[3])
                self.assertNotEqual(None, run.find('column[@title="score"]'))
            else:
                self.assertEqual(category_from_verification, actual[3])

    def test_getValidationResult_coverage_branches(self):
        for task in tasks:
            run = copy.deepcopy(mock_get_verification_result(task)).run
            run.set("properties", "coverage-branches")
            status_from_verification = run.find('column[@title="status"]').get("value")
            category_from_verification = run.find('column[@title="category"]').get(
                "value"
            )
            actual = adjust_results_verifiers.get_validation_result(
                BenchmarkRun(task, "test", run),
                [mock_validator()],
                [],
                status_from_verification,
                category_from_verification,
            )
            self.assertTupleEqual(
                (
                    status_from_verification,
                    result.CATEGORY_CORRECT,
                    status_from_verification,
                    result.CATEGORY_CORRECT,
                ),
                actual,
            )
            self.assertNotEqual(None, run.find('column[@title="score"]'))

    def test_getValidationResult_malformed_coverage(self):
        modified_verification_run = copy.deepcopy(
            verifier_xml_parsed.find(
                'run[@name="../sv-benchmarks/c/array-examples/sanfoundry_24-1.yml"]'
            )
        )
        modified_verification_run.set("properties", "coverage-branches")
        modified_validator_run = copy.deepcopy(
            validator_xml_parsed_1.find(
                'run[@name="../sv-benchmarks/c/array-examples/sanfoundry_24-1.yml"]'
            )
        )
        coverage_column = ET.Element(
            "column",
            title="branches_covered",
            value="fifty percent",  # this cannot be parsed into a number
        )
        modified_validator_run.append(coverage_column)
        modified_validator_parsed = copy.deepcopy(validator_xml_parsed_1)
        modified_validator_parsed.remove(
            modified_validator_parsed.find(
                'run[@name="../sv-benchmarks/c/array-examples/sanfoundry_24-1.yml"]'
            )
        )
        modified_validator_parsed.append(modified_validator_run)
        actual = adjust_results_verifiers.get_validation_result(
            BenchmarkRun(verifier_xml, "test", modified_verification_run),
            [BenchmarkRuns(validator_xml_1, modified_validator_parsed)],
            [],
            result.RESULT_TRUE_PROP,
            result.CATEGORY_CORRECT,
        )
        # we should still be able to assign the correct results:
        self.assertTupleEqual(
            (
                result.RESULT_TRUE_PROP,
                result.CATEGORY_CORRECT,
                result.RESULT_TRUE_PROP,
                result.CATEGORY_CORRECT,
            ),
            actual,
        )
        # score should be None since we were not able to parse "fifty percent" above:
        self.assertTrue(modified_validator_run.find('column[@title="score"]') is None)

    def test_merge_no_witness(self):
        results_xml_cp1 = copy.deepcopy(verifier_xml_parsed)
        for run in results_xml_cp1.findall("run"):
            category = run.find('column[@title="category"]').get("value")
            if category == result.CATEGORY_CORRECT:
                run.find('column[@title="category"]').set(
                    "value", result.CATEGORY_CORRECT_UNCONFIRMED
                )
        runs = BenchmarkRuns(verifier_xml, copy.deepcopy(verifier_xml_parsed))
        adjust_results_verifiers.adjust_status_category(runs, [], [])
        self.assertEqual(ET.tostring(results_xml_cp1), ET.tostring(runs.runs))

    def test_merge_no_witness_no_overwrite(self):
        results_xml_cp1 = copy.deepcopy(verifier_xml_parsed)
        results_xml_cp1.set("name", "SV-COMP.-NoDataRace-")
        for run in results_xml_cp1.findall("run"):
            category = run.find('column[@title="category"]').get("value")
            status = run.find('column[@title="status"]').get("value")
            if (
                category == result.CATEGORY_CORRECT
                and result.RESULT_CLASS_FALSE
                == result.get_result_classification(status)
            ):
                run.find('column[@title="category"]').set(
                    "value", result.CATEGORY_CORRECT_UNCONFIRMED
                )
        runs = BenchmarkRuns(verifier_xml, copy.deepcopy(verifier_xml_parsed))
        runs.runs.set("name", "SV-COMP.-NoDataRace-")
        adjust_results_verifiers.adjust_status_category(runs, [], [])
        self.assertEqual(ET.tostring(results_xml_cp1), ET.tostring(runs.runs))

    def test_merge(self):
        expected_results = [
            ("true", result.CATEGORY_CORRECT_UNCONFIRMED),
            ("false(unreach-call)", result.CATEGORY_CORRECT),
            ("TIMEOUT", result.CATEGORY_ERROR),
            ("witness invalid (false(unreach-call))", result.CATEGORY_ERROR),
            ("false(unreach-call)", result.CATEGORY_WRONG),
        ]
        verifier_runs = BenchmarkRuns(verifier_xml)
        adjust_results_verifiers.adjust_status_category(
            verifier_runs, [mock_validator()], [mock_validator()]
        )
        for expected, run in zip(
            expected_results, verifier_runs.as_dictionary.values()
        ):
            status = run.find('column[@title="status"]').get("value")
            category = run.find('column[@title="category"]').get("value")
            self.assertTupleEqual(expected, (status, category))

    def test_merge_no_overwrite(self):
        expected_results = [
            ("true", result.CATEGORY_CORRECT),
            ("false(unreach-call)", result.CATEGORY_CORRECT),
            ("TIMEOUT", result.CATEGORY_ERROR),
            ("witness invalid (false(unreach-call))", result.CATEGORY_ERROR),
            ("false(unreach-call)", result.CATEGORY_WRONG),
        ]
        verifier_runs = BenchmarkRuns(verifier_xml)
        # NoDataRace does not have correctness witnesses
        verifier_runs.runs.set("name", "SV-COMP.-NoDataRace-")
        adjust_results_verifiers.adjust_status_category(
            verifier_runs, [mock_validator()], [mock_validator()]
        )
        for expected, run in zip(
            expected_results, verifier_runs.as_dictionary.values()
        ):
            status = run.find('column[@title="status"]').get("value")
            category = run.find('column[@title="category"]').get("value")
            self.assertTupleEqual(expected, (status, category))

    def test_merge_no_status_no_category(self):
        expected_results = [("not found", result.CATEGORY_CORRECT)] * 5
        verifier_runs = BenchmarkRuns(verifier_xml)
        for run in verifier_runs.as_dictionary.values():
            status_column = run.find('column[@title="status"]')
            category_column = run.find('column[@title="category"]')
            run.remove(status_column)
            run.remove(category_column)
            run.set("properties", "coverage-branches")
        adjust_results_verifiers.adjust_status_category(
            verifier_runs, [mock_validator()], []
        )
        for expected, run in zip(
            expected_results, verifier_runs.as_dictionary.values()
        ):
            status = run.find('column[@title="status"]').get("value")
            category = run.find('column[@title="category"]').get("value")
            self.assertTupleEqual(expected, (status, category))

    def test_merge_verifier_correct_linter_done_validator_timeout_memory_none(self):
        test_input = {
            "validators": [
                test_data["validator_timeout"],
                test_data["validator_no_data"],
                test_data["validator_out_of_memory"],
            ],
            "verifier": test_data["verifier_correct"],
            "linter": test_data["linter_done"],
        }
        for elem in prepare_files(test_input).findall("run"):
            self.assertNotEqual(
                result.CATEGORY_CORRECT,
                elem.find('column[@title="category"]').get("value"),
            )
            self.assertNotEqual(
                result.CATEGORY_WRONG,
                elem.find('column[@title="category"]').get("value"),
            )

    def test_merge_verifier_correct_linter_done_validator_timeout_reject_none(self):
        # if no validator confirms a linter-approved "correct" witness, the category changes to "error/unknown"
        test_input = {
            "validators": [
                test_data["validator_timeout"],
                test_data["validator_reject"],
                test_data["validator_no_data"],
            ],
            "verifier": test_data["verifier_correct"],
            "linter": test_data["linter_done"],
        }
        for elem in prepare_files(test_input).findall("run"):
            self.assertNotEqual(
                result.CATEGORY_CORRECT,
                elem.find('column[@title="category"]').get("value"),
            )
            self.assertNotEqual(
                result.CATEGORY_WRONG,
                elem.find('column[@title="category"]').get("value"),
            )

    def test_merge_verifier_correct_linter_done_validator_timeout_confirm_no_data(self):
        # if at least one validator confirms a linter-approved witness, the category stays correct
        test_input = {
            "validators": [
                test_data["validator_timeout"],
                test_data["validator_confirm"],
                test_data["validator_no_data"],
            ],
            "verifier": test_data["verifier_correct"],
            "linter": test_data["linter_done"],
        }
        for elem in prepare_files(test_input).findall("run"):
            self.assertEqual(
                result.CATEGORY_CORRECT,
                elem.find('column[@title="category"]').get("value"),
            )

    def test_merge_verifier_correct_linter_done_validator_timeout_confirm_reject(self):
        # if at least one validator confirms a linter-approved witness, the category stays correct
        test_input = {
            "validators": [
                test_data["validator_timeout"],
                test_data["validator_confirm"],
                test_data["validator_reject"],
            ],
            "verifier": test_data["verifier_correct"],
            "linter": test_data["linter_done"],
        }
        for elem in prepare_files(test_input).findall("run"):
            self.assertEqual(
                result.CATEGORY_CORRECT,
                elem.find('column[@title="category"]').get("value"),
            )

    def test_merge_verifier_wrong_linter_done_validator_timeout_reject_none(self):
        # if the verifier is wrong, the category must not change
        test_input = {
            "validators": [
                test_data["validator_timeout"],
                test_data["validator_reject"],
                test_data["validator_no_data"],
            ],
            "verifier": test_data["verifier_wrong"],
            "linter": test_data["linter_done"],
        }
        for elem in prepare_files(test_input).findall("run"):
            self.assertEqual(
                result.CATEGORY_WRONG,
                elem.find('column[@title="category"]').get("value"),
            )

    def test_merge_verifier_wrong_linter_done_validator_timeout_confirm_no_data(self):
        # if the verifier is wrong, the category must not change
        test_input = {
            "validators": [
                test_data["validator_timeout"],
                test_data["validator_confirm"],
                test_data["validator_no_data"],
            ],
            "verifier": test_data["verifier_wrong"],
            "linter": test_data["linter_done"],
        }
        for elem in prepare_files(test_input).findall("run"):
            self.assertEqual(
                result.CATEGORY_WRONG,
                elem.find('column[@title="category"]').get("value"),
            )

    def test_merge_verifier_wrong_linter_done_validator_timeout_confirm_reject(self):
        # if the verifier is wrong, the category must not change
        test_input = {
            "validators": [
                test_data["validator_timeout"],
                test_data["validator_confirm"],
                test_data["validator_reject"],
            ],
            "verifier": test_data["verifier_wrong"],
            "linter": test_data["linter_done"],
        }
        for elem in prepare_files(test_input).findall("run"):
            self.assertEqual(
                result.CATEGORY_WRONG,
                elem.find('column[@title="category"]').get("value"),
            )

    def test_merge_verifier_wrong_linter_done_validator_timeout_memory_none(self):
        # if the verifier is wrong, the category must not change
        test_input = {
            "validators": [
                test_data["validator_timeout"],
                test_data["validator_no_data"],
                test_data["validator_out_of_memory"],
            ],
            "verifier": test_data["verifier_wrong"],
            "linter": test_data["linter_done"],
        }
        for elem in prepare_files(test_input).findall("run"):
            self.assertEqual(
                result.CATEGORY_WRONG,
                elem.find('column[@title="category"]').get("value"),
            )

    def test_merge_verifier_correct_overflow_mismatching_property_linter_done_validator_overflow_false_confirm_no_data(
        self,
    ):
        # if at least one validator confirms a linter-approved witness with mismatching properties, the category stays correct
        test_input = {
            "validators": [
                test_data["validator_timeout"],
                test_data["validator_overflow_false"],
                test_data["validator_no_data"],
            ],
            "verifier": test_data["verifier_correct_overflow_mismatching_property"],
            "linter": test_data["linter_done"],
        }
        for elem in prepare_files(test_input).findall("run"):
            self.assertEqual(
                result.CATEGORY_CORRECT,
                elem.find('column[@title="category"]').get("value"),
            )

    def test_merge_verifier_correct_deref_linter_done_validator_deref_false_confirm_no_data(
        self,
    ):
        # if at least one validator confirms a linter-approved witness with valid-memsafety properties, the category stays correct
        test_input = {
            "validators": [
                test_data["validator_timeout"],
                test_data["validator_deref_false"],
                test_data["validator_no_data"],
            ],
            "verifier": test_data["verifier_correct_deref"],
            "linter": test_data["linter_done"],
        }
        for elem in prepare_files(test_input).findall("run"):
            self.assertEqual(
                result.CATEGORY_CORRECT,
                elem.find('column[@title="category"]').get("value"),
            )

    def test_merge_verifier_correct_deref_mismatching_property_linter_done_validator_deref_false_confirm_no_data(
        self,
    ):
        # if a validator confirms a linter-approved witness with mismatching valid-memsafety properties, the category becomes unconfirmed
        # this should never happen, as Benchexec would not allow setting correct=true if the expected and real verdicts differ in the
        # specified subproperty, but nevertheless, this is the expected behavior in that case.
        test_input = {
            "validators": [
                test_data["validator_timeout"],
                test_data["validator_deref_false"],
                test_data["validator_no_data"],
            ],
            "verifier": test_data["verifier_correct_deref_mismatching_property"],
            "linter": test_data["linter_done"],
        }
        for elem in prepare_files(test_input).findall("run"):
            self.assertEqual(
                result.CATEGORY_CORRECT_UNCONFIRMED,
                elem.find('column[@title="category"]').get("value"),
            )

    def test_merge_validators_timeout(self):
        test_input = {
            "validators": [
                test_data["validator_timeout"],
                test_data["validator_timeout"],
                test_data["validator_timeout"],
            ],
            "verifier": test_data["verifier_correct"],
            "linter": test_data["linter_done"],
        }
        for elem in prepare_files(test_input).findall("run"):
            self.assertEqual(
                result.CATEGORY_CORRECT_UNCONFIRMED,
                elem.find('column[@title="category"]').get("value"),
            )

    def test_merge_linter_error_or_no_data(self):
        # In any combination, the status has to be error if the linter has no file or detects errors.
        # However, if the verifier is wrong, the category stays wrong.
        for verifier in [
            "verifier_correct",
            "verifier_wrong",
            "verifier_error",
            "verifier_no_data",
        ]:
            for validator in [
                "validator_confirm",
                "validator_reject",
                "validator_timeout",
                "validator_no_data",
            ]:
                for linter in ["linter_error", "linter_no_data"]:
                    test_input = {
                        "validators": [test_data[validator]],
                        "verifier": test_data[verifier],
                        "linter": test_data[linter],
                    }
                    for elem in prepare_files(test_input).findall("run"):
                        if verifier == "verifier_wrong":
                            self.assertEqual(
                                result.CATEGORY_WRONG,
                                elem.find('column[@title="category"]').get("value"),
                            )
                        else:
                            self.assertEqual(
                                result.CATEGORY_ERROR,
                                elem.find('column[@title="category"]').get("value"),
                            )

    def test_remove_correct(self):
        banned = {"../sv-benchmarks/c/test.yml", "../sv-benchmarks/c/test/test.yml"}
        xml = str(
            pathlib.Path(__file__).parent.resolve()
            / "test_mkAnaRemoveResults/test_data/test_run.xml.bz2"
        )
        verifier_runs = BenchmarkRuns(xml)
        adjust_results_verifiers.adjust_status_category(
            verifier_runs, [], [], invalid_tasks=banned
        )
        for run in verifier_runs.as_dictionary.values():
            for b in banned:
                if run.get("name").endswith(b):
                    self.assertTrue(
                        run.find('column[@title="status"]')
                        .get("value")
                        .startswith("invalid task")
                    )
                    self.assertEqual(
                        run.find('column[@title="category"]').get("value"),
                        result.CATEGORY_MISSING,
                    )
