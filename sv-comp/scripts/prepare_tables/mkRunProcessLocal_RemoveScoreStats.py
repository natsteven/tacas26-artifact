#!/usr/bin/env python3

import argparse
import os
import json
import _logging as logging


def _replace_data_json(file_name: str, data_rows: dict) -> str:
    new_content = list()
    in_data_def = False
    json_str = json.dumps(data_rows, sort_keys=True)
    assert json_str[0] == "{", "json str starts with {}".format(json_str[:20])
    assert json_str[-1] == "}", "json str stops with {}".format(json_str[-20:])
    json_str = "{\n" + json_str[1:-1] + "\n};\n"
    with open(file_name, "r") as inp:
        for line in inp.readlines():
            if line.startswith("const data = {"):
                in_data_def = True
                new_line = "const data = " + json_str
                new_content.append(new_line)

            if not in_data_def:
                new_content.append(line)
            elif line.startswith("}"):
                in_data_def = False
    return "".join(new_content)


def _get_data_json(file_name: str) -> dict:
    # This method gets the data json from the html
    # through simple pattern matching.
    # After the start of the expected data json is found in the given file,
    # every line is considered until a line starting with '}' is encountered.
    # If one of the considered lines starts with "const data = {"
    # the object starting with '{' at the end of that line is read and returned
    # until a line starting with '}' is encountered. This is then considered the end
    # of the data object.
    # If the table generator changes that expected structure,
    # it must be adjusted here.
    in_data_def = False
    with open(file_name, "r") as inp:
        relevant_lines = list()
        for line in inp.readlines():
            if line.startswith("const data = {"):
                in_data_def = True
                relevant_lines.append("{")
            elif in_data_def:
                if line.startswith("}"):
                    in_data_def = False
                    relevant_lines.append("}")
                    break
                else:
                    relevant_lines.append(line)
        if relevant_lines:
            return json.loads("".join(relevant_lines))
        return None


# Only execute automatically if called from command line.
# This allows us to use the methods of this module in other scripts.
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "files", metavar="html-file", nargs="+", help="html files to modify"
    )
    parser.add_argument(
        "--insitu",
        dest="replace_files",
        action="store_true",
        help="replace files in-place. New file content will be written to $file.new, otherwise",
    )
    args = parser.parse_args()

    logging.init(logging.DEBUG, "create-hashes")

    for filename in args.files:
        if not os.path.exists(filename):
            logging.warning("File %s doesn't exist, skipping it", filename)
            continue

        try:
            data_json = _get_data_json(filename)
            new_stats = list()
            for stat in data_json["stats"]:
                if stat["id"] != "score":
                    new_stats.append(stat)
            data_json["stats"] = new_stats
            new_html = _replace_data_json(filename, data_json)
            if args.replace_files:
                new_filename = filename
            else:
                new_filename = filename + ".new"
            with open(new_filename, "w") as file_out:
                file_out.write(new_html)

        except json.JSONDecodeError as e:
            logging.warning("File %s not parseable, skipping it: %s", filename, e)
        except TypeError as e:
            logging.warning("Error occurred with file %s, skipping it: %s", filename, e)
