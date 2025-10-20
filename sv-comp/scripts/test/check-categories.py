#!/usr/bin/env python3
import argparse
from collections import namedtuple, defaultdict
import logging
from pathlib import Path
import sys
from typing import Iterable
import itertools
import _util as util
import xml.etree.ElementTree as ET

sys.path.append(
    str(
        Path(__file__).parent.parent.parent.resolve()
        / "fm-tools/lib-fm-tools/python/src"
    )
)
from fm_tools.competition_participation import Competition
from fm_tools.fmtoolscatalog import FmToolsCatalog

sys.path.append(str(Path(__file__).parent.parent.resolve()))
from prepare_tables.utils import (
    competition_from_string,
    verifiers_of_competition,
    validators_of_competition,
)

LINTERS = [
    "witnesslint-validate-violation-witnesses-1.0",
    "witnesslint-validate-violation-witnesses-2.0",
    "witnesslint-validate-correctness-witnesses-1.0",
    "witnesslint-validate-correctness-witnesses-2.0",
]


def _all_categories(category_info: dict) -> Iterable[str]:
    meta_categories = category_info["categories"]
    categories = set(meta_categories.keys())
    for info in meta_categories.values():
        # do not use util.get_category_name(c) on purpose, to distinguish same task sets for different properties
        categories |= set(info["categories"])
    return categories


def _check_info_consistency(category_info: dict) -> Iterable[str]:
    if "categories_process_order" not in category_info:
        yield "Missing 'categories_process_order'"
        return
    in_process_order = set(category_info["categories_process_order"])

    if "categories_table_order" not in category_info:
        yield "Missing 'categories_table_order'"
        return
    in_table_order = set(category_info["categories_table_order"])

    if len(in_process_order) > len(in_table_order):
        yield f"Categories listed in process order, but missing in table order: {in_process_order - in_table_order}"
    if len(in_process_order) < len(in_process_order):
        yield f"Categories listed in table order, but missing in process order: {in_table_order - in_process_order}"

    categories_used = _all_categories(category_info)
    if len(categories_used) > len(in_process_order | in_table_order):
        yield f"Categories (used in) meta categories, but missing in process and table order: {categories_used - (in_process_order | in_table_order)}"
    if len(categories_used) < len(in_process_order | in_table_order):
        yield f"Categories used in process or table order, but missing in meta categories: {(in_process_order | in_table_order) - categories_used}"

    for opt in ("opt_in", "opt_out"):
        if opt not in category_info or not category_info[opt]:
            continue  # no opt_in or opt_out in category info
        for category in {
            c for categories in category_info[opt].values() for c in categories
        }:
            if category not in categories_used:
                yield f"Category used in {opt}, but missing in meta categories: {category}"


def _check_validator_participation(
    category_info: dict, validators: list[str]
) -> Iterable[str]:
    category_validators = set()
    for name, c in category_info["categories"].items():
        category_validators |= set(c["validators"])
        for v in c["validators"]:
            if v not in validators:
                yield f"Validator {v} in category {name} not in list of validators"
    if set(validators) != category_validators:
        yield f"Validators in FM-Tools ({validators}) differ from validators in categories ({category_validators})"


def _check_category_participants(
    category_info: dict, participants: Iterable[str]
) -> Iterable[str]:
    participants = set(participants)
    list_of_not_participating = category_info["not_participating"]
    doubles = set(list_of_not_participating).intersection(participants)
    if doubles:
        yield f"Participant(s) listed as participant AND as 'not_participating': {doubles}"
    for name, c in category_info["categories"].items():
        not_participating = set(c["verifiers"]) - participants
        if not_participating:
            yield f"Verifiers listed in category {name}, but not participating: {not_participating}"

    yield from _check_participant_order(category_info)


def _check_category_benchdef_for_tool_exists(
    verifiers: list[str],
    validators: list[str],
    benchmark_defs: Path,
    competition: Competition,
):
    for t in itertools.chain(verifiers, validators):
        bench_def_path = benchmark_defs / f"{t}.xml"
        exists = bench_def_path.is_file()
        if not exists:
            yield f"Cannot find benchmark definition for {bench_def_path}. Add the tool to https://gitlab.com/sosy-lab/{competition.value.lower()}/bench-defs/-/tree/main/benchmark-defs/."


def _check_participant_order(category_info: dict) -> Iterable[str]:
    verifiers = category_info["verifiers"]

    def sort(vs: list[str]) -> list[str]:
        return sorted(vs, key=lambda v: v.lower())

    def out_of_order(vs):
        if sort(vs) != vs:
            yield f"Verifiers not in lexicographic order: {verifier_list(vs)}. Should be {verifier_list(sort(vs))}"

    def verifier_list(vs) -> str:
        return ", ".join(vs)

    yield from out_of_order(verifiers)

    for category, info in category_info["categories"].items():
        verifiers = info["verifiers"]
        yield from [f"{category}: {msg}" for msg in out_of_order(verifiers)]


def _check_metacategory_dependencies(category_info: dict) -> Iterable[str]:
    # TODO: This only checks one step dependencies i.e.
    # it will not try to recursively check dependencies+
    # Is sufficient for now but should be improved in the future
    categories = category_info["categories"]
    validation_only_categories = category_info["validation_only"]
    for meta_category, meta_info in sorted(categories.items(), key=lambda x: x[0]):
        full_categories = set(filter(lambda c: "." not in c, meta_info["categories"]))
        verifiers = set(meta_info["verifiers"])
        validators = set(meta_info["validators"])
        # Iterate over all full categories which exist in the
        # current meta category
        for category in full_categories:
            full_category = categories[category]
            verifiers_dependency = set(full_category["verifiers"])
            validators_dependency = set(full_category["validators"])
            # Check that all verifiers in the meta category are also
            # in the dependent category
            if category not in validation_only_categories:
                if not verifiers.issubset(verifiers_dependency):
                    yield f"Category {category} does not contain all verifiers of meta category {meta_category}. Missing: {verifiers - verifiers_dependency}"

            filtered_validators = set()
            for v in validators:
                witness_version = v.split("-")[-1]
                validator_type = "-".join(v.split("-")[-3:-1])
                if "correctness-witnesses" == validator_type:
                    if category in [
                        "ConcurrencySafety",
                        "MemSafety",
                        "Termination",
                        "JavaOverall",
                    ]:
                        continue
                elif "violation-witnesses" == validator_type:
                    if witness_version == "2.0":
                        if category in [
                            "ConcurrencySafety",
                            "Termination",
                            "JavaOverall",
                        ]:
                            continue
                filtered_validators.add(v)

            if not filtered_validators.issubset(validators_dependency):
                yield f"Category {category} does not contain all validators of meta category {meta_category}. Missing: {filtered_validators - validators_dependency}"


def check_categories(
    category_info: dict, benchmark_def: Path, fm_tools: FmToolsCatalog
) -> Iterable[str]:
    competition: Competition = competition_from_string(category_info["competition"])
    year = category_info["year"]
    verifiers = verifiers_of_competition(fm_tools, competition, year)
    validators = validators_of_competition(
        fm_tools, competition, year, include_postfix=True
    )
    errors = itertools.chain(
        _check_info_consistency(category_info),
        _check_category_participants(category_info, verifiers),
        _check_validator_participation(category_info, validators),
        _check_category_benchdef_for_tool_exists(
            verifiers, validators, benchmark_def, competition
        ),
        _check_metacategory_dependencies(category_info),
    )
    if competition == Competition.SV_COMP:
        errors = itertools.chain(errors, _check_witness_lint_categories(category_info))
    return errors


def check_all_tasks_used(
    tasks_dir: Path,
    category_info: dict,
    ignore: Iterable[Path],
    reference_benchdef_c: Path,
    reference_benchdef_java: Path,
) -> Iterable[str]:
    PropAndCat = namedtuple("PropAndCat", ["property", "category"])

    def to_category(category_key):
        if "." not in category_key:
            raise ValueError(
                f"Category key expected to be of form 'property.Name', but was '{category_key}'"
            )
        return PropAndCat(*category_key.split("."))

    # Collect <tasks> elements from the provided reference benchdefs
    reference_benchdefs = []
    if reference_benchdef_c:
        logging.debug("Checking that all tasks are used for C")
        reference_benchdefs.append(reference_benchdef_c)
    if reference_benchdef_java:
        logging.debug("Checking that all tasks are used for Java")
        reference_benchdefs.append(reference_benchdef_java)

    reference_tasks = {
        tasks.get("name"): tasks
        for ref_benchdef in reference_benchdefs
        for tasks in util.get_tasks(ref_benchdef)
    }
    assert (
        len({ref_benchdef.parent for ref_benchdef in reference_benchdefs}) == 1
    ), f"We currently only support that both reference benchmark definitions are in the same directory: {reference_benchdef_c.parent} != {reference_benchdef_java.parent}"
    reference_basedir = next(
        ref_benchdef.parent for ref_benchdef in reference_benchdefs
    )

    # This for-loop collects all set files and directories that are used in the
    # reference benchmark definition
    used_directories = defaultdict(set)
    for info in category_info["categories"].values():
        properties = info["properties"]
        if not isinstance(properties, list):
            properties = [properties]

        # by checking that there's a '.' in the category name,
        # we only check base categories and ignore other meta categories
        # that are used as sub-categories of the current meta category.
        used_categories = [to_category(c) for c in info["categories"] if "." in c]

        for prop in properties:
            # get all relevant <tasks> elements for the current property
            relevant_tasks = [
                reference_tasks[c.category]
                for c in used_categories
                if c.property == prop and c.category in reference_tasks
            ]
            # get all .set files included in the relevant <tasks> elements.
            # .set files are defined relative to the benchmark definition's directory,
            # so we use that as basis for the paths.
            used_set_files = [
                reference_basedir / Path(incl.text)
                for tasks_tag in relevant_tasks
                for incl in tasks_tag.findall("includesfile")
            ]
            used_directories[prop] |= {
                # We need to resolve the paths to absolute path to make sure that it matches
                # with tasks_dir later
                t.parent.resolve()
                for set_file in used_set_files
                for t in util.get_setfile_tasks(set_file)
            }

    # Collect task directories that can be ignored
    ignored_directories = {
        # We need to resolve the paths to absolute path to make sure that it matches
        # with tasks_dir later
        t.parent.resolve()
        for ignored_set_file in ignore
        for t in util.get_setfile_tasks(ignored_set_file)
    }

    # Different relative paths to the same directory would make this check fail.
    # So we resolve the path to an absolute path to make sure that it matches
    # with the used directories.
    tasks_dir = tasks_dir.resolve()

    # Check whether any sets are relevant and not used
    # Use absolute paths for ignore to make match with other set files unambiguous
    ignore = {i.resolve() for i in ignore}
    relevant_set_files = [
        set_file
        for set_file in tasks_dir.glob("**/*.set")
        if set_file.resolve() not in ignore
    ]
    logging.debug("Used directories per property: %s", used_directories)
    logging.debug("Ignored directories: %s", ignored_directories)
    for prop, used_dirs in used_directories.items():
        covered_directories = used_dirs.copy()
        sets_with_unused_tasks = set()
        for set_file in relevant_set_files:
            for t in util.get_setfile_tasks(set_file):
                task_parent_dir = t.parent
                if (
                    task_parent_dir in covered_directories
                    or task_parent_dir in ignored_directories
                ):
                    continue
                if prop in util.get_properties_of_task(t):
                    covered_directories.add(task_parent_dir)
                    logging.debug(
                        "Missing task dir included from %s: %s",
                        set_file,
                        task_parent_dir,
                    )
                    sets_with_unused_tasks.add(set_file)
        for set_file in sets_with_unused_tasks:
            yield f"For property {prop}, the following set contains unused tasks: {set_file}"


def _check_witness_lint_categories(category_info):
    for category in category_info["categories"]:
        if "java" in str(category).lower():
            # we ignore java since there is no witnesslint
            continue

        validators = set(category_info["categories"][category]["validators"])
        for linter in LINTERS:
            if "concurrency" in str(category).lower() and "correctness" in linter:
                continue
            if linter not in validators:
                yield f"{category} misses {linter}"


def check_witness_lint_xml(
    category_info, linter, witness_lint_file, witnesslint_allowed_missing_categories
):
    witness_lint = ET.parse(witness_lint_file)
    root = witness_lint.getroot()
    opt_out = category_info["opt_out"].get(linter, [])
    xml_categories = set()
    allowed_missing = set()
    for rundef in root.findall("rundefinition"):
        prefix = rundef.get("name").split("_")[-1]
        for task in rundef.findall("tasks"):
            category_name = task.get("name")
            if category_name in witnesslint_allowed_missing_categories:
                allowed_missing.add(f"{prefix}.{category_name}")
                continue
            xml_categories.add(f"{prefix}.{category_name}")
    yml_categories = set()
    for category in category_info["categories"]:
        if "java" in str(category).lower():
            # we ignore java since there is no witnesslint
            continue
        if "overall" in str(category).lower():
            # we ignore category overall since it only contains meta categories which are not specified in the xml files
            # same applies for category falsification overall
            continue
        if linter not in category_info["categories"][category]["validators"]:
            # we ignore this category since there is no witnesslint
            continue
        for sub_category in category_info["categories"][category]["categories"]:
            if sub_category not in opt_out:
                yml_categories.add(sub_category)
    if len(yml_categories) < len(xml_categories):
        yield (
            f"There are more categories in {witness_lint_file} as in the "
            f"category_structure.yml, namely {xml_categories.difference(yml_categories)}"
        )
    difference = yml_categories.difference(xml_categories) - allowed_missing
    if difference:
        yield f"{witness_lint_file} misses the following categories: {difference}"


def parse_args(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--category-structure",
        default="benchmark-defs/category-structure.yml",
        required=False,
        help="category-structure.yml to use",
    )
    parser.add_argument(
        "--reference-benchdef-c",
        default=None,
        required=False,
        help="Reference XML that contains the tasks definitions for all C categories."
        + " If this is given, check that the categories do not miss any possible C analysis tasks",
    )

    parser.add_argument(
        "--reference-benchdef-java",
        default=None,
        required=False,
        help="Reference XML that contains the tasks definitions for all Java categories."
        + " If this is given, check that the categories do not miss any possible Java analysis tasks",
    )
    parser.add_argument(
        "--witness-lint-correctness-1",
        default="benchmark-defs/witnesslint-validate-correctness-witnesses-1.0.xml",
        required=False,
        help="category-structure.yml to use",
    )
    parser.add_argument(
        "--witness-lint-correctness-2",
        default="benchmark-defs/witnesslint-validate-correctness-witnesses-2.0.xml",
        required=False,
        help="category-structure.yml to use",
    )
    parser.add_argument(
        "--witness-lint-violation-1",
        default="benchmark-defs/witnesslint-validate-violation-witnesses-1.0.xml",
        required=False,
        help="category-structure.yml to use",
    )
    parser.add_argument(
        "--witness-lint-violation-2",
        default="benchmark-defs/witnesslint-validate-violation-witnesses-2.0.xml",
        required=False,
        help="category-structure.yml to use",
    )
    parser.add_argument(
        "--allow-unused",
        dest="allow_unused",
        default="",
        type=str,
        help="comma-separated list of set files whose tasks may be left out from category structure",
    )
    parser.add_argument(
        "--tasks-directory",
        dest="tasks_base_dir",
        default="sv-benchmarks",
        required=False,
        help="directory to benchmark tasks",
    )
    parser.add_argument(
        "--benchdef-xmls",
        dest="benchdef_xmls",
        default="benchmark-defs",
        required=False,
        help="directory benchmark-defs directory in the bench-defs repository.",
    )
    parser.add_argument(
        "--fm-tools",
        default=Path("fm-tools/data"),
        type=Path,
        help="Directory with archive files to check",
    )
    parser.add_argument(
        "--witnesslint-allowed-missing-categories",
        dest="witnesslint_allowed_missing_categories",
        default="",
        help="comma-separated list of categories that are allowed to be missing in when checking the witnesslint categories",
    )

    args = parser.parse_args(argv)

    args.category_structure = Path(args.category_structure)
    args.tasks_base_dir = Path(args.tasks_base_dir)
    args.benchdef_xmls = Path(args.benchdef_xmls)
    args.allow_unused = (
        [Path(ignore_set) for ignore_set in args.allow_unused.split(",")]
        if args.allow_unused
        else []
    )
    if args.reference_benchdef_c is not None:
        args.reference_benchdef_c = Path(args.reference_benchdef_c)
    if args.reference_benchdef_java is not None:
        args.reference_benchdef_java = Path(args.reference_benchdef_java)
    missing_files = [
        f
        for f in [
            args.category_structure,
            args.reference_benchdef_c,
            args.reference_benchdef_java,
        ]
        + args.allow_unused
        if f and not f.exists()
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

    success = True
    category_info = util.parse_yaml(args.category_structure)
    competition = competition_from_string(category_info["competition"])
    fm_tools = FmToolsCatalog(args.fm_tools)

    logging.warning("Checking categories ...")
    errors = check_categories(category_info, args.benchdef_xmls, fm_tools)
    for msg in errors:
        success = False
        util.error(msg)
    if args.reference_benchdef_c or args.reference_benchdef_java:
        logging.warning("Checking that all tasks are used ...")
        errors = check_all_tasks_used(
            args.tasks_base_dir,
            category_info,
            ignore=args.allow_unused,
            reference_benchdef_c=args.reference_benchdef_c,
            reference_benchdef_java=args.reference_benchdef_java,
        )
        for msg in errors:
            success = False
            util.error(msg)
    else:
        logging.warning(
            "WARN: No reference benchdef given, so there is no check that all categories are used"
        )
    if competition == Competition.SV_COMP:
        logging.warning("Checking WitnessLint definitions ...")
        witnesslint_allowed_missing_categories = (
            args.witnesslint_allowed_missing_categories.split(",")
        )
        errors = itertools.chain(
            errors,
            check_witness_lint_xml(
                category_info,
                "witnesslint-validate-violation-witnesses-1.0",
                witness_lint_file=args.witness_lint_violation_1,
                witnesslint_allowed_missing_categories=witnesslint_allowed_missing_categories,
            ),
            check_witness_lint_xml(
                category_info,
                "witnesslint-validate-violation-witnesses-2.0",
                witness_lint_file=args.witness_lint_violation_2,
                witnesslint_allowed_missing_categories=witnesslint_allowed_missing_categories,
            ),
            check_witness_lint_xml(
                category_info,
                "witnesslint-validate-correctness-witnesses-1.0",
                witness_lint_file=args.witness_lint_correctness_1,
                witnesslint_allowed_missing_categories=witnesslint_allowed_missing_categories,
            ),
            check_witness_lint_xml(
                category_info,
                "witnesslint-validate-correctness-witnesses-2.0",
                witness_lint_file=args.witness_lint_correctness_2,
                witnesslint_allowed_missing_categories=witnesslint_allowed_missing_categories,
            ),
        )
        for msg in errors:
            success = False
            util.error(msg)
    return 0 if success else 1


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format=None)
    sys.exit(main())
