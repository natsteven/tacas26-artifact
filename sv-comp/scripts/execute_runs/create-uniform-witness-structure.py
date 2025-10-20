#!/usr/bin/env python3

import os
import glob
import sys
import argparse
import _logging as logging


def unify_directories(expected_name_in_files_dir, *dirs):
    for directory in dirs:
        if not os.path.exists(directory):
            logging.warning("Invalid directory %s" % directory)
            return None

        logging.info(
            "  Processing files (unify_directories) in '%s' using name '%s' ...",
            directory,
            expected_name_in_files_dir,
        )
        target_file_glob = expected_name_in_files_dir
        if target_file_glob == "test-suite.zip":
            target_file_glob = ".zip"
        glob_pattern = directory + "/**/*" + target_file_glob
        logging.debug("Globbing for %s", glob_pattern)
        for i in glob.iglob(glob_pattern, recursive=True):
            if os.path.isdir(i):
                # We skip directories
                continue
            logging.debug("Looking at %s", i)
            abs_path = os.path.abspath(i)
            lookup_phrase = ".yml/"
            assert ".yml/" in abs_path, (
                "Found file is not within a <task_def>.yml/ directory: '%s'" % abs_path
            )
            dir_idx_stop = abs_path.rfind(lookup_phrase)
            file_dir = abs_path[:dir_idx_stop] + lookup_phrase
            witness_file = os.path.join(file_dir, expected_name_in_files_dir)
            target_file = os.path.relpath(abs_path, file_dir)
            if not os.path.exists(witness_file):
                logging.debug("Link from %s to %s", i, witness_file)
                os.symlink(target_file, witness_file)


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
        "--copy-to-files-dir",
        dest="new_name",
        action="store",
        type=str,
        required=True,
        help="it is checked whether the given file name exists in a *.files directory in which a file matching the glob were found, and if this is not the case, is is created as a link to the original file",
    )
    parser.add_argument("dirs", nargs="+", help="list of folders to visit")

    return parser.parse_args(argv)


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    args = parse(argv)
    if args.verbose:
        logging.init(logging.DEBUG, "uniform-witness-struct")
    else:
        logging.init(logging.INFO, "uniform-witness-struct")

    unify_directories(args.new_name, *args.dirs)


if __name__ == "__main__":
    sys.exit(main())
