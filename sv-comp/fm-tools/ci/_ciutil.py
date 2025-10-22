import logging
from pathlib import Path
from typing import Iterable

import yaml

COLOR_RED = "\033[31;1m"
COLOR_GREEN = "\033[32;1m"
COLOR_ORANGE = "\033[33;1m"
COLOR_MAGENTA = "\033[35;1m"

COLOR_DEFAULT = "\033[m"
COLOR_DESCRIPTION = COLOR_MAGENTA
COLOR_VALUE = COLOR_GREEN
COLOR_WARNING = COLOR_RED

# if not sys.stdout.isatty():
#    COLOR_DEFAULT = ''
#    COLOR_DESCRIPTION = ''
#    COLOR_VALUE = ''
#    COLOR_WARNING = ''


def _add_color(description, value, color=COLOR_VALUE, sep=": "):
    return "".join(
        (
            COLOR_DESCRIPTION,
            description,
            COLOR_DEFAULT,
            sep,
            color,
            value,
            COLOR_DEFAULT,
        )
    )


def error(msg, cause=None, label="    ERROR"):
    msg = _add_color(label, str(msg), color=COLOR_WARNING)
    if cause:
        logging.exception(msg)
    else:
        logging.error(msg)


def info(msg, label="INFO"):
    msg = str(msg)
    if label:
        msg = _add_color(label, msg)
    logging.info(msg)


def parse_yaml(yaml_file):
    try:
        with open(yaml_file) as inp:
            return yaml.safe_load(inp)
    except yaml.scanner.ScannerError as e:
        logging.error("Exception while scanning %s", yaml_file)
        raise e


def get_benchmark_filename(tool: str, competition_track: str) -> str:
    benchmark_def_name = f"{tool}-{get_track_for_filename(competition_track)}"
    if competition_track in ["Verification", "Test Generation"]:
        benchmark_def_name = tool
    return benchmark_def_name


def get_track_for_filename(competition_track: str) -> str:
    return (
        competition_track.lower()
        .replace(" ", "-")
        .replace("verification", "verify")
        .replace("test-generation", "test")
        .replace("validation-of", "validate")
    )


def get_archive_name_for_validator(validator_identifier):
    return f"val_{validator_identifier.rsplit('-validate-')[0]}.zip"


def get_archive_name_for_verifier(verifier_identifier):
    return f"{verifier_identifier}.zip"


def verifiers_in_category(category_info, category):
    categories = category_info["categories"]
    selected = categories.get(category, {})
    return [v + ".xml" for v in selected.get("verifiers", [])]


def validators_in_category(category_info, category):
    categories = category_info["categories"]
    selected = categories.get(category, {})
    validators = []
    # Construction of the bench-def.xml is according to this pattern,
    # based on how category-structure.yml names validators:
    # 1. toolname-violation -> toolname-validate-violation-witnesses.xml
    # 2. toolname-correctness -> toolname-validate-correctness-witnesses.xml
    # 3. toolname only -> toolname-validate-witnesses.xml
    for validator in selected.get("validators", []):
        try:
            tool_name, validation_type = validator.rsplit("-")
            validators.append(f"{tool_name}-validate-{validation_type}-witnesses.xml")
        except ValueError:
            tool_name = validator
            validators.append(f"{tool_name}-validate-witnesses.xml")
    return validators


def unused_verifiers(category_info):
    if "not_participating" not in category_info:
        return []
    return category_info["not_participating"]


def get_category_name(set_file) -> str:
    if isinstance(set_file, Path):
        return get_category_name(set_file.name)
    name = set_file
    if name.endswith(".set"):
        name = name[: -len(".set")]
    if "." in name:
        name = ".".join(name.split(".")[1:])
    return name


def is_category_empty(set_file: Path, prop: str) -> Iterable[str]:
    """
    Returns whether a given property never occurs in any task of a given set file.

    Returns False if at least one task included by the given set file defines
    the given property (by name).
    Returns True otherwise.
    """
    return all(
        prop not in get_properties_of_task(t) for t in get_setfile_tasks(set_file)
    )


def get_setfile_tasks(set_file: Path) -> Iterable[Path]:
    """Returns all tasks (as paths) defined in a given set file."""
    with open(set_file) as inp:
        globs = [
            line.strip()
            for line in inp.readlines()
            if line.strip() and not line.strip().startswith("#")
        ]
    return (t for g in globs for t in set_file.parent.glob(g))


def get_properties_of_task(task_file: Path) -> Iterable[str]:
    """Returns the names of all properties defined in a given YAML task file."""
    task_yaml = parse_yaml(task_file)
    properties = task_yaml["properties"]
    if not isinstance(properties, list):
        properties = [properties]
    return (_get_prop_name(p["property_file"]) for p in properties)


def _get_prop_name(property_file) -> str:
    """Returns the property name (as used in SV-COMP and Test-Comp) for a given .prp file."""
    if isinstance(property_file, Path):
        return property_file.name[: -len(".prp")]
    return _get_prop_name(Path(property_file))
