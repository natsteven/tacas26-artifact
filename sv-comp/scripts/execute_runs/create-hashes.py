#!/usr/bin/env python3

import os
from functools import partial
import glob
import json
import mmap
import sys
import hashlib
import multiprocessing as mp
import subprocess
import argparse
from pathlib import Path

sys.path.append(str((Path(__file__).parent / ".." / "prepare_tables").resolve()))
import utils
import _logging as logging


def get_sha256_from_file(file_name):
    def create_hash(content):
        return hashlib.sha256(content).hexdigest()

    with open(file_name, "rb") as i:
        try:
            # map the file content into virtual memory and hash from there
            # - this avoids unnecessary reads.
            # cf. https://stackoverflow.com/a/62214783/3012884
            with mmap.mmap(i.fileno(), 0, prot=mmap.PROT_READ) as mm:
                return create_hash(mm)
        except ValueError:
            logging.debug(
                "mmap can't map %s for hashing. Falling back to default read", file_name
            )
            return create_hash(i.read())


def handle_file(i, root_dir):
    if os.path.isdir(i):
        return dict()
    if utils.is_on_blacklist(i):
        # We skip blacklisted files
        logging.debug("Skipping blacklisted file %s", i)
        return dict()
    logging.debug("Hashing %s", i)
    sha_hash = get_sha256_from_file(i)
    file_path_for_map = os.path.relpath(i, start=root_dir)
    return {file_path_for_map: sha_hash}


def write_hashmap(output_file, directories, root_dir, target_file_glob):
    """Create a hashmap from the result files found in the given directory,
    and writes it to the output file.
    If the output file already exists, its values are merged with the newly created values.

    :param str output_file: Name of the output file to write map into.
    :param List[str] directories: Path to the directories in which to look for result files.
    :param str root_dir: Path to the directory that should be used as
             base directory for file links.
    :param str target_file_glob: Glob pattern for files to create hashes for.
    """
    hashes = dict()
    hashes_file = output_file
    hashes_dir = os.path.dirname(hashes_file)
    if not hashes_dir:
        hashes_dir = "."
    # Create the directory of the output file
    # if it doesn't exist
    os.makedirs(hashes_dir, exist_ok=True)
    # Read all old hashmap values first
    if os.path.exists(hashes_file):
        with open(hashes_file) as inp:
            old_hashes = json.load(inp)
        hashes.update(old_hashes)

    for directory in directories:
        if not os.path.exists(directory):
            logging.warning("Invalid directory %s" % directory)
            return

        logging.info("  Processing files (write_hashmap) in '%s' ..." % directory)
        glob_pattern = directory + "/**/" + target_file_glob
        logging.debug("Globbing for %s", glob_pattern)
        # Process pool that is used to create hashes for files in parallel.
        # The given number defines the number of jobs that are run in parallel.
        with mp.Pool(2) as process_pool:
            individual_hash_dicts = process_pool.map(
                partial(handle_file, root_dir=root_dir),
                glob.iglob(glob_pattern, recursive=True),
            )
            for h in individual_hash_dicts:
                assert all(
                    k not in hashes or hashes[k] == v for k, v in h.items()
                ), "Duplicate key: %s and %s" % next(
                    ((k, v), hashes[k])
                    for k, v in h.items()
                    if k in hashes and hashes[k] != v
                )
                hashes.update(h)
    with open(hashes_file, "w+") as outp:
        json.dump(hashes, outp, indent=utils.JSON_INDENT)
    logging.info("Wrote hashes map to %s" % hashes_file)
    hashmap_dir = os.path.dirname(os.path.abspath(hashes_file))
    zip_dir = hashmap_dir + ".zip"
    if os.path.exists(zip_dir):
        logging.debug("Zipping %s into %s", hashes_file, zip_dir)
        zip_cmd = ["zip", "-MM", "-u", zip_dir, hashes_file]
        zip_result = subprocess.run(
            zip_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )
        print(zip_result.stdout.decode())

        logging.info("Added hashes map to %s" % zip_dir)


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
        "--root-dir",
        dest="root_dir",
        action="store",
        type=str,
        required=True,
        help="Base directory to use for relative paths in hashes.json",
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
    parser.add_argument(
        "--glob",
        dest="glob_pattern",
        action="store",
        type=str,
        default="*",
        help="glob pattern to use. If not given, all files in all subdirectories of the given directory are used.",
    )
    parser.add_argument("dirs", nargs="+", help="list of folders to create hashes for")

    return parser.parse_args(argv)


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    args = parse(argv)
    if args.verbose:
        logging.init(logging.DEBUG, "create-hashes")
    else:
        logging.init(logging.INFO, "create-hashes")

    write_hashmap(args.output_path, args.dirs, args.root_dir, args.glob_pattern)


if __name__ == "__main__":
    sys.exit(main())
