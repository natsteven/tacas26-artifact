#!/usr/bin/env python3
import argparse
import sys
import logging
from pathlib import Path
from lxml import etree
import _util as util
from typing import Iterable

ALLOWLIST_TASK_SETS = [
    # only properties not used in SV-COMP
    "def-behavior.DefinedBehavior-TerminCrafted",
    # only properties not used in SV-COMP
    "def-behavior.DefinedBehavior-Arrays",
    # only properties not used in SV-COMP
    "coverage-branches.SoftwareSystems-SQLite-MemSafety",
    # unused
    "valid-memsafety.Unused_Juliet",
    # no coverage-error-call properties so far, false positive
    "coverage-error-call.SoftwareSystems-AWS-C-Common-ReachSafety",
    # no coverage-error-call properties so far, false positive
    "coverage-error-call.ReachSafety-Combinations",
    # no coverage-error-call properties so far, false positive
    "coverage-error-call.Termination-MainControlFlow",
    # no coverage-error-call properties so far, false positive
    "coverage-error-call.Termination-BitVectors",
    # no coverage-error-call properties so far, false positive
    "coverage-error-call.Termination-MainHeap",
    # no coverage-error-call properties so far, false positive
    "coverage-error-call.ReachSafety-Hardness",
    # no coverage-error-call properties so far, false positive
    "coverage-error-call.SoftwareSystems-SQLite-MemSafety",
]

CPU_MODELS_TO_USE = ["Intel Xeon E3-1230 v5 @ 3.40 GHz"]
CPU_MODELS_TO_USE_VALIDATION = [
    "Intel Xeon E3-1230 v5 @ 3.40 GHz",
    "Intel Core i7-10700 @ 2.90 GHz",
    "Intel Core i7-6700 @ 3.40 GHz",
    "AMD EPYC 7713 64-Core",
]

WITNESS_REQUIRED_PATH = [
    "../results-verified/LOGDIR/${rundefinition_name}/${taskdef_name}/witness.graphml",
    "../results-verified/LOGDIR/${rundefinition_name}/${taskdef_name}/witness.yml",
    "../results-verified/LOGDIR/${rundefinition_name}/${taskdef_name}/test-suite.zip",
]
WITNESS_TOOL_PATH = [
    "../../results-verified/LOGDIR/${rundefinition_name}/${taskdef_name}/witness.graphml",
    "../../results-verified/LOGDIR/${rundefinition_name}/${taskdef_name}/witness.yml",
    "../../results-verified/LOGDIR/${rundefinition_name}/${taskdef_name}/test-suite.zip",
]


def _check_valid(xml_file: Path):
    """Tries to parse the given xml file and returns any produced exceptions."""
    try:
        util.parse_xml(str(xml_file), check_dtd=True)
        return []
    except (etree.ParseError, etree.XMLSyntaxError) as e:
        return ["Failed parsing xml: " + str(e)]


def _check_task_defs_match_set(xml_file: Path, /, tasks_dir: Path):
    """Checks that each task element in the given xml_file fulfills certain criteria.

    The criteria are the following:
    1. each task element has an attribute 'name'
    2. each task element contains at least one includesfile element
    3. each includesfile element references a `.set`-file in the sv-benchmarks directory
    4. each referenced `.set`-file matches the name of the task element
    """
    errors = []
    for task_tag in util.get_tasks(xml_file):
        name = task_tag.get("name")
        if not name:
            errors.append(
                "Task tag is missing name in line {}".format(task_tag.sourceline)
            )

        try:
            included_sets = _get_setfiles(task_tag, relative_to=xml_file.parent)
        except ValueError as e:
            errors.append(str(e))
        else:
            for included_set in included_sets:
                benchmark_dir = included_set.parent.resolve()
                expected_dir = tasks_dir.resolve()
                if expected_dir.exists() and benchmark_dir != expected_dir:
                    logging.warning(
                        "Expected directory of set to be %s for tasks %s (is %s)",
                        expected_dir,
                        name,
                        benchmark_dir,
                    )
                set_file = included_set.name
                if not set_file.endswith(".set"):
                    errors.append(
                        "Set name does not end on '.set': {}".format(set_file)
                    )

        if task_tag.findall("option"):
            errors.append("task {} contains <option> tag.".format(name))

    return errors


def _check_validators_use_correct_path_to_witnesses(xml):
    benchdef = util.parse_xml(xml)
    errors = []
    for rundef in benchdef.findall("rundefinition"):
        contains_required = False
        contains_witness_path = False
        for required in rundef.findall("requiredfiles"):
            contains_required = (
                contains_required or required.text in WITNESS_REQUIRED_PATH
            )
        for options in rundef.findall("option"):
            contains_witness_path = (
                contains_witness_path or options.text in WITNESS_TOOL_PATH
            )
        if not contains_required:
            errors.append(f"{rundef.get('name')} misses required files for witnesses.")
        if not contains_witness_path:
            errors.append(f"{rundef.get('name')} misses path to witness for validator.")
    return errors


def _get_base_categories_participating(
    verifier, category_info, exclude_opt_outs=False
) -> set:
    if category_info["opt_out"] and verifier in category_info["opt_out"]:
        opt_outs = set(category_info["opt_out"][verifier])
    else:
        opt_outs = set()
    if category_info["opt_in"] and verifier in category_info["opt_in"]:
        opt_ins = set(category_info["opt_in"][verifier])
    else:
        opt_ins = set()

    meta_categories = category_info["categories"]
    categories_participating = set()
    for category, info in meta_categories.items():
        if exclude_opt_outs and category in opt_outs:
            continue
        participants = info["verifiers"]
        if verifier in participants:
            categories_participating |= set(info["categories"])

    categories_participating = categories_participating - set(meta_categories.keys())
    if exclude_opt_outs:
        categories_participating -= opt_outs
    categories_participating |= opt_ins
    return categories_participating


def _get_verifier_name(bench_def: Path) -> str:
    return bench_def.name[: -len(".xml")]


def _get_setfiles(task_tag: etree.Element, /, relative_to: Path) -> Iterable[Path]:
    includes = task_tag.findall("includesfile")
    if len(includes) == 0:
        raise ValueError("Expected at least one <includesfile> tag.")
    return [relative_to / Path(incl.text) for incl in includes]


def _get_categories(bench_def) -> Iterable[str]:
    rundefinitions = util.get_rundefinitions(bench_def)
    tasks_toplevel = util.get_tasks(bench_def, recursive=False)

    categories = set()
    for rundef in rundefinitions:
        name = rundef.get("name")
        _, _, category_property = name.partition("_")
        for t in tasks_toplevel:
            tasks_name = t.get("name")
            category = f"{category_property}.{tasks_name}"
            categories.add(category)

        tasks_rundef = list(rundef.iter(tag="tasks"))
        for t in tasks_rundef:
            tasks_name = t.get("name")
            category = f"{category_property}.{tasks_name}"
            setfiles = _get_setfiles(t, relative_to=bench_def.parent)
            empty_setfiles = [
                setfile
                for setfile in setfiles
                if util.is_category_empty(setfile, category_property)
            ]
            # A <tasks> element is defined inside a run definition,
            # but the set of run-definition + tasks is empty.
            # This means that an always-empty category is defined
            if empty_setfiles == setfiles:
                raise ValueError(f"All set files are empty for category {category}")
            else:
                for empty_setfile in empty_setfiles:
                    logging.warning(
                        f"Category {category} is empty for set file {empty_setfile}"
                    )
            categories.add(category)

    return categories


def _check_all_sets_used(
    bench_def: Path, category_info, /, tasks_directory: Path, exceptions: list = []
):
    categories_included = _get_categories(bench_def)
    categories_expected = _get_base_categories_participating(
        _get_verifier_name(bench_def), category_info
    )

    if not categories_expected:
        return ["No entry in category info"]

    errors = list()

    obsolete_categories = categories_included - categories_expected - set(exceptions)
    if obsolete_categories:
        errors += [
            f"Sets used that are not defined in category structure: {obsolete_categories}"
        ]
    missing_categories = categories_expected - categories_included - set(exceptions)

    if missing_categories:
        errors += [f"Missing includes for following sets: {missing_categories}"]
    return errors


def _check_verifier_listed_in_category_info(xml: Path, category_info):
    verifier = _get_verifier_name(xml)
    if "validate" in verifier:
        return []

    participants_key = "verifiers"
    not_participating_key = "not_participating"
    participating = category_info[participants_key]
    not_participating = category_info[not_participating_key]

    if verifier not in participating and verifier not in not_participating:
        return [
            f"Verifier not listed in category_structure.yml. Add either to '{participants_key}' or to '{not_participating_key}'"
        ]
    return []


def _check_required_options(bench_def: Path, cpu_models):
    errors = []
    xml_root = util.parse_xml(bench_def)
    errors += _check_required_option_cpuModel_set(xml_root, cpu_models)
    return errors


def _check_no_additional_parameters_in_subcategory(xml):
    """
    Ensures that no options within subcategories are specified.

    This is disallowed:

    <rundefinition name="SV-COMP23_unreach-call">
      <tasks name="ReachSafety-Arrays">
        <option name="name">name</option>
        <includesfile>../sv-benchmarks/c/ReachSafety-Arrays.set</includesfile>
        <propertyfile>../sv-benchmarks/c/properties/unreach-call.prp</propertyfile>
      </tasks>
    </rundefinition>

    :param xml: path to xml file
    :return: a list of error messages if violations are found
    """
    benchdef = util.parse_xml(xml)
    errors = []
    for rundef in benchdef.findall("rundefinition"):
        for tasks in rundef.findall("tasks"):
            options = [o.get("name") for o in tasks.findall("option")]
            if options:
                errors.append(
                    f"{tasks.get('name')} in {rundef.get('name')} contains the following additional program parameters: {options}"
                )
    return errors


def _check_required_option_cpuModel_set(
    xml_root,
    cpu_models,
    name_require_elem="require",
    name_cpuModel_attrib="cpuModel",
):
    for elem in xml_root.findall(name_require_elem):
        if name_cpuModel_attrib in elem.attrib:
            if set(elem.attrib[name_cpuModel_attrib].split(",")).issubset(cpu_models):
                return []
            return [
                f'Wrong CPU model set in element \'{name_require_elem}\': "{elem.attrib[name_cpuModel_attrib]}" should be "{cpu_models}"'
            ]
    return ["CPU model not set. Add with '<require cpuModel=...'"]


def _perform_checks(xml: Path, category_info, tasks_dir: Path):
    util.info(str(xml), label="CHECKING")
    xml_errors = _check_valid(xml)
    errors = []
    if xml_errors:
        return xml_errors
    cpu_models = CPU_MODELS_TO_USE
    if "validate" in xml.name:
        cpu_models = CPU_MODELS_TO_USE_VALIDATION
    if "validate" not in xml.name:
        errors += _check_no_additional_parameters_in_subcategory(xml)
    errors += _check_task_defs_match_set(xml, tasks_dir=tasks_dir)
    errors += _check_verifier_listed_in_category_info(xml, category_info)
    errors += _check_required_options(xml, cpu_models)
    if "validate" in xml.name:
        errors += _check_validators_use_correct_path_to_witnesses(xml)
    if tasks_dir.exists() and "validate" not in xml.name:
        errors += _check_all_sets_used(
            xml,
            category_info,
            tasks_directory=tasks_dir,
            exceptions=ALLOWLIST_TASK_SETS,
        )
    return errors


def _check_bench_def(xml: Path, category_info, /, tasks_dir: Path):
    """Checks the given xml benchmark definition for conformance."""
    errors = _perform_checks(xml, category_info, tasks_dir)
    if errors:
        util.error(xml)
        for msg in errors:
            util.error(msg)
    return not errors


def parse_args(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--category-structure",
        default="benchmark-defs/category-structure.yml",
        required=False,
        help="category-structure.yml to use",
    )
    parser.add_argument(
        "--tasks-directory",
        dest="tasks_base_dir",
        default="sv-benchmarks",
        required=False,
        help="directory to benchmark tasks",
    )
    parser.add_argument(
        "benchmark_definition",
        nargs="+",
        help="benchmark-definition XML files to check",
    )

    args = parser.parse_args(argv)

    args.category_structure = Path(args.category_structure)
    args.tasks_base_dir = Path(args.tasks_base_dir)
    args.benchmark_definition = [
        Path(bench_def) for bench_def in args.benchmark_definition
    ]

    missing_files = [
        f
        for f in args.benchmark_definition + [args.category_structure]
        if not f.exists()
    ]
    if missing_files:
        raise ValueError(
            f"File(s) do not exist: {','.join([str(f) for f in missing_files])}"
        )
    return args


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    args = parse_args(argv)

    category_info = util.parse_yaml(args.category_structure)
    java_verifiers = util.verifiers_in_category(category_info, "JavaOverall")
    java_validators = util.validators_in_category(category_info, "JavaOverall")
    unmaintained = util.unused_verifiers(category_info)
    success = True
    if not args.tasks_base_dir or not args.tasks_base_dir.exists():
        util.info(
            f"Tasks directory doesn't exist. Will skip some checks. (Directory: {str(args.tasks_base_dir)})"
        )
    for bench_def in args.benchmark_definition:
        if _get_verifier_name(bench_def) in unmaintained:
            util.info(f"{bench_def}", label="SKIP")
            continue
        if bench_def.is_dir():
            util.info(str(bench_def) + " (is directory)", label="SKIP")
            continue
        if bench_def.name in java_verifiers or bench_def.name in java_validators:
            tasks_directory = args.tasks_base_dir / "java"
        else:
            tasks_directory = args.tasks_base_dir / "c"

        success &= _check_bench_def(bench_def, category_info, tasks_dir=tasks_directory)

    return 0 if success else 1


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format=None)
    sys.exit(main())
