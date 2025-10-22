import argparse
import contextlib
from pathlib import Path
from tempfile import NamedTemporaryFile

import check_all_with_service
import yaml
from check_archives_with_service import check_tool, participates_in_svcomp

ACTOR_LOC = Path(__file__).parent.parent / "data"


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        "check_my_tool.py", description="Check a tool for SV-COMP 24"
    )

    tools = [tool.name for tool in ACTOR_LOC.glob("*.yml")]

    parser.add_argument(
        "tool",
        help="The tool to check",
        action="store",
        choices=tools,
        metavar=f"TOOL.yml ∈ ./{ACTOR_LOC.relative_to(Path.cwd())}",
    )
    arggroup = parser.add_mutually_exclusive_group()

    arggroup.add_argument(
        "--but-download-from",
        action="store",
        dest="download_from",
        help="Download the tool from this URL (not DOI!) "
        "instead of the one in the tool YAML",
        default=None,
    )

    return parser


def main(args):
    opts = make_parser().parse_args(args)

    if opts.download_from is None:
        print(f"Checking {opts.tool}")
        check_all_with_service.main([opts.tool])
        return

    print(f"Downloading {opts.tool} from {opts.download_from}")

    tool = ACTOR_LOC / opts.tool

    if (version := participates_in_svcomp(tool)) is None:
        print(
            f"{opts.tool} does not participate in SV-COMP 24!"
            "\nI'm is not sure which version to replace the download link in."
        )

    with tool.open("r") as f:
        actor_def = yaml.safe_load(f)

    try:
        tool_version = [
            v for v in actor_def.get("versions", []) if v["version"] == version
        ].pop()
    except IndexError:
        print(f"{opts.tool} does not have a version {version}!")
        return

    tool_version["url"] = opts.download_from

    with contextlib.suppress(KeyError):
        del tool_version["doi"]

    with NamedTemporaryFile("w") as f:
        yaml.safe_dump(actor_def, f)
        f.flush()
        check_tool(tool.stem, Path(f.name), version, is_svcomp=True)


if __name__ == "__main__":
    import sys

    main(sys.argv[1:])
