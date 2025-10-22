#!/usr/bin/env python3

import argparse
import os
import sys
from io import StringIO
from pathlib import Path

from ruamel.yaml import YAML


def format(yaml_file_path, check):
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.width = 4096  # Set the line width
    yaml.indent(mapping=2, sequence=4, offset=2)  # Set indentation

    # Load the YAML file
    with open(yaml_file_path, "r") as f:
        data = yaml.load(f)

    # Write the modified data back to the file, preserving the format
    if check:
        string_stream = StringIO()
        yaml.dump(data, string_stream)
        string = string_stream.getvalue()
        file_contents = Path(yaml_file_path).read_text()
        if string != file_contents:
            print(
                f"File {yaml_file_path} is not formatted, run '{sys.argv[0]} --file {yaml_file_path}' to format it"
            )
            exit(1)
    else:
        with open(yaml_file_path, "w") as f:
            yaml.dump(data, f)


def parse_args():
    parser = argparse.ArgumentParser(description="Format YAML files")
    parser.add_argument(
        "--directory", help="Path to the directory containing YAML files"
    )
    parser.add_argument("--file", help="Path to the YAML file to format")
    parser.add_argument("--check", default=False, action="store_true")

    args = parser.parse_args()

    if not args.directory and not args.file:
        parser.print_help()
        exit()

    return args


if __name__ == "__main__":
    args = parse_args()

    if args.file:
        format(args.file, args.check)
        exit()

    elif args.directory:
        directory_path = args.directory
        for filename in os.listdir(directory_path):
            if filename.endswith(".yml"):
                file_path = os.path.join(directory_path, filename)
                format(file_path, args.check)
        exit()
