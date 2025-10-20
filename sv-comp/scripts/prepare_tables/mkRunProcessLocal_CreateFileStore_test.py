#!/usr/bin/env python3

import unittest
import prepare_tables.mkRunProcessLocal_CreateFileStore as file_store


class mkRunProcessLocal_CreateFileStore_TestCase(unittest.TestCase):
    def test_get_source_and_target(self):
        source, by_hash_file = file_store.get_source_and_target(
            "files.c", "hash", "/", "/"
        )
        self.assertEqual(source, "/files.c")
        self.assertEqual(by_hash_file, "/hash.c")

        # Check result with: ls -U fileByHash/ | grep -vi "\.\(zip\|graphml\|yml\|i\|cil\|c\|h\|py\|sh\|Makefile\|makeall\|verdict\|md\|set\|xml\|prp\|bat\|txt\|README\|LICENSE\)\$"
        source, by_hash_file = file_store.get_source_and_target(
            "32_1_cilled_ok_nondet_linux-3.4-32_1-drivers--mtd--mtdoops.ko-ldv_main0_sequence_infinite_withcheck_stateful.cil.out.i",
            "hash",
            "/",
            "/",
        )
        self.assertEqual(
            source,
            "/32_1_cilled_ok_nondet_linux-3.4-32_1-drivers--mtd--mtdoops.ko-ldv_main0_sequence_infinite_withcheck_stateful.cil.out.i",
        )
        self.assertEqual(by_hash_file, "/hash.i")
