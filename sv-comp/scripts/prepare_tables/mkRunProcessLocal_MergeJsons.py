#!/usr/bin/env python3

import json
import sys
import argparse

import utils
import _logging as logging


def _merge_hashmaps(*files):
    hashmap_union = dict()
    for hashmap_file in files:
        with open(hashmap_file) as inp:
            curr_hashmap = json.load(inp)
            # This always fails because of the program files
            # for k in curr_hashmap:
            #    assert k not in hashmap_union, "Key already exists: %s" % k
            hashmap_union.update(curr_hashmap)
    return hashmap_union


def merge_hashmaps(output_file, *files):
    hashmap_union = _merge_hashmaps(*files)
    hashmap_file = output_file
    with open(hashmap_file, "w+") as outp:
        json.dump(hashmap_union, outp, indent=utils.JSON_INDENT)
    logging.info("Wrote hashmap to %s", hashmap_file)


def parse(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--verbose",
        "-v",
        dest="verbose",
        action="store_true",
        default=False,
        help="verbose output",
    )
    parser.add_argument(
        "--output",
        "-o",
        dest="output_path",
        action="store",
        type=str,
        required=True,
        help="output file to write result json into.",
    )
    parser.add_argument("files", nargs="+", help="list of json files to merge")

    return parser.parse_args(argv)


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    args = parse(argv)
    if args.verbose:
        logging.init(logging.DEBUG, "merge-jsons")
    else:
        logging.init(logging.INFO, "merge-jsons")

    merge_hashmaps(args.output_path, *args.files)


if __name__ == "__main__":
    sys.exit(main())
