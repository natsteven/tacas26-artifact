import argparse
import logging
import sys
from pathlib import Path

from check_archives_with_service import check_tool, participates_in_svcomp

SCRIPT = Path(__file__).parent
DATA = SCRIPT.parent / "data"


def main(raw_args):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "glob", help="The glob to check for (default *.yml)", default="*.yml", nargs="?"
    )
    args = parser.parse_args(raw_args)
    for tool in DATA.glob(args.glob):
        logging.info("Looking at tool: %s", tool)
        if (version := participates_in_svcomp(tool)) is not None:
            try:
                logging.info("Checking tool (version): %s (%s)", tool, version)
                check_tool(tool.stem, tool, version, is_svcomp=True)
            except Exception as e:
                print(tool, " ended with an exception!", e, "\n\n")

        else:
            print(tool, " does not participate in SV-COMP 24!")


if __name__ == "__main__":
    main(sys.argv[1:])
