#! /usr/bin/python3

import sys

if sys.version_info < (3,):
    sys.exit("benchexec.test_tool_info needs Python 3 to run.")

import argparse
import logging
import os
import re
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime
from enum import Enum
from pathlib import Path
from subprocess import call
from types import SimpleNamespace
from urllib.request import HTTPError, Request, urlopen

import _ciutil as util
import benchexec
import httpx
from benchexec import model
from benchexec.tools.template import BaseTool2

sys.dont_write_bytecode = True  # prevent creation of .pyc files

SUCCESS = 0
ERROR = 1


class ZIPFileCode(Enum):
    # define some constants for zipfiles,
    # needed to get the interesting bits from zipped objects, for further details take a look at
    # https://unix.stackexchange.com/questions/14705/the-zip-formats-external-file-attribute/14727#14727
    S_IFIFO = 0o010000  # named pipe (fifo)
    S_IFCHR = 0o020000  # character special
    S_IFDIR = 0o040000  # directory
    S_IFBLK = 0o060000  # block special
    S_IFREG = 0o100000  # regular
    S_IFLNK = 0o120000  # symbolic link
    S_IFSOCK = 0o140000  # socket


def is_flag_set(attr, flag: ZIPFileCode):
    """returns whether a flag is set or not"""
    return (attr & (flag << 16)) == (flag << 16)


def get_attributes(info_object):
    return {
        "named pipe": is_flag_set(info_object.external_attr, ZIPFileCode.S_IFIFO.value),
        "special char": is_flag_set(
            info_object.external_attr, ZIPFileCode.S_IFCHR.value
        ),
        "directory": is_flag_set(info_object.external_attr, ZIPFileCode.S_IFDIR.value),
        "block special": is_flag_set(
            info_object.external_attr, ZIPFileCode.S_IFBLK.value
        ),
        "regular": is_flag_set(info_object.external_attr, ZIPFileCode.S_IFREG.value),
        "symbolic link": is_flag_set(
            info_object.external_attr, ZIPFileCode.S_IFLNK.value
        ),
        "socket": is_flag_set(info_object.external_attr, ZIPFileCode.S_IFSOCK.value),
    }


def error(arg, cause=None, label="    ERROR", exit_on_first_error=False):
    util.error(arg, cause, label)
    if exit_on_first_error:
        sys.exit(1)


def info(msg, label="INFO"):
    util.info(msg, label)


def _contains_file_in_root(root_directory: str, name_list: list, check_against: str):
    for file_root in name_list:
        file_path = os.path.join(root_directory, check_against)
        # check if there is a file rootDirectory/check_against. Second check ensures that it is a file (only one /)
        if (
            file_root.lower().startswith(file_path.lower())
            and file_root.count("/") == 1
        ):
            return True

    return False


def check_zipfile(
    tool, archives_root: Path, competition_track, exit_on_first_error=False
):
    zip_filename = (
        archives_root / f"{tool}-{util.get_track_for_filename(competition_track)}.zip"
    )

    if not os.path.isfile(zip_filename):
        error(f"File '{zip_filename}' does not exist.", exit_on_first_error=True)
    try:
        zip_content = zipfile.ZipFile(zip_filename)
    except zipfile.BadZipfile as e:
        error(
            f"zipfile is invalid: {zip_filename}",
            cause=e,
            exit_on_first_error=exit_on_first_error,
        )
        return ERROR
    namelist = zip_content.namelist()
    if not namelist:
        error(
            f"zipfile is empty: {zip_filename}", exit_on_first_error=exit_on_first_error
        )
        return ERROR

    # check whether there is a single root directory for all files.
    root_directory = namelist[0].split("/")[0] + "/"
    status = SUCCESS
    for name in namelist:
        if not name.startswith(root_directory):
            error(
                "file '{}' is not located under a common root directory".format(name),
                exit_on_first_error=exit_on_first_error,
            )
            status = ERROR

    # check if root directory contains readme
    if not _contains_file_in_root(root_directory, namelist, "readme"):
        error(
            f"no readme found in root directory: {root_directory}",
            exit_on_first_error=exit_on_first_error,
        )
        status = ERROR

    # check if root directory contains license
    if not _contains_file_in_root(
        root_directory, namelist, "license"
    ) and not _contains_file_in_root(root_directory, namelist, "license"):
        error(
            f"no license found in root directory: {root_directory}",
            exit_on_first_error=exit_on_first_error,
        )
        status = ERROR

    # check whether there are unwanted files
    pattern = re.compile(
        r".*(\/\.git\/|\/\.svn\/|\/\.hg\/|\/CVS\/|\/__MACOSX|\/\.aptrelease).*"
    )
    for name in namelist:
        if pattern.match(name):
            error(
                "file '{}' should not be part of the zipfile".format(name),
                exit_on_first_error=exit_on_first_error,
            )
            status = ERROR

    # check whether all symlinks point to valid targets
    directories = set(os.path.dirname(f) for f in namelist)
    for info_object in zip_content.infolist():
        attr = get_attributes(info_object)
        if attr["symbolic link"]:
            relativTarget = bytes.decode(zip_content.open(info_object).read())
            target = os.path.normpath(
                os.path.join(os.path.dirname(info_object.filename), relativTarget)
            )
            if target not in directories and target not in namelist:
                error(
                    "symbolic link '{}' points to invalid target '{}'".format(
                        info_object.filename, target
                    ),
                    exit_on_first_error=exit_on_first_error,
                )
                status = ERROR

    return status, root_directory


# Adopted from commit https://gitlab.com/sosy-lab/benchmarking/fm-tools/-/commit/0dac651b8278d3de33b6aeb2b4d00486ba8bb072 from FM-Tools repository.
def _find_correct_URL(competition_name: str, year: int, branch: str = None):
    if branch is not None:
        return f"https://gitlab.com/sosy-lab/{competition_name}/bench-defs/-/raw/{branch}/benchmark-defs"
    competition_name = competition_name.lower()
    project_id = {"test-comp": 9359396, "sv-comp": 22074720}[competition_name]
    tags_url = f"https://gitlab.com/api/v4/projects/{project_id}/repository/tags"
    response = httpx.get(tags_url)
    response.raise_for_status()
    # We assume that every tag starts with either svcompYY or testcompYY.
    tag_search_string = competition_name.replace("-", "") + str(year)[-2:]
    tags = [tag for tag in response.json() if tag_search_string in tag["name"]]
    most_recent_tag = "main"
    if len(tags) > 0:
        most_recent_tag = max(
            tags,
            key=lambda tag: datetime.fromisoformat(
                tag["created_at"].replace("Z", "+00:00")
            ),
        )["name"]
    return f"https://gitlab.com/sosy-lab/{competition_name}/bench-defs/-/raw/{most_recent_tag}/benchmark-defs"


def check_benchmark_file(tool: str, competition: str, competition_track: str):
    # check that a benchmark definition exists for this tool in the official repository
    competition_name = competition.split(" ")[0]
    competition_year = competition.split(" ")[1]
    benchmark_def_name = (
        str(util.get_benchmark_filename(tool, competition_track)) + ".xml"
    )
    benchmark_url = (
        _find_correct_URL(competition_name, competition_year) + "/" + benchmark_def_name
    )
    request = Request(benchmark_url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        response = urlopen(request)
    except HTTPError:
        benchmark_url = (
            _find_correct_URL(competition_name, competition_year, "dev")
            + "/"
            + benchmark_def_name
        )
        request = Request(benchmark_url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            response = urlopen(request)
        except HTTPError:
            error(
                f"File {benchmark_url} not available. Please rename the archive to match an existing benchmark definition, or add a new benchmark definition at 'https://gitlab.com/sosy-lab/{competition_name.lower()}/bench-defs'."
            )
            return ERROR, ""
    content = response.read()
    benchmark_definition = ET.fromstring(content)
    # Test access of something in XML structure
    tool_name = benchmark_definition.get("tool")
    return SUCCESS, tool_name


def check_tool_info_module(
    tool: str,
    competition_track: str,
    archives_root: Path,
    root_directory: Path,
    tool_name: str,
    config: str,
):
    zip_filename = (
        archives_root / f"{tool}-{util.get_track_for_filename(competition_track)}.zip"
    )
    with tempfile.TemporaryDirectory(prefix="comp_check_") as tmp_dir:
        # lets use the real unzip, because Python may not handle symlinks
        call(["unzip", "-q", "-d", tmp_dir, zip_filename])

        tool_dir = os.path.join(tmp_dir, root_directory)
        try:
            os.chdir(tool_dir)
            return _check_tool_info_module(tool_name, config)
        finally:
            os.chdir(os.environ["PWD"])


def _check_tool_info_module(tool_name, config):
    status = SUCCESS
    try:
        # nice colorful dump, but we would need to parse it
        # from benchexec import test_tool_info
        # test_tool_info.print_tool_info(toolname)

        _, tool = model.load_tool_info(tool_name, config)
    except (Exception, SystemExit) as e:
        error(f"loading tool-info for {tool_name} failed", cause=e)
        return ERROR

    try:
        # import inspect
        # if not inspect.getdoc(tool):
        #     error("tool %s has no documentation" % toolname)
        exe = tool.executable(BaseTool2.ToolLocator(use_path=True, use_current=True))
        if not exe:
            error("tool '%s' has no executable" % tool_name)
            status = ERROR
        if not os.path.isfile(exe) or not os.access(exe, os.X_OK):
            error("tool '%s' with file %s is not executable" % (tool_name, exe))
            status = ERROR
        if exe:
            status |= _checks_on_executable(tool, exe, tool_name)
    except Exception as e:
        error(f"querying tool executable failed for {tool_name}", cause=e)
        status = ERROR

    return status


def _checks_on_executable(tool, exe, toolname):
    status = SUCCESS
    try:
        reported_name = tool.name()
        if not reported_name:
            error("tool '%s' has no name" % toolname)
            status = ERROR
    except Exception as e:
        error(f"querying tool-name failed for {toolname}", cause=e)
        status = ERROR
        reported_name = ""
    if not reported_name:
        reported_name = ""

    try:
        version = tool.version(exe)
        if not version:
            error("tool '%s' has no version number" % toolname)
            status = ERROR
        if "\n" in version:
            error(
                "tool '%s' has an invalid version number (newline in version)"
                % toolname
            )
            status = ERROR
        if len(version) > 100:  # long versions look ugly in tables
            error("tool '%s' has a very long version number" % toolname)
            status = ERROR
        if version.startswith(reported_name):
            error(
                "tool '%s' is part of its own version number '%s'" % (toolname, version)
            )
            status = ERROR
    except Exception as e:
        error(f"querying tool version failed for {toolname}", cause=e)
        status = ERROR
        version = ""
    if not version:
        version = ""

    try:
        list(tool.program_files(exe))
    except Exception as e:
        error(f"querying program files failed for {toolname}", cause=e)
        status = ERROR

    label, displayed_name = "     --> ", reported_name + " " + version
    if exe and version:
        info(displayed_name, label=label)
    else:
        error(displayed_name, label=label)
        status = ERROR
    return status


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Check archive for a given competition."
    )
    parser.add_argument(
        "--exit-on-first-error",
        action="store_true",
        default=False,
        help="Exit on first error.",
    )
    parser.add_argument(
        "--competition",
        type=str,
        help="Competition name and year",
    )
    parser.add_argument(
        "--archives-root",
        type=Path,
        help="Path to archives directory",
    )
    parser.add_argument(
        "--competition-track",
        type=str,
        help="Competition track",
    )
    parser.add_argument("tool", type=Path, help="Tool name")
    return parser.parse_args()


def check_archive(
    tool, competition: str, competition_track, archives: Path, exit_on_first_error=False
):
    # dummy config. this script is meant to be executed by the CI,
    # so no need to run it in an extra container:
    config = SimpleNamespace()
    config.container = False
    file_status, root_directory = check_zipfile(
        tool, archives, competition_track, exit_on_first_error
    )
    def_status, tool_name = check_benchmark_file(tool, competition, competition_track)
    module_status = check_tool_info_module(
        tool, competition_track, archives, root_directory, tool_name, config
    )
    return file_status | def_status | module_status


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format=None)
    args = parse_arguments()
    logging.info(
        f"This script checks the archive for tool '{args.tool}' for '{args.competition}' and '{args.competition_track}' with\n\tPython {sys.version}\n\tand BenchExec {benchexec.__version__}"
    )
    sys.exit(
        check_archive(
            args.tool,
            args.competition,
            args.competition_track,
            args.archives_root,
            args.exit_on_first_error,
        )
    )
