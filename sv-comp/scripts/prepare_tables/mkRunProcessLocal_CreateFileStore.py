#!/usr/bin/env python3

import os
import json
import sys
import prepare_tables._logging as logging
import argparse
import functools
import multiprocessing

import prepare_tables.utils as utils


def link_file(f, sha_hash, root_dir, store_dir):
    source, by_hash_file = get_source_and_target(f, sha_hash, root_dir, store_dir)
    try:
        os.link(source, by_hash_file)
        logging.debug("Linked %s to %s", source, by_hash_file)
    except FileExistsError:
        # assert os.path.exists(by_hash_file), "File exists but is broken link. This should be handled"
        logging.debug("Skipping %s, already exists", by_hash_file)
    except FileNotFoundError:
        logging.warning(
            "File from hashmap does not exist, not adding it to file store: %s",
            source,
        )


def get_source_and_target(f, sha_hash, root_dir, store_dir):
    if utils.is_on_blacklist(f):
        logging.debug("%s on blacklist, not adding to file hash", f)
        return

    # assert not os.path.isabs(f)
    source = os.path.realpath(os.path.join(root_dir, f))
    try:
        file_suffix = os.path.basename(f).rsplit(".")[-1]
        target = os.path.join(store_dir, sha_hash + "." + file_suffix)
    except IndexError:
        target = os.path.join(store_dir, sha_hash)
    return source, target


def create_store(by_hash_dir, root_dir, *hash_files):
    """Create, for each entry in the given hashmap, a file $by_hash_dir/$hash.$file_suffix.

    :param str by_hash_dir: Path to the directory into which to put hashed files.
    :param str root_dir: Path to the directory that should be used as
             base directory for file links.
    :param str hash_files: JSON files that contains hashes that should be processed.
    """
    if not os.path.exists(by_hash_dir):
        os.mkdir(by_hash_dir)
        logging.debug("%s created", by_hash_dir)

    root_dir = os.path.abspath(root_dir)

    link = functools.partial(link_file, root_dir=root_dir, store_dir=by_hash_dir)
    for hashes_file in hash_files:
        logging.debug("Considering %s", hashes_file)
        try:
            with open(hashes_file) as inp:
                hashmap = json.load(inp)
        except json.decoder.JSONDecodeError as e:
            logging.error("Error loading %s: %s", hashes_file, e)
            continue

        with multiprocessing.Pool(processes=4) as pool:
            pool.starmap(link, hashmap.items())


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
        dest="store_dir",
        action="store",
        type=str,
        required=True,
        help="output directory to write store into.",
    )
    parser.add_argument(
        "--root-dir",
        dest="root_dir",
        action="store",
        type=str,
        required=True,
        help="base directory to use for relative paths in hashes.json",
    )
    parser.add_argument(
        "files", nargs="+", help="list of json files to create store for"
    )

    return parser.parse_args(argv)


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    args = parse(argv)
    if args.verbose:
        logging.init(logging.DEBUG, "create-store")
    else:
        logging.init(logging.INFO, "create-store")

    create_store(args.store_dir, args.root_dir, *args.files)


if __name__ == "__main__":
    sys.exit(main())
