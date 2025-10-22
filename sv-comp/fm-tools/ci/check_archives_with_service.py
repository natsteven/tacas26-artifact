#!/bin/python3


import io
import json
import logging
import os
import re
import subprocess  # noqa S404
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any, Dict, Final, Iterable, Union
from zipfile import ZipFile, ZipInfo

import requests
import yaml

TOOL_TYPE = os.getenv("TOOL_TYPE", "verifier")

URL = "https://coveriteam-service.sosy-lab.org/execute"

CURRENT_SVCOMP = "SV-COMP 2025"
SCRIPT = Path(__file__).parent

OPTION_MAP = SCRIPT / Path(f"test-data/{TOOL_TYPE}_mapping.json")

VERIFIER_CVT: Final[Path] = SCRIPT / Path("test-data/verifier.cvt")
TESTER_CVT: Final[Path] = SCRIPT / Path("test-data/tester.cvt")

SPECIFICATION_JAVA: Final[Path] = SCRIPT / Path("test-data/assert_java.prp")
SPECIFICATION_C: Final[Path] = SCRIPT / Path("test-data/unreach-call.prp")
SPECIFICATION_TESTER: Final[Path] = SCRIPT / Path("test-data/coverage-error-call.prp")

PROGRAM_C: Final[Path] = SCRIPT / Path("test-data/program.c")
PROGRAM_JAVA: Final[Path] = SCRIPT / Path("test-data/Program")
COMMON_JAVA: Final[Path] = SCRIPT / Path("test-data/Verifier.java")
PROGRAM_TESTER: Final[Path] = SCRIPT / Path("test-data/program_tester.i")

SUPPORTED_TRACKS = frozenset(
    [
        "Verification",
    ]
)


logging.basicConfig(format="[%(levelname)s] %(message)s", level=logging.INFO)
StrPath = Union[str, Path]
FileRead = Union[io.BytesIO, StrPath]


@dataclass
class Options:
    program: Path
    specification: Path
    cvt_file: Path
    is_java: bool


def get_diff() -> Iterable[str]:
    ret = subprocess.run(  # noqa B603 B602
        [
            "git",
            "diff",
            "--name-only",
            "--diff-filter=d",
            "origin/main...",
            "--",
            "./data/*.yml",
        ],
        stdout=subprocess.PIPE,
    )

    output = ret.stdout.decode(errors="ignore")
    output = [path for path in output.splitlines() if "schema.yml" not in path]
    logging.info("Git diff: %s", ", ".join(output))

    return (Path(path) for path in output)


def as_path(value: str | None, default: Path) -> Path:
    if value is None:
        return default

    relative_to = OPTION_MAP.parent

    resource = relative_to / value

    if resource.exists():
        return resource
    logging.info("%s does not exist. Falling back to default %s", resource, default)
    return default


@cache
def load_options() -> dict[str, dict[str, str]]:
    with OPTION_MAP.open("rb") as fd:
        return json.load(fd)


def is_validator(tool: Path):
    return tool.stem.startswith("val_")


def is_java(tool: Path) -> bool:
    with tool.open("r") as f:
        opt = yaml.safe_load(f)
        languages = opt.get("input_languages", [])
        if len(languages) > 1:
            raise RuntimeError(
                "Tool uses more than one language!\n"
                "Please specify the language to be used in "
                "ci/test-data/verifier-mapping.json\n"
                " as 'language': 'java' or 'language': 'c'"
            )

        lang = languages[0]
        return lang.strip().lower() == "java"


def participates_in_svcomp(tool: Path) -> str | None:
    with tool.open("r") as f:
        tool_config = yaml.safe_load(f)

    for comp in tool_config.get("competition_participations", []):
        current_svcomp = comp.get("competition", "") == CURRENT_SVCOMP
        logging.info("Checking competition: %s", comp.get("competition", ""))
        if not current_svcomp:
            logging.info("Not current SV-COMP, skipping...")
            continue

        track = comp.get("track", "")
        logging.info("Checking track %s", track)
        if track not in SUPPORTED_TRACKS:
            logging.info("Track currently not supported: %s", track)
            continue

        return comp.get("tool_version", None)

    return None


def get_options(tool_name, tool: Path) -> Options:
    default_program = PROGRAM_C
    default_spec = SPECIFICATION_C
    default_cvt = VERIFIER_CVT

    opts = load_options().get(tool_name, {})

    lang = opts.get("language", None)
    tool_is_java = False
    tool_is_java = is_java(tool) if lang is None else lang.strip().lower() == "java"

    if tool_is_java:
        print("Java tool detected")
        if TOOL_TYPE == "tester":
            raise RuntimeError("Java Testers are not supported at this moment")

        default_program = PROGRAM_JAVA
        default_spec = SPECIFICATION_JAVA

    if TOOL_TYPE == "tester":
        default_program = PROGRAM_TESTER
        default_spec = SPECIFICATION_TESTER
        default_cvt = TESTER_CVT

    prog = as_path(opts.get("program"), default_program)
    spec = as_path(opts.get("specification"), default_spec)
    cvtf = as_path(opts.get("cvt_file"), default_cvt)

    return Options(
        program=prog, specification=spec, cvt_file=cvtf, is_java=tool_is_java
    )


def prepare_file_dict(tool: Path, options: Options):
    program = options.program.name
    spec = options.specification.name

    if options.is_java:
        prog_path = program + "/Main.java"
        return {
            options.cvt_file.name: options.cvt_file.open("rb"),
            spec: options.specification.open("rb"),
            "actor.yml": tool.open("rb"),
            prog_path: (options.program / "Main.java").open("rb"),
            "common/org/sosy_lab/sv_benchmarks/Verifier.java": COMMON_JAVA.open("rb"),
        }

    return {
        options.cvt_file.name: options.cvt_file.open("rb"),
        spec: options.specification.open("rb"),
        "actor.yml": tool.open("rb"),
        program: options.program.open("rb"),
    }


def prepare_args(options: Options, version: str):
    args: dict[str, Any] = {
        "coveriteam_inputs": {
            "tool_path": "actor.yml",
            "specification_path": options.specification.name,
            "tool_version": version,
            "data_model": "ILP32",
        },
        "cvt_program": options.cvt_file.name,
        "working_directory": "coveriteam",
    }

    if options.is_java:
        args["coveriteam_inputs"]["program_path"] = [options.program.name, "common"]
    else:
        args["coveriteam_inputs"]["program_path"] = options.program.name

    return args


def make_request(args: Dict[str, Any], files):
    jargs = json.dumps(args)

    return requests.post(url=URL, data={"args": jargs}, files=files, timeout=240)


def determine_result(run):
    """
    It assumes that any verifier or validator implemented in CoVeriTeam
    will print out the produced aftifacts.
    If more than one dict is printed, the first matching one.
    """
    verdict = None
    verdict_regex = re.compile(r"'verdict': '([a-zA-Z\(\)\ \-]*)'")
    if TOOL_TYPE == "tester":
        verdict_regex = re.compile(r"'test_suite': '([a-zA-Z0-9_.\(\)\ \-/]*)'")

    for line in reversed(run):
        line = line.strip()
        verdict_match = verdict_regex.search(line)
        if verdict_match and verdict is None:
            # CoVeriTeam outputs benchexec result categories as verdicts.
            verdict = verdict_match.group(1)
        if "Traceback (most recent call last)" in line:
            verdict = "EXCEPTION"
    if verdict is None:
        return "UNKNOWN"
    return verdict


def handle_response(tool: str, response: requests.Response):
    output_path = Path(f"output-{tool}.zip")
    with output_path.open("w+b") as fd:
        fd.write(response.content)
        fd.flush()
        fd.seek(0)
        with ZipFile(fd, "r") as zipf, zipf.open("LOG") as log:
            cvt_log = log.read().decode(errors="ignore")
            logging.info(
                "------------------------------------------------------------------\n"
                "The following log was produced by the execution of the CoVeriTeam "
                "program on the server: %s\n"
                "--------------------------------------------------------------"
                "-----------\nEND OF THE LOG FROM REMOTE EXECUTION",
                cvt_log,
            )
            return determine_result(cvt_log.splitlines()), output_path


def prepare_curl_command(args: Dict[str, Any], files: Iterable[str]):
    base = "#!/bin/sh\n\n"
    base += "curl -X POST -H 'ContentType: multipart/form-data' -k \\\n"
    base += "https://coveriteam-service.sosy-lab.org/execute \\\n"
    base += "\t--form args='{}'\\\n".format(json.dumps(args))
    base += "\t--output cvt_remote_output.zip"
    for file in files:
        base += f"\t--form '{file}'=@{file}\\\n"

    return base


def add_call_data(archive: StrPath, args: Dict[str, Any], files: Dict[str, Any]):
    with ZipFile(archive, "a") as zipf:
        for key, fd in files.items():
            try:
                fd.seek(0)
                zipf.writestr(f"data/{key}", fd.read())
            except AttributeError:
                zipf.writestr(f"data/{key}", fd[1])

        curl = prepare_curl_command(args, files)

        info = ZipInfo("data/send_request.sh")
        # make executable
        info.external_attr |= 0o755 << 16
        zipf.writestr(info, curl)


def check_tool(tool_name: str, tool: Path, version: str, is_svcomp: bool):
    if "license" in tool_name or "LICENSE" in tool_name:
        logging.info(f"Skipping the check for {tool} as it looks like a license file.")
        return

    options = get_options(tool_name, tool)
    files = prepare_file_dict(tool, options)
    args = prepare_args(options, version)

    logging.info("Calling coveriteam-service...")
    ret = make_request(args, files)

    if ret.status_code != 200:
        try:
            message = ret.json()["message"]
            logging.error(message)
        except (KeyError, json.JSONDecodeError):
            lines = "\n".join(ret.iter_lines())
            logging.error("There was an error:\n%s", lines)

        archive = Path(f"output-{tool_name}.zip")
        add_call_data(archive, args, files)
        logging.info(
            "All files used to test the tool "
            "and produce the error can be found in %s",
            archive,
        )
        raise RuntimeError("Tool did not pass test")

    result, archive = handle_response(tool_name, ret)

    add_call_data(archive, args, files)
    logging.info(
        "All files used to test the tool as well as the results can be found in %s",
        archive,
    )
    if TOOL_TYPE == "verifier":
        if (
            options.specification.name == "no-data-race.prp"
            and result.lower().startswith("verdict")
        ):
            logging.info("SUCCESS")
            logging.info("Result was: %s", result)

        if result.startswith("true") or result.startswith("false"):
            logging.info("SUCCESS")
            logging.info("Result was: %s", result)
        else:
            logging.error("result was not 'true' or 'false': %s", result)
            raise RuntimeError("Tool did not pass!")

    if TOOL_TYPE == "tester":
        if result.startswith("cvt-output/"):
            logging.info("SUCCESS")
            logging.info("Result was: %s", result)
        else:
            logging.error("No test suite was produced.")
            raise RuntimeError("Tool did not pass!")


def main():
    logging.info("Running...")
    tools_to_exclude = os.getenv("EXCLUDE_FROM_COVERITEAM_SERVICE_CHECK", "").split(" ")

    for tool in get_diff():
        if tool.stem in tools_to_exclude:
            logging.info(
                "%s is excluded from the CoVeriTeam Service check",
                tool,
            )
            continue
        if is_validator(tool):
            logging.info(
                "A CoVeriTeam Service check for validators is not"
                " supported at this moment. Skipping %s ...",
                tool,
            )
            continue

        if (version := participates_in_svcomp(tool)) is not None:
            check_tool(tool.stem, tool, version, True)


if __name__ == "__main__":
    main()
