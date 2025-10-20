#!/usr/bin/env python3

import sys
import argparse
import os
import urllib.parse
import re
import zipfile
import json
import multiprocessing as mp
import functools
import _logging as logging
import io
import base64
from typing import List, Tuple
import utils

import yaml
import numpy as np

try:
    from matplotlib import pyplot as plt
except ModuleNotFoundError:
    logging.warning("This script requires matplotlib: `pip3 install matplotlib`")
    sys.exit(15)


FILE_STORE = "fileByHash"
FILE_STORE_URL_PREFIX = ""

COVERAGE_SEQ_NAME = "results.json"
COV_ACCUMULATED = "Coverage (accumulated)"
MAX_COVERAGE = (
    100  # change this to 1 if coverage is expressed in 0.0--1.0 instead of percent
)

TABLE_STATS_IDX_TOOL = 4
TABLE_STATS_IDX_VALIDATOR = 3

ADDITIONAL_TABLE_CSS = """
.img-inline img {
    max-width: 100%;
}

.img-inline span {
    z-index:  10;
    display:  none;
    position: fixed;
    top: 0;
    left: 50%;
    margin-top:  40px;
    margin-left:  -300px;
    width:  600px;
    line-height: 16px;
}

.img-inline span img {
    max-height: none;
}

.img-inline:hover span {
    display:  inline;
    position:  fixed;
    border:  5px solid #FFF;
    color:  #EEE;
    background-color: #FFF;
    top: 50%;
    margin-top: -100px;
}
"""


def get_inputfile_paths(task_definition_yml) -> List[str]:
    """Return the input file for the given task definition.

    :param str task_definition_yml: Path to the task definition file.
    :return str: Path to the used input file, relative to the current directory.
    """
    try:
        with open(task_definition_yml) as inp:
            parsed_def = yaml.load(inp, Loader=yaml.FullLoader)
    except FileNotFoundError:
        logging.warning(f"File {task_definition_yml} not found")
        return None
    input_files_stated = parsed_def["input_files"]
    if isinstance(input_files_stated, str):
        input_files_stated = [input_files_stated]
    input_files = list()
    for input_file_relative_to_yml in input_files_stated:
        task_def_dir = os.path.dirname(task_definition_yml)
        input_file_relative_to_cwd = os.path.join(
            task_def_dir, input_file_relative_to_yml
        )
        input_files.append(os.path.relpath(input_file_relative_to_cwd))
    return input_files


def preg_match(pattern, text):
    return re.search(pattern, text) is not None


def preg_replace(pattern, replace_with, text):
    return re.sub(pattern, replace_with, text)


def get_witness_name(tag, line):
    witness_name = preg_replace(r"^.*___" + tag + "___(.*)$", "\\1", line.strip())
    witness_name = preg_replace(r"^\.\.\/", "", witness_name)
    witness_name = preg_replace(r"\.logfiles", ".files", witness_name)
    witness_yaml_name = preg_replace(r"___WITNESS___", "witness.yml", witness_name)
    witness_graphml_name = preg_replace(
        r"___WITNESS___", "witness.graphml", witness_name
    )
    expected_yaml_witness = "results-verified/" + urllib.parse.unquote(
        witness_yaml_name
    )
    expected_graphml_witness = "results-verified/" + urllib.parse.unquote(
        witness_graphml_name
    )
    # If both YAML and GraphML witness are generated,
    # the YAML witness has precedence over the GraphML witness;
    # so check for that first.
    if os.path.exists(expected_yaml_witness):
        return expected_yaml_witness
    return expected_graphml_witness


def make_url(line, task_def_name, tag, service, file_to_hash):
    input_files = get_inputfile_paths(task_def_name)
    if input_files is None:
        return ""
    if len(input_files) != 1:
        logging.debug(
            "Task %s  has multiple or no input files. We currently can't handle this. Input files: %s",
            task_def_name,
            input_files,
        )
        return ""
    input_program_name = input_files[0]
    witness_name = get_witness_name(tag, line)
    # print(witness_name)
    # print(input_program_name)

    input_program_sha256 = ""
    if os.path.exists(input_program_name):
        input_program_sha256 = file_to_hash[input_program_name]

    witness_sha256 = "0" * 64
    if os.path.exists(witness_name):
        witness_sha256 = file_to_hash[witness_name]

    parameters = [
        ("programSHA256", input_program_sha256),
        ("programName", input_program_name),
        ("witnessSHA256", witness_sha256),
        ("witnessName", witness_name),
    ]  # Use a list so that the key-value pairs are always in the same order

    data = urllib.parse.urlencode(parameters)

    url_components = [
        "https",  # scheme
        "www.sosy-lab.org",  # address
        "/research/witness-based-debugging/{}.php".format(service),  # directory
        "",  # parameters
        data,  # query components (GET-attributes)
        "",
    ]  # fragment identifier

    url = urllib.parse.urlunparse(url_components)
    # print('{}'.format(url))
    return url


def make_url_string(file_name, file_to_hash):
    urlstring = "---"
    if os.path.exists(file_name):
        assert file_name in file_to_hash, "{} not in hashmap".format(file_name)
        file_sha256 = file_to_hash[file_name]
        assert file_sha256
        basename = os.path.basename(file_name)
        file_suffix = ""
        if "." in basename:
            file_suffix = "." + basename.split(".")[-1]
        file_store_file_name = FILE_STORE + "/" + file_sha256 + file_suffix
        urlstring = FILE_STORE_URL_PREFIX + file_store_file_name
        if not os.path.exists(file_store_file_name):
            logging.warning(
                "File does not exist in store for %s, creating invalid URL: %s",
                file_name,
                file_store_file_name,
            )
    # print(file_name)
    return urlstring


def make_url_wit(line, tag, service, file_to_hash):
    witness_name = get_witness_name(tag, line)
    return make_url_string(witness_name, file_to_hash)


def make_value_size(line, tag, service):
    witness_name = get_witness_name(tag, line)
    test_count = utils.get_file_number_in_zip(witness_name)
    return test_count


def make_branches_plot(line, tag):
    witness = get_witness_name(tag, line)
    witness = witness.replace("results-verified/", "")
    if not os.path.exists(witness):
        return ""
    img_small = _get_plot_img(witness)
    img_large = _get_plot_img(witness, plot_labels=True)
    img_tag_small = '<img src="' + img_small + '" title="cov plot" />'
    img_tag_large = '<img src="' + img_large + '" title="cov plot" />'
    img_html = [
        '<div class="img-inline">',
        img_tag_small,
        "<span>",
        img_tag_large,
        "</span>",
        "</div>",
    ]
    imgstring = "\n".join(img_html)
    return imgstring


def _get_plot_img(zipped_file, plot_labels=False) -> str:
    """Extract the coverage-sequence file from the given zip and create the corresponding plot.

    :return str: image content for in-line HTML.
    """
    with zipfile.ZipFile(zipped_file) as inp_zip:
        sequence_file = next(
            (n for n in inp_zip.namelist() if n.endswith(COVERAGE_SEQ_NAME)), None
        )
        # assert sequence_file is not None, "No sequence file %s found in %s" % (COVERAGE_SEQ_NAME, zipped_file)
        if sequence_file is None:
            logging.warning(
                "No sequence file %s found in %s, no coverage plot"
                % (COVERAGE_SEQ_NAME, zipped_file)
            )
            coverage_sequence = []
        else:
            with inp_zip.open(sequence_file) as seq_inp:
                content = seq_inp.read().decode("utf-8")
            test_data = json.loads(content)

            if len(test_data) <= 1 or COV_ACCUMULATED not in test_data[0]:
                logging.debug(
                    "Only 0 or 1 test executed, not generating coverage plot for %s",
                    zipped_file,
                )
                return ""

            coverage_sequence = [float(t[COV_ACCUMULATED]) for t in test_data]

    # Each sequence should start with a 0
    coverage_sequence = [0.0] + coverage_sequence
    return _create_plot_img(coverage_sequence, plot_labels)


def _create_plot_img(coverage_sequence: list, plot_labels=False) -> str:
    """Creates a plot from the given sequence of coverage values.COVERAGE_SEQ_NAME

    :return str: image content for in-line HTML.
    """
    dpi = 100
    height = 200  # pixels
    width = 600
    # Use golden ratio of ~1.62 to get nice rectangular plot shape
    # width = height*1.62
    fg = plt.figure(figsize=(width / dpi, height / dpi), dpi=dpi, frameon=False)
    xlim = len(coverage_sequence) - 1
    if xlim == 0:
        xlim = 1
    if plot_labels:
        p = fg.add_subplot(111, xlim=(0, xlim), ylim=(0, MAX_COVERAGE))
        # This is necessary to achieve integer-only ticks on x axis.
        from matplotlib.ticker import MaxNLocator

        fg.gca().xaxis.set_major_locator(MaxNLocator(integer=True))
    else:
        p = fg.add_subplot(
            111, xticks=[], yticks=[], xlim=(0, xlim), ylim=(0, MAX_COVERAGE)
        )

    p.margins(x=0, y=0)

    p.plot(coverage_sequence, linewidth=2.5)

    imgdata = io.BytesIO()
    plt.subplots_adjust(left=0.06, right=0.99, top=0.93, bottom=0.15)
    plt.savefig(imgdata, format="png")
    plt.savefig("/tmp/plottest.png", format="png")
    imgdata.seek(0)

    plt.close()

    return "data:image/png;base64," + urllib.parse.quote(
        base64.b64encode(imgdata.read())
    )


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
    # If one of the considered lines starts with "rows: [" (with an arbitray number of whitespace),
    # the array following "rows: " on the same line is considered.
    # If the table generator changes that expected structure,
    # it must be adjusted here.
    in_data_def = False
    with open(file_name, "r") as inp:
        relevant_lines = list()
        for line in inp:
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


def _add_more_style(file_content: str) -> str:
    new_lines = []
    for line in file_content.split("\n"):
        new_lines.append(line)
        if "<head" in line:
            new_lines.append("<style>")
            new_lines.append(ADDITIONAL_TABLE_CSS)
            new_lines.append("</style>")
    return "\n".join(new_lines)


def _add_testsuite_stats(data_json, both_testsuite_sizes):
    def _add_stats_at_index(testsuite_sizes, is_validator):
        testsuite_sizes = np.array(testsuite_sizes)
        # Add statistics for test-suite size
        testsuite_size_stats = {
            "sum": str(np.sum(testsuite_sizes)),
            "avg": str(utils.round_to_sig_numbers(np.mean(testsuite_sizes), 3)),
            "max": str(np.max(testsuite_sizes)),
            "median": str(np.median(testsuite_sizes)),
            "min": str(np.min(testsuite_sizes)),
            "stdev": str(utils.round_to_sig_numbers(np.std(testsuite_sizes), 3)),
        }
        # Magic numbers that map to correct location in benchexec data json,
        # which just identifies elements by their order
        if is_validator:
            ts_size_idx = TABLE_STATS_IDX_VALIDATOR
            idx = 1
        else:
            ts_size_idx = TABLE_STATS_IDX_TOOL
            idx = 0
        data_json["stats"][0]["content"][idx][ts_size_idx] = testsuite_size_stats

    if both_testsuite_sizes["tool"]:
        _add_stats_at_index(both_testsuite_sizes["tool"], False)
    if both_testsuite_sizes["validator"]:
        _add_stats_at_index(both_testsuite_sizes["validator"], True)


def parse(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "html_file", nargs="+", help="HTML file to replace templates in"
    )
    parser.add_argument(
        "--hashmap_file",
        required=True,
        help="hashmap of file store. Links in resulting HTML will link to files of that file store.",
    )
    parser.add_argument(
        "--file-store-url-prefix",
        required=True,
        help="URL prefix of file store. This should point to a publicly reachable file-store webpage.",
    )
    parser.add_argument(
        "--no-plots",
        dest="create_plots",
        action="store_false",
        default=True,
        help="Do not create plots",
    )

    args = parser.parse_args(argv)
    missing = [f for f in args.html_file + [args.hashmap_file] if not os.path.exists(f)]
    if missing:
        raise ValueError(f"File(s) {missing} don't exist")
    return args


def replace_links(row, hashmap, create_plots=True) -> Tuple[dict, dict]:
    """Replace template strings in the given (JSON) data row with the values stored in the hashmap.

    The returned value is a tuple '(adjusted_row, testsuite_size)'.
    The first tuple value ('adjusted_row') is the given row with the template strings replaced.

    For SV-COMP, the second tuple value ('testsuite_size') can be safely ignored.
    For Test-Comp, the second tuple value is a dictionary that contains
    the test-suite sizes encountered, in a list.
    Test-suite sizes are recorded and returned
    for (a) the test suites created by the considered participant tool
    and (b) the minimized test suites created by the validator.
    """

    testsuite_sizes = {"validator": list(), "tool": list()}
    # [3:] removes the prefix "../" of "../sv-benchmarks" to be consistent
    # with the hash map
    task_name = row["href"][3:]
    task_name = urllib.parse.unquote(task_name)
    for idx, subsec in enumerate(row["results"]):
        is_validator = idx > 0
        # the data of each individual result set merged into a table
        # is one 'subsec' in the data json
        relevant_cells = subsec["values"]
        for cell in relevant_cells:
            if "href" in cell:
                v = cell["href"]
                if not v:
                    continue
                if "___WITINSPDEL" in v:
                    url = make_url(v, task_name, "WITINSPDEL", "inspect", hashmap)
                    if url:
                        cell["html"] = "<a href='{}' target='_self'>inspect</a>".format(
                            url
                        )
                    else:
                        cell["html"] = None
                    cell["href"] = None
                    cell["raw"] = None
                elif "___WITVALIDEL___" in v:
                    url = make_url(v, task_name, "WITVALIDEL", "validate", hashmap)
                    if url:
                        cell["html"] = (
                            "<a href='{}' target='_self'>validate</a>".format(url)
                        )
                    else:
                        cell["html"] = None
                    cell["href"] = None
                    cell["raw"] = None
                elif "___WITDOWNDEL___" in v:
                    url = make_url_wit(v, "WITDOWNDEL", "", hashmap)
                    cell["html"] = "<a href='{}' target='_self'>view</a>".format(url)
                    cell["href"] = None
                    cell["raw"] = None
                elif "___TESTSUITESIZE___" in v:
                    testsuite_size = make_value_size(v, "TESTSUITESIZE", "")
                    if is_validator:
                        testsuite_sizes["validator"].append(testsuite_size)
                    else:
                        testsuite_sizes["tool"].append(testsuite_size)
                    cell["raw"] = str(testsuite_size)
                    cell["href"] = None
                    del testsuite_size  # don't use testsuite_size outside of this block
                elif create_plots and "___COVPLOT___" in v:
                    cell["html"] = make_branches_plot(v, "COVPLOT")
                    cell["href"] = None
                    cell["raw"] = None
    return (row, testsuite_sizes)


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    logging.init(logging.DEBUG, "replace-links")
    try:
        args = parse(argv)
    except ValueError as e:
        logging.error("%s", e)
        return 1
    hashmap_file = args.hashmap_file
    global FILE_STORE_URL_PREFIX
    FILE_STORE_URL_PREFIX = args.file_store_url_prefix

    try:
        logging.debug("Start reading hashmap")
        with open(hashmap_file) as inp:
            hashmap = json.load(inp)
        logging.debug("Done reading hashmap")
    except json.decoder.JSONDecodeError as e:
        logging.error("File %s no valid json: %s", hashmap_file, e)
        return 1

    for filename in args.html_file:
        logging.info("Replacer: Processing {}".format(filename))
        new_content = handle_file(filename, hashmap, args.create_plots)
        if new_content:
            with open(filename, "w") as file_out:
                file_out.write(new_content)
    logging.info("Replacer: Done")


def handle_file(filename, hashmap, create_plots=True):
    logging.debug("Start getting data json from html")
    data_json = _get_data_json(filename)
    logging.debug("Done getting data json from html")
    if not data_json or not data_json["rows"]:
        logging.error(
            "Content of %s not in expected format: field 'rows' missing", filename
        )
        return None

    logging.debug("Start replacing template links in data json")
    with mp.Pool(processes=2) as pool:
        rep = functools.partial(
            replace_links, hashmap=hashmap, create_plots=create_plots
        )
        rows, individual_testsuites_sizes = zip(*pool.map(rep, data_json["rows"]))
        data_json["rows"] = rows
        testsuite_sizes = {
            "tool": [s for ts in individual_testsuites_sizes for s in ts["tool"]],
            "validator": [
                s for ts in individual_testsuites_sizes for s in ts["validator"]
            ],
        }
    logging.debug("Done replacing template links in data json")

    # if there's no data for tool, there also won't be any data for validator, so this check
    # is good enough for both
    if testsuite_sizes["tool"]:
        _add_testsuite_stats(data_json, testsuite_sizes)
    logging.debug("Start replacing data json in HTML")
    new_content = _replace_data_json(filename, data_json)
    logging.debug("Done replacing data json in HTML")
    logging.debug("Start adding stylesheets in HTML")
    new_content = _add_more_style(new_content)
    logging.debug("Done adding stylesheets in HTML")
    return new_content


# Only execute automatically if called from command line.
# This allows us to use the methods of this module in other scripts.
if __name__ == "__main__":
    sys.exit(main())
