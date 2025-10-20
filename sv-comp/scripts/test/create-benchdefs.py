#!/usr/bin/env python3

import argparse
import os
import sys
from typing import NamedTuple
from pathlib import Path
import re
import yaml

from xml.etree import ElementTree as ET

FM_TOOLS_BENCHEXEC_TOOLINFO_MODULE = "benchexec_toolinfo_module"
FM_TOOLS_INPUT_LANGUAGE = "input_languages"
FM_TOOLS_PARTICIPATION = "competition_participations"
FM_TOOLS_PARTICIPATION_TOOL_VERSION = "tool_version"
FM_TOOLS_VERSIONS = "versions"
FM_TOOLS_VERSION_NAME = "version"
FM_TOOLS_VERSION_BENCHEXEC_TOOLINFO_OPTIONS = "benchexec_toolinfo_options"
XML_DOCTYPE_DECLARATION = """<?xml version="1.0"?>
<!DOCTYPE benchmark PUBLIC "+//IDN sosy-lab.org//DTD BenchExec benchmark 2.3//EN" "https://www.sosy-lab.org/benchexec/benchmark-2.3.dtd">
"""

TRACK_SV_COMP_VERIFICATION_TRACK = "Verification"
TRACK_TEST_COMP_TEST_GENERATION_TRACK = "Test Generation"
TRACK_SV_COMP_VALIDATION_VIOLATION_1 = "Validation of Violation Witnesses 1.0"
TRACK_SV_COMP_VALIDATION_VIOLATION_2 = "Validation of Violation Witnesses 2.0"
TRACK_SV_COMP_VALIDATION_CORRECTNESS_1 = "Validation of Correctness Witnesses 1.0"
TRACK_SV_COMP_VALIDATION_CORRECTNESS_2 = "Validation of Correctness Witnesses 2.0"

WITNESS_PLACEHOLDER_TOOLINFO_OPTIONS = r"${witness}"
WITNESS_FILE_PLACEHOLDER = "witness_placeholder"

RELEVANT_LANGUAGES = ("C", "Java")
"""Languages that we currently support."""


# This class is copied and adjusted from
# https://stackoverflow.com/a/34324359/3012884
# We could also use lxml instead of the stdlib's ElementTree, but this would
# introduce an additional dependency.
class CommentedTreeBuilder(ET.TreeBuilder):
    def comment(self, data):
        self.start(ET.Comment, {})
        self.data(data)
        self.end(ET.Comment)


def parse_xml_with_comments(xml_string):
    parser = ET.XMLParser(target=CommentedTreeBuilder())
    return ET.fromstring(xml_string, parser=parser)


def _parse_tool_data(tool_data: str | Path | dict) -> dict:
    if isinstance(tool_data, (str, Path)):
        return yaml.safe_load(open(tool_data))
    return tool_data


def get_version_info(tool_data: str | Path | dict, version: str) -> dict:
    """
    Return the info for a given tool version.

    :param tool_data: The tool's fm-tools data (YAML file or parsed dict).
    :param version: The version of interest (for example "2.3.1")
    :return: The version info for the given version, or None if the tool does not
             have a version with the given version string.
    """
    tool_data = _parse_tool_data(tool_data)
    return next(
        (
            v
            for v in tool_data[FM_TOOLS_VERSIONS]
            if v[FM_TOOLS_VERSION_NAME] == version
        ),
        None,
    )


def get_participation_info(
    tool_data: str | Path | dict,
    *,
    competition: list[str] | str | None = None,
    track: list[str] | str | None = None,
) -> dict | None:
    """
    Return the participation info for a tool in a given competition and track.

    :param tool_data: The tool's fm-tools data (YAML file or parsed dict).
    :param competition: The competition of interest (for example "SV-COMP 2024").
                        If this is None, all competitions are considered.
    :param track: The track of interest (for example "Verification" or "Validation of
                  Correctness Witnesses 1.0"). If this is None, all tracks are considered.
    :return: The participation info for the tool in the given competition and track,
             or None if the tool does not participate in the given combination
             of competition and track.
    """
    tool_data = _parse_tool_data(tool_data)
    if isinstance(competition, str):
        competition = [competition]
    if isinstance(track, str):
        track = [track]
    try:
        return next(
            (
                p
                for p in tool_data[FM_TOOLS_PARTICIPATION]
                if (not competition or p["competition"] in competition)
                and (not track or p["track"] in track)
            ),
            None,
        )
    except KeyError:
        # Missing key in tool-data means the tool does not participate in any competition
        return None


def tool_participates(
    tool_file: str | Path | dict,
    *,
    competition: str | None = None,
    track: str | None = None,
) -> bool:
    """
    Return whether a tool participates in a given competition and track.

    :param tool_file: The tool's fm-tools data file or parsed dict.
    :param competition: The competition of interest (for example "SV-COMP 2024").
                        If this is None, all competitions are considered.
    :param track: The track of interest (for example "Verification" or "Test Generation").
                  If this is None, all tracks are considered.
    """
    return bool(get_participation_info(tool_file, competition=competition, track=track))


def get_participants(
    data_dir: str, *, competition: str, track: str, ignore: list[str] | None = None
) -> dict[str, str]:
    """
    Return all tools that participate in at least one competition.
    Information is based on the FM-tools data YAML files in the given data_dir.

    :param data_dir: The directory containing the FM-tools data YAML files.
    :param competition: The competition to consider (for example "SV-COMP 2024").
    :param track: The track to consider (for example "Verification").
    :param ignore: A list of tool names to ignore.
    :return: A dictionary of participants, mapping the tool name to the path of the FM-tools data file.
    """
    return {
        get_tool_name(fil): os.path.join(data_dir, fil)
        for fil in os.listdir(data_dir)
        if tool_participates(
            os.path.join(data_dir, fil), competition=competition, track=track
        )
        and (ignore is None or get_tool_name(fil) not in ignore)
    }


def get_tool_name(filename: str) -> str:
    return filename.split(".yml")[0].split("/")[-1]


def parse_cli(argv):
    parser = argparse.ArgumentParser(
        description="Create a benchmark XML for a fm-tools data file"
    )
    parser.add_argument(
        "--competition",
        required=True,
        help="Competition to consider. This must match the competition value in FM-Tools data. Example: 'SV-COMP 2024'",
    )
    parser.add_argument(
        "--track",
        required=True,
        help="Track to consider. This must match the 'track' value in FM-Tools data. Example: 'Test Generation'",
    )
    parser.add_argument(
        "--ignore",
        dest="ignore_tools",
        nargs="*",
        help="Ignore tools",
    )
    parser.add_argument(
        "--fm-data", required=True, help="fm-tools data file or directory"
    )
    parser.add_argument(
        "--xml-template-directory",
        required=True,
        help="Directory to consider for XML templates",
    )
    parser.add_argument(
        "--extension-directory",
        default=None,
        help="Directory to consider for template extensions",
    )
    parser.add_argument(
        "--category-structure", required=True, help="Category structure to use"
    )
    parser.add_argument("--output", required=True, help="Output folder")
    args = parser.parse_args(argv)

    if not os.path.exists(args.fm_data):
        raise ValueError(f"File {args.fm_data} does not exist")
    if os.path.isdir(args.fm_data):
        args.fm_data = get_participants(
            args.fm_data,
            competition=args.competition,
            track=args.track,
            ignore=args.ignore_tools,
        )
    else:
        tool_name = get_tool_name(args.fm_data)
        args.fm_data = {tool_name: args.fm_data}
    args.fm_data = {
        tool_name: yaml.safe_load(open(data_file))
        for tool_name, data_file in args.fm_data.items()
    }

    if not os.path.exists(args.xml_template_directory):
        raise ValueError(f"Directory {args.xml_template_directory} does not exist")

    if args.extension_directory is not None and not os.path.exists(
        args.extension_directory
    ):
        raise ValueError(f"Directory {args.extension_directory} does not exist")
    elif args.extension_directory is None:
        args.extension_directory = os.path.join(
            args.xml_template_directory, "..", "extensions"
        )
        print(
            f"No extension directory given, using default directory: {args.extension_directory}",
            file=sys.stderr,
        )

    if not os.path.exists(args.category_structure):
        raise ValueError(f"File {args.category_structure} does not exist")
    args.category_structure = yaml.safe_load(open(args.category_structure))

    if not os.path.exists(args.output) or not os.path.isdir(args.output):
        raise ValueError(
            f"Directory {args.output} does not exist or is not a directory"
        )

    return args


def _get_toolinfo_name(data: dict) -> str:
    module = data[FM_TOOLS_BENCHEXEC_TOOLINFO_MODULE]
    if module.startswith("benchexec.tools."):
        toolinfo_name = module[len("benchexec.tools.") :]
    elif module.startswith("http"):
        toolinfo_name = module.split("/")[-1]
    else:
        toolinfo_name = module
    if toolinfo_name.endswith(".py"):
        return toolinfo_name.split(".py")[0]
    return toolinfo_name


def _get_toolinfo_options(
    data: str | Path | dict, *, competition: str, track: str
) -> tuple[str, str]:
    """Returns the tool options as <option> XML elements in the first position of the tuple
    and the witness-validation-specific options as <option> XML elements in the second
    position of the tuple.

    The witness-validation-specific options use the placeholder '{WITNESS_FILE_PLACEHOLDER}'
    to indicate where the witness file is expected. This placeholder should be replaced
    by the actual witness files before writing it to the benchmark definition.
    """

    participation_info = get_participation_info(
        data, competition=competition, track=track
    )
    tool_version = participation_info[FM_TOOLS_PARTICIPATION_TOOL_VERSION]
    version_info = get_version_info(data, version=tool_version)
    options_as_sequence = version_info[FM_TOOLS_VERSION_BENCHEXEC_TOOLINFO_OPTIONS]
    witness_arguments = []
    while True:
        try:
            idx_witness_placeholder = options_as_sequence.index(
                WITNESS_PLACEHOLDER_TOOLINFO_OPTIONS
            )
        except ValueError:
            # no witness placeholder found, continue
            break
        witness_arguments.append(options_as_sequence[idx_witness_placeholder - 1])
        # remove the witness argument from the default options
        options_without_witness_args = []
        if idx_witness_placeholder > 1:
            options_without_witness_args.extend(
                options_as_sequence[: idx_witness_placeholder - 1]
            )
        if idx_witness_placeholder < len(options_as_sequence) - 1:
            options_without_witness_args.extend(
                options_as_sequence[idx_witness_placeholder + 1 :]
            )
        options_as_sequence = options_without_witness_args
    # The order of options must stay as in FM-tools data. We can not differentiate
    # between a positional argument and a command-line flag, so we need to preserve
    # the order of the options as given in the tool's fm-tools data.
    options_as_xml_sequence = [
        f'  <option name="{option}" />' for option in options_as_sequence
    ]
    witness_options_as_xml_sequence = [
        f'    <option name="{witness_argument}">{{{WITNESS_FILE_PLACEHOLDER}}}</option>'
        for witness_argument in witness_arguments
    ]
    return "\n".join(options_as_xml_sequence), "\n".join(
        witness_options_as_xml_sequence
    )


def _get_tool_xml_extension(tool_name: str, extension_dir: str) -> str:
    """
    Look in extension_dir for a file named {tool_name}.ext and return its contents.

    :return: The contents of the extension file, or an empty string if the file does not exist.
    """
    extension_file = os.path.join(extension_dir, f"{tool_name}.ext")
    if not os.path.exists(extension_file):
        return ""
    return open(extension_file).read()


def _get_xml_template(xml_template_dir: str, track: str, tool_language: str) -> str:
    """
    Return the XML template for a tool. Placeholders for the tool's data
    are written in the returned template as {placeholder_name}.

    :param xml_template_dir: The directory containing the XML templates.
    :param track: The track for which the XML template should be used (for example "Verification").
    :param tool_language: the target input language of the tool
    :return: The XML template for the tool.
    """
    if track == TRACK_SV_COMP_VERIFICATION_TRACK:
        tool_type = "verifier"
    elif track == TRACK_TEST_COMP_TEST_GENERATION_TRACK:
        tool_type = "tester"
    elif track == TRACK_SV_COMP_VALIDATION_VIOLATION_1:
        tool_type = "validate-violation-witnesses-1.0"
    elif track == TRACK_SV_COMP_VALIDATION_VIOLATION_2:
        tool_type = "validate-violation-witnesses-2.0"
    elif track == TRACK_SV_COMP_VALIDATION_CORRECTNESS_1:
        tool_type = "validate-correctness-witnesses-1.0"
    elif track == TRACK_SV_COMP_VALIDATION_CORRECTNESS_2:
        tool_type = "validate-correctness-witnesses-2.0"
    else:
        raise ValueError(f"Unhandled track: {track}")
    template_file = os.path.join(
        xml_template_dir, f"reference-{tool_type}-{tool_language}.xml"
    )
    return open(template_file).read()


class Category(NamedTuple):
    prop: str
    name: str


def get_category_name_as_in_xml(
    category_name_as_in_category_structure: str,
) -> Category:
    try:
        return Category(*category_name_as_in_category_structure.split("."))
    except (IndexError, TypeError):
        raise ValueError(
            f"Non-leaf category name: {category_name_as_in_category_structure}"
        )


def to_property_name(propertyfile: str) -> str:
    return propertyfile.split("/")[-1].split(".prp")[0]


def purge_categories(xml_str, tool_name, category_structure) -> str:
    categories_tool_participates_in = set()
    cs = category_structure
    for metaname, metacategory in cs["categories"].items():
        if (
            tool_name in metacategory["verifiers"]
            or tool_name in metacategory["validators"]
        ):
            subcategories = metacategory["categories"]
            try:
                category_names_as_in_xml = {
                    get_category_name_as_in_xml(category) for category in subcategories
                }
            except ValueError as e:
                if metaname not in ("Overall", "FalsificationOverall"):
                    print(
                        f"Ignoring {metaname} because of non-leaf subcategory. {e}",
                        file=sys.stderr,
                    )
            else:
                categories_tool_participates_in |= category_names_as_in_xml
    optins = cs["opt_in"].get(tool_name, [])
    category_names_as_in_xml = {
        get_category_name_as_in_xml(category) for category in optins
    }
    categories_tool_participates_in |= category_names_as_in_xml

    root = parse_xml_with_comments(xml_str)
    # Check whether there are any global <tasks> elements that are applied to all rundefinitions.
    global_taskdef_names = [taskdef.get("name") for taskdef in root.findall("tasks")]
    rundef_names = [rundef.get("name") for rundef in root.findall("rundefinition")]
    global_taskdef_uses = {
        rundef_name: list(global_taskdef_names) for rundef_name in rundef_names
    }

    # The below XML modification expects the following template xml structure:
    # <benchmark [...]>
    #   <rundefinition name="rundef1">
    #     <tasks name="task1">[...]</tasks>
    #     [...]
    #     <tasks name="taskn">[...]</tasks>
    #   </rundefinition>
    #   [...]
    #   <rundefinition name="rundefm">
    #   [...]
    for rundef in root.findall("rundefinition"):
        global_property = rundef.find("propertyfile")
        if global_property is not None:
            global_property_name = to_property_name(global_property.text)
        else:
            global_property_name = None
        tasks = rundef.findall("tasks")
        for taskdef in tasks:
            local_property = taskdef.find("propertyfile")
            if local_property is not None:
                local_property_name = to_property_name(local_property.text)
            else:
                local_property_name = None
            assert (
                global_property is None or local_property is None
            ), f"Either global or local property must be set, but not both: '{global_property_name}' and '{local_property_name}'"
            property_name = global_property_name or local_property_name
            current_category = Category(name=taskdef.get("name"), prop=property_name)
            if current_category not in categories_tool_participates_in:
                rundef.remove(taskdef)
        rundef_name = rundef.get("name")
        for taskdef_name in list(global_taskdef_uses[rundef_name]):
            current_category = Category(name=taskdef_name, prop=global_property_name)
            print(current_category)
            print(categories_tool_participates_in)
            if current_category not in categories_tool_participates_in:
                global_taskdef_uses[rundef_name].remove(taskdef_name)
        if len(global_taskdef_uses[rundef_name]) > 0:
            if len(global_taskdef_uses[rundef_name]) != len(global_taskdef_names):
                print(
                    f"WARNING: Category structure requires a fine-grained opt-out/opt-in that is not supported by this creation script. Keeping all sub-categories for tool {tool_name} in rundefinition {rundef_name}",
                    file=sys.stderr,
                )
        else:
            leftover_tasks = rundef.findall("tasks")
            if not leftover_tasks:
                root.remove(rundef)
    if root.find("rundefinition") is None:
        # no rundefinition left, do not write anything
        raise ValueError("No rundefinitions left in benchmark definition")
    new_xml = ET.tostring(root, encoding="unicode")
    return XML_DOCTYPE_DECLARATION + new_xml


def _get_normalized_tool_name(tool_name, track):
    if track == TRACK_SV_COMP_VALIDATION_VIOLATION_1:
        return f"{tool_name}-validate-violation-witnesses-1.0"
    elif track == TRACK_SV_COMP_VALIDATION_VIOLATION_2:
        return f"{tool_name}-validate-violation-witnesses-2.0"
    elif track == TRACK_SV_COMP_VALIDATION_CORRECTNESS_1:
        return f"{tool_name}-validate-correctness-witnesses-1.0"
    elif track == TRACK_SV_COMP_VALIDATION_CORRECTNESS_2:
        return f"{tool_name}-validate-correctness-witnesses-2.0"
    return tool_name


def _get_benchdef_name(tool_name):
    return tool_name


def _add_expected_verdicts(xml_str, track):
    if track in (
        TRACK_SV_COMP_VALIDATION_CORRECTNESS_1,
        TRACK_SV_COMP_VALIDATION_CORRECTNESS_2,
    ):
        expected_verdict = "true"
    elif track in (
        TRACK_SV_COMP_VALIDATION_VIOLATION_1,
        TRACK_SV_COMP_VALIDATION_VIOLATION_2,
    ):
        expected_verdict = "false"
    else:
        raise ValueError(f"Unhandled track: {track}")
    return xml_str.replace(
        "<propertyfile>", f'<propertyfile expectedverdict="{expected_verdict}">'
    )


def handle_tool_data(tool_name, data, cli_args, *, competition, track):
    display_name = data["name"]
    toolinfo_name = _get_toolinfo_name(data)
    tool_languages = [
        lang for lang in data[FM_TOOLS_INPUT_LANGUAGE] if lang in RELEVANT_LANGUAGES
    ]
    tool_name = _get_normalized_tool_name(tool_name, track)
    benchdef_name = _get_benchdef_name(tool_name)
    for tool_language in tool_languages:
        try:
            xml_template = _get_xml_template(
                cli_args.xml_template_directory,
                track=track,
                tool_language=tool_language,
            )
        except FileNotFoundError:
            continue
        else:
            benchexec_toolinfo_options, witness_options = _get_toolinfo_options(
                data, competition=competition, track=track
            )
            extension = _get_tool_xml_extension(
                benchdef_name, extension_dir=cli_args.extension_directory
            )
            if witness_options:
                # SV-COMP infrastructure requires an additional '../' for the witness file
                witness_file = "../" + re.search(
                    r"<requiredfiles>(.+)</requiredfiles>", xml_template
                ).group(1)
                witness_options_with_correct_file = witness_options.format(
                    **{WITNESS_FILE_PLACEHOLDER: witness_file}
                )
            else:
                witness_options_with_correct_file = ""
            # make sure that original placeholders of SV-COMP infrastructure (${placeholder})
            # are not replaced by our below call to .format
            xml_template = re.sub(r"\$\{([a-zA-z_]+)\}", r"${{\1}}", xml_template)
            xml_with_all_categories = xml_template.format(
                toolinfo_name=toolinfo_name,
                name=display_name,
                benchexec_toolinfo_options=benchexec_toolinfo_options,
                extension=extension,
                witness_options=witness_options_with_correct_file,
            )

            if tool_name.startswith("witnesslint"):
                xml_with_all_categories = _add_expected_verdicts(
                    xml_with_all_categories, track
                )

            try:
                xml_with_only_opt_ins = purge_categories(
                    xml_with_all_categories, tool_name, cli_args.category_structure
                )

                output_file = os.path.join(cli_args.output, f"{benchdef_name}.xml")
                with open(output_file, "w") as out:
                    out.write(xml_with_only_opt_ins)
            except ValueError as e:
                print(f"Skipping {tool_name} for language {tool_language} because: {e}")


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    cli_args = parse_cli(argv)
    data = cli_args.fm_data

    for name, single_tool in data.items():
        handle_tool_data(
            name,
            single_tool,
            cli_args,
            competition=cli_args.competition,
            track=cli_args.track,
        )


if __name__ == "__main__":
    sys.exit(main())
