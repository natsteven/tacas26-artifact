#! /usr/bin/python3

# TODO: Adopt for changes in https://gitlab.com/sosy-lab/benchmarking/competition-scripts/-/merge_requests/153

import argparse
import yaml
import multiprocessing
from pathlib import Path
import sys
import os
from update_archives import update_archives

sys.path.append(str(Path(__file__).parent.parent.resolve() / "test"))
from check_archive import check_archive


def process_tool(
    fm_tools: Path,
    archives: Path,
    competition_name: str,
    competition_track: str,
    tool_name: str,
):
    try:
        print(f"Downloading archive for '{tool_name}' ...", file=sys.stderr)
        update_archives(
            fm_tools, [tool_name], archives, competition_name, competition_track
        )
    except AssertionError:
        # legacy from shell script, output needs to match
        print(f"Archive download for '{tool_name}' failed.", file=sys.stderr)
        return
    print(f"Checking archive for '{tool_name}' ...", file=sys.stderr)
    status = check_archive(
        tool_name,
        competition_name[: -len(" 2024")],
        competition_track,
        archives,
    )
    if status == 0:
        print(f"Checked and usable tool: '{tool_name}'.", file=sys.stderr)
        print(tool_name)
    else:
        print(f"Archive check for '{tool_name}' failed.", file=sys.stderr)


def wrap_process_tool(parameters):
    return process_tool(*parameters)


def list_tools(competition_name: str, competition_track: str, tools: list):
    for tool in tools:
        tool_name = tool.name[:-4]
        if tool.name == "schema.yml":
            continue
        data = yaml.safe_load(tool.open())
        tool_version = None
        doi = None
        # look for competition and track in competition_participations extract tool_version
        for competition in data["competition_participations"]:
            if (
                competition["competition"] == competition_name
                and competition["track"] == competition_track
            ):
                for version in data["versions"]:
                    if version["version"] == competition["tool_version"]:
                        tool_version = version["version"]
                        if "doi" in version:
                            doi = version["doi"]
                        break
                break
        if tool_version is None or tool_version == "null":
            # print(
            #    f"There is no version of the tool '{tool_name}' participating in '{competition_name}', track '{competition_track}'.",
            #    file=sys.stderr,
            # )
            continue
        if doi is None or doi == "null":
            print(
                f"There is no DOI for version '{tool_version}' of tool '{tool_name}' participating in '{competition_name}', track '{competition_track}'.",
                file=sys.stderr,
            )
            continue
        yield tool_name


def main():
    parser = argparse.ArgumentParser(description="Process competition information.")

    parser.add_argument("competition_name", type=str, help="Name of the competition")
    parser.add_argument("competition_year", type=int, help="Year of the competition")
    parser.add_argument("competition_track", type=str, help="Track of the competition")
    parser.add_argument(
        "--fm-tools",
        type=Path,
        default=Path("fm-tools"),
        help="root directory of fm-tools",
    )
    parser.add_argument(
        "--archives",
        type=Path,
        default=Path("archives"),
        help="root directory of archives",
    )

    args = parser.parse_args()

    competition_name = args.competition_name
    competition_year = args.competition_year
    competition_track = args.competition_track
    competition_full_name = competition_name + " " + str(competition_year)

    tools = set(args.fm_tools.joinpath("data").glob("*.yml"))
    parameters = []
    for tool in list_tools(competition_full_name, competition_track, tools):
        parameters.append(
            (
                args.fm_tools,
                args.archives,
                competition_full_name,
                competition_track,
                tool,
            )
        )
    with multiprocessing.Pool(os.cpu_count()) as pool:
        pool.map(wrap_process_tool, parameters)
        pool.close()
        pool.join()


if __name__ == "__main__":
    main()
