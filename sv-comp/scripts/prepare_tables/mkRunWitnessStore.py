import argparse
import sys
import functools
from os import makedirs
import os
from os.path import isfile, getmtime
import time
from xml.etree import ElementTree as etree
import json
import re
import zipfile
import multiprocessing as mp
import utils
import _logging as logging
import yaml

GRAPHML_TAG = "{http://graphml.graphdrawing.org/xmlns}graphml"
METADATA_TAG = "test-metadata"
GRAPH_TAG = "{http://graphml.graphdrawing.org/xmlns}graph"
DATA_TAG = "{http://graphml.graphdrawing.org/xmlns}data"
RESULTS_VERIFIED_DIR = "results-verified"

JSON_DIR = "witnessInfoByHash"
WITNESS_LIST_BY_PROGRAM_DIR = "witnessListByProgramHash"
WITNESS_LIST_BY_PROGRAM_JSON = "witnessListByProgramHashJSON"

EXPECTED_WITNESS_NAME = "witness.yml"


def is_graphml_file(file_name):
    return isfile(file_name) and file_name.endswith(".graphml")


def is_yaml_witness(file_name):
    return isfile(file_name) and os.path.basename(file_name) == EXPECTED_WITNESS_NAME


def is_witness(file_name):
    return is_graphml_file(file_name) or is_yaml_witness(file_name)


def is_zip_file(file_name):
    return isfile(file_name) and file_name.endswith(".zip")


def parse_xml(xml_content):
    tree_root = etree.fromstring(xml_content)
    return tree_root


def parse_graphml(graphml_file):
    with open(graphml_file) as inp:
        tree_root = parse_xml(inp.read())

    if GRAPHML_TAG != tree_root.tag:
        raise etree.ParseError(
            "Graphml file '{}' is invalid: Its root element is not named '{}'.".format(
                graphml_file, GRAPHML_TAG
            )
        )

    return tree_root


def parse_test_metadata(test_metadata_content):
    tree_root = parse_xml(test_metadata_content)

    if METADATA_TAG != tree_root.tag:
        raise etree.ParseError(
            "Metadata.xml is invalid: Its root element is named '{}', not '{}'.".format(
                tree_root.tag, GRAPHML_TAG
            )
        )

    return tree_root


def get_if_exists(dictionary, key):
    if key in dictionary.keys():
        return dictionary[key]
    else:
        return ""


def mk_witness_info(witness_file, output_dir):
    try:
        witness_info = _get_witness_info(witness_file)
    except Exception as e:
        witness_size = os.path.getsize(witness_file) / 1000.0
        logging.exception(
            "Exception for %s (size: %s kB): %s", witness_file, witness_size, e
        )
    else:
        if witness_info:
            write_witness_info(witness_info, output_dir)


def _get_witness_info_from_yaml_witness(witness_file):
    with open(witness_file, "r") as inp:
        data = yaml.safe_load(inp)

    if not isinstance(data, list) or len(data) != 1:
        raise ValueError(
            f"Currently, witness store can only handle a single entry per YAML witness file. Got {len(data)} entries."
        )
    data = data[0]
    witness_info = {}
    # These data fields are set by the GraphML witness format and expected
    if data["entry_type"] == "invariant_set":
        witness_type = "correctness_witness"
    elif data["entry_type"] == "violation_sequence":
        witness_type = "violation_witness"
    witness_info["witness-type"] = witness_type
    metadata = data["metadata"]
    witness_info["format-version"] = metadata["format_version"]
    witness_info["creationtime"] = metadata["creation_time"]

    producer = metadata["producer"]["name"]
    if "version" in metadata["producer"]:
        producer = f"{producer} {metadata['producer']['version']}"
    witness_info["producer"] = producer

    if len(metadata["task"]["input_files"]) != 1:
        raise ValueError(
            f"Can not handle more than one input file. Got {len(metadata['task']['input_files'])} input files."
        )
    program_file = metadata["task"]["input_files"][0]
    witness_info["programfile"] = program_file
    witness_info["programhash"] = metadata["task"]["input_file_hashes"][program_file]

    # Use the architecture names of GraphML to be backwards-compatible: '32bit' and '64bit'
    if metadata["task"]["data_model"] == "ILP32":
        architecture = "32bit"
    elif metadata["task"]["data_model"] == "LP64":
        architecture = "64bit"
    else:
        raise ValueError(f"Unknown data model: {metadata['task']['data_model']}")
    witness_info["architecture"] = architecture
    witness_info["sourcecodelang"] = metadata["task"]["language"]
    witness_info["specification"] = metadata["task"]["specification"]

    return witness_info


def _get_witness_info(witness_file):
    if not is_witness(witness_file) and not is_zip_file(witness_file):
        return None
    witness_info = dict()
    witness_info["witness-file"] = witness_file
    witness_info["witness-sha256"] = re.sub(
        r"^.*\/([^\/]*).(graphml|zip|yml)", "\\1", witness_file
    )
    witness_info["witness-size"] = os.path.getsize(witness_file)

    # Extract witness-info record from witness
    if is_graphml_file(witness_file):
        try:
            witness_info["format-version"] = "1.0"
            witness_xml = parse_graphml(witness_file)
            for data in witness_xml.find(GRAPH_TAG).findall(DATA_TAG):
                witness_info[data.get("key")] = data.text
        except etree.ParseError:
            witness_info["error-xmlparsing"] = "File produces XML parsing error."
        except OverflowError as e:
            logging.error("Error parsing file '{}': {}".format(witness_file, e.msg))
    elif is_yaml_witness(witness_file):
        try:
            witness_info.update(_get_witness_info_from_yaml_witness(witness_file))
        except yaml.scanner.ScannerError as e:
            witness_info["error-yamlparsing"] = (
                f"File produces YAML parsing error: {str(e)}"
            )
        except (KeyError, ValueError) as e:
            witness_info["error-yamlparsing"] = (
                f"File YAML does not match expected schema: {str(e)}"
            )
    elif is_zip_file(witness_file):
        # Extract info from metadata.xml in the zip archive
        with zipfile.ZipFile(witness_file) as zfile:
            for finfo in zfile.infolist():
                if finfo.filename.endswith("metadata.xml"):
                    try:
                        with zfile.open(finfo) as ifile:
                            metadata_xml = parse_test_metadata(ifile.read())
                        for data in metadata_xml:
                            witness_info[data.tag] = data.text

                    except etree.ParseError:
                        witness_info["error-xmlparsing"] = (
                            "File produces XML parsing error."
                        )
                    # There's only one metadata.xml, so stop after we found it
                    break
        witness_info["witness-type"] = "test-suite"
        witness_info["witness-number-of-tests"] = utils.get_file_number_in_zip(
            witness_file
        )
    else:
        raise ValueError(f"Unhandled file type: {witness_file}")

    if "programhash" in witness_info.keys():
        if len(get_if_exists(witness_info, "programhash")) == 64:
            witness_info["program-sha256"] = witness_info["programhash"]
        else:
            witness_info["error-program-sha256"] = (
                "Key 'programhash' is not an SHA-256 hash."
            )
    else:
        witness_info["error-programhash"] = "Key 'programhash' not present."
    if "specification" not in witness_info.keys():
        witness_info["error-specification-exists"] = "Key 'specification' not present."
    if len(get_if_exists(witness_info, "specification")) > 100:
        witness_info["error-specification-length"] = (
            "Key 'specification' longer than 100 characters."
        )
    if "creationtime" not in witness_info.keys():
        witness_info["creationtime"] = (
            time.strftime("%Y-%m-%dT%H:%M %Z", time.localtime(getmtime(witness_file)))
            + " (comp)"
        )
    return witness_info


def write_witness_info(witness_info, output_dir):
    # Add witness info to directory 'witnessInfoByHash'
    json_dir = os.path.join(output_dir, JSON_DIR)
    json_file = os.path.join(json_dir, witness_info["witness-sha256"] + ".json")
    if os.path.exists(json_file):
        logging.info("%s already exists, not overwriting." % json_file)
        return

    with open(json_file, "w") as json_file_obj:
        json.dump(witness_info, json_file_obj, indent=utils.JSON_INDENT, sort_keys=True)

    # Add witness info to directory 'witnessListByProgramHash/<hash>'
    if "program-sha256" in witness_info.keys():
        witness_dir = os.path.join(
            output_dir, WITNESS_LIST_BY_PROGRAM_DIR, witness_info["program-sha256"]
        )
        if not os.path.exists(witness_dir):
            if os.path.lexists(witness_dir):
                # witness_dir is broken symlink. Remove it.
                os.remove(witness_dir)
            makedirs(witness_dir, exist_ok=True)
        try:
            info_file = witness_info["witness-sha256"] + ".json"
            os.link(json_file, os.path.join(witness_dir, info_file))
        except FileExistsError:
            # logging.error('Error: File exists.')
            pass
        except IOError as e:
            logging.error("%s", e)


def _yield_witnesses_in_dir(witnesses):
    for witness_file in witnesses:
        try:
            with open(witness_file, "r") as f:
                yield json.load(f)
        except Exception as e:
            witness_size = os.path.getsize(witness_file) / 1000.0
            logging.exception(
                "Exception for %s (size: %s kB): %s", witness_file, witness_size, e
            )


def mk_witness_list(program_dir, output_dir):
    witness_list = list(
        _yield_witnesses_in_dir(
            [
                os.path.join(curr_dir, witness_file)
                for curr_dir, _, witness_files in os.walk(program_dir)
                for witness_file in witness_files
            ]
        )
    )
    witness_list_dir = os.path.join(output_dir, WITNESS_LIST_BY_PROGRAM_JSON)
    os.makedirs(witness_list_dir, exist_ok=True)
    json_file = witness_list_dir + "/" + re.sub(r".*\/", "", program_dir) + ".json"
    try:
        with open(json_file, "w") as json_file_obj:
            json.dump(witness_list, json_file_obj, indent=2)
    except IOError as e:
        logging.error("%s", e)


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description="Build the witness store from the existing fileByHash directory"
    )
    parser.add_argument(
        "--output-dir",
        default=".",
        help="The output directory for the witness store. The witness store may be multiple directories.",
    )
    parser.add_argument(
        "fileByHash",
        default="fileByHash",
        help="The fileByHash directory, as it is created by mkRunProcessLocal_CreateFileStore.py",
    )
    return parser.parse_args(argv)


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    args = parse_args(argv)

    json_dir = os.path.join(args.output_dir, JSON_DIR)

    logging.init(logging.DEBUG, "mkRunWitnessStore")
    logging.info("Updating witness info records and program-to-witness map ...")
    # parallel = concurrent.futures.ProcessPoolExecutor(max_workers=os.cpu_count()*2)
    os.makedirs(json_dir, exist_ok=True)

    create_individual_info = functools.partial(
        mk_witness_info, output_dir=args.output_dir
    )
    create_witness_list = functools.partial(mk_witness_list, output_dir=args.output_dir)
    with mp.Pool(processes=min(os.cpu_count(), 100)) as parallel:
        parallel.map(
            create_individual_info,
            (
                os.path.join(curr_dir, f)
                for curr_dir, _, files in os.walk(args.fileByHash)
                for f in files
            ),
        )

        logging.info("Updating program-to-witness map in JSON files ...")
        # parallel = concurrent.futures.ProcessPoolExecutor(max_workers=os.cpu_count()*2)
        parallel.map(
            create_witness_list,
            (
                os.path.join(curr_dir, d)
                for curr_dir, program_dirs, _ in os.walk(
                    os.path.join(args.output_dir, WITNESS_LIST_BY_PROGRAM_DIR)
                )
                for d in program_dirs
            ),
        )


if __name__ == "__main__":
    sys.exit(main())
