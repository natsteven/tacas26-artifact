#!/bin/python3


from dataclasses import dataclass
from functools import cache
import io
import json
import os
from pathlib import Path
import re
import subprocess
from typing import IO, Any, Dict, Final, Iterable, List, Optional, Union, overload
import xml.etree.ElementTree as et
from zipfile import ZipFile, ZipInfo
import yaml
import sys

import logging
import requests

TOOL_TYPE = os.getenv("TOOL_TYPE", "verifier")

BENCHDEF_TEMPLATE = os.getenv(
    "BENCHDEF_TEMPLATE",
    "https://gitlab.com/sosy-lab/sv-comp/bench-defs/-"
    "/raw/main/benchmark-defs/{tool}.xml",
)

BRANCH_TEMPLATE = os.getenv(
    "BRANCH_TEMPLATE",
    "https://gitlab.com/sosy-lab/sv-comp/archives-2023/-/raw/{branch}/2023/{tool}.zip",
)
URL = "https://coveriteam-service.sosy-lab.org/execute"


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


logging.basicConfig(format="[%(levelname)s] %(message)s", level=logging.INFO)
StrPath = Union[str, Path]
FileRead = Union[io.BytesIO, StrPath]


@dataclass
class ActorDef:
    name: str
    tool_info: str
    options: List[str]
    is_java: bool


@dataclass
class Options:
    program: Path
    specification: Path
    cvt_file: Path


def get_diff() -> Iterable[str]:
    ret = subprocess.run(
        [
            "git",
            "diff",
            "--name-only",
            "--diff-filter=d",
            "origin/main...",
            "--",
            "./2023/*.zip",
        ],
        stdout=subprocess.PIPE,
    )

    output = ret.stdout.decode(errors="ignore")
    logging.info("Git diff: %s", output)

    return set((Path(path).stem for path in output.splitlines()))


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


def download_benchdef_xml(tool: str) -> io.BytesIO:
    link = BENCHDEF_TEMPLATE.format(tool=tool)
    resp = requests.get(link)
    return io.BytesIO(resp.content)


def get_link(branch: str, tool: str) -> str:
    return BRANCH_TEMPLATE.format(branch=branch, tool=tool)


def is_validator(tool: str):
    return tool.startswith("val_")


def parse_benchdef_options(benchdef: FileRead, tool_name: str) -> ActorDef:
    root = et.parse(benchdef).getroot()

    is_java = any(
        (
            d.get("name").endswith("_java")  # type: ignore
            for d in root.findall("rundefinition")
            if d is not None
        )
    )

    options: List[str] = []
    for option in root.findall("option"):
        name = option.get("name")
        if name is None:
            raise RuntimeError(f"'name' tag missing for an option in xml {benchdef}")
        options.append(name)
        if option.text:
            options.append(option.text)

    tool_info = root.get("tool")
    if tool_info is None:
        raise RuntimeError(f"'tool' tag missing for benchmark xml {benchdef}")

    return ActorDef(tool_name, tool_info, options, is_java)


@overload
def assemble_actor_yml(branch: str, definition: ActorDef, to_file: None) -> None: ...


@overload
def assemble_actor_yml(
    branch: str, definition: ActorDef, to_file: IO[bytes] = ...
) -> "yaml._Yaml": ...


def assemble_actor_yml(
    branch: str, definition: ActorDef, to_file: Optional[IO[bytes]] = None
):
    # Remote location of the tool
    loc = get_link(branch=branch, tool=definition.name)

    raw = {
        "resourcelimits": {
            "memlimit": "8 GB",
            "timelimit": "2 min",
            "cpuCores": "2",
        },
        "actor_name": definition.name,
        "toolinfo_module": definition.tool_info,
        "archives": [
            {"version": "svcomp23", "location": loc, "options": definition.options}
        ],
        "format_version": "1.2",
    }

    if to_file is not None:
        yaml.dump(raw, to_file)
        return

    return yaml.dump(raw)


def get_options(tool: str, is_java: bool) -> Options:
    default_program = PROGRAM_C
    default_spec = SPECIFICATION_C
    default_cvt = VERIFIER_CVT

    if is_java:
        if TOOL_TYPE == "tester":
            raise RuntimeError("Java Testers are not supported at this moment")

        default_program = PROGRAM_JAVA
        default_spec = SPECIFICATION_JAVA

    if TOOL_TYPE == "tester":
        default_program = PROGRAM_TESTER
        default_spec = SPECIFICATION_TESTER
        default_cvt = TESTER_CVT

    opts = load_options().get(tool, dict())

    prog = as_path(opts.get("program"), default_program)
    spec = as_path(opts.get("specification"), default_spec)
    cvtf = as_path(opts.get("cvt_file"), default_cvt)

    return Options(program=prog, specification=spec, cvt_file=cvtf)


def prepare_file_dict(actor_yml: str, options: Options, is_java: bool):
    program = options.program.name
    spec = options.specification.name

    if is_java:
        prog_path = program + "/Main.java"
        return {
            options.cvt_file.name: options.cvt_file.open("rb"),
            spec: options.specification.open("rb"),
            "actor.yml": ("actor.yml", actor_yml),
            prog_path: (options.program / "Main.java").open("rb"),
            "common/org/sosy_lab/sv_benchmarks/Verifier.java": COMMON_JAVA.open("rb"),
        }

    return {
        options.cvt_file.name: options.cvt_file.open("rb"),
        spec: options.specification.open("rb"),
        "actor.yml": ("actor.yml", actor_yml),
        program: options.program.open("rb"),
    }


def prepare_args(options: Options, is_java: bool):
    args: dict[str, Any] = {
        "coveriteam_inputs": {
            "tool_path": "actor.yml",
            "specification_path": options.specification.name,
            "tool_version": "svcomp23",
            "data_model": "ILP32",
        },
        "cvt_program": options.cvt_file.name,
        "working_directory": "coveriteam",
    }

    if is_java:
        args["coveriteam_inputs"]["program_path"] = [options.program.name, "common"]
    else:
        args["coveriteam_inputs"]["program_path"] = options.program.name

    return args


def make_request(args: Dict[str, Any], files):
    jargs = json.dumps(args)

    return requests.post(url=URL, data={"args": jargs}, files=files)


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


def check_tool(tool: str, branch: str):
    if "license" in tool or "LICENSE" in tool:
        logging.info(f"Skipping the check for {tool} as it looks like a license file.")
        return

    benchdef = download_benchdef_xml(tool=tool)

    actor_def = parse_benchdef_options(benchdef, tool)
    logging.info("Extracted actor def: %s", actor_def)

    yml = assemble_actor_yml(branch, actor_def)
    logging.info("Created yaml:\n%s", yml)

    options = get_options(tool, actor_def.is_java)
    files = prepare_file_dict(yml, options, actor_def.is_java)
    args = prepare_args(options, actor_def.is_java)

    logging.info("Calling coveriteam-service...")
    ret = make_request(args, files)

    if ret.status_code != 200:
        try:
            message = ret.json()["message"]
            logging.error(message)
        except (KeyError, json.JSONDecodeError):
            lines = "\n".join(ret.iter_lines())
            logging.error("There was an error:\n%s", lines)

        archive = Path(f"output-{tool}.zip")
        add_call_data(archive, args, files)
        logging.info(
            "All files used to test the tool "
            "and produce the error  can be found in output-%s.zip",
            tool,
        )
        sys.exit(1)

    result, archive = handle_response(tool, ret)

    add_call_data(archive, args, files)
    logging.info(
        "All files used to test the tool "
        "as well as the results can be found in output-%s.zip",
        tool,
    )
    if TOOL_TYPE == "verifier":
        if result.startswith("true") or result.startswith("false"):
            logging.info("SUCCESS")
            logging.info("Result was: %s", result)
        else:
            logging.error("result was not 'true' or 'false': %s", result)
            sys.exit(1)

    if TOOL_TYPE == "tester":
        if result.startswith("cvt-output/"):
            logging.info("SUCCESS")
            logging.info("Result was: %s", result)
        else:
            logging.error("No test suite was produced.")
            sys.exit(1)


def main():
    logging.info("Running...")
    branch = os.getenv("CI_MERGE_REQUEST_SOURCE_BRANCH_NAME", "main")
    tools_to_exclude = os.getenv("EXCLUDE_FROM_COVERITEAM_SERVICE_CHECK", "").split(" ")

    for tool in get_diff():
        if tool in tools_to_exclude:
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

        check_tool(tool, branch)


if __name__ == "__main__":
    main()
