#!/usr/bin/env python3

import unittest
import sys
from pathlib import Path

from . import utils

sys.path.append(
    str(
        Path(__file__).parent.parent.parent.resolve()
        / "fm-tools/lib-fm-tools/python/src"
    )
)
from fm_tools.fmtoolscatalog import FmToolsCatalog
from fm_tools.competition_participation import Competition, Track


class utils_TestCase(unittest.TestCase):
    def test_is_hors_concours_cbmc_true(self):
        fm_tools_catalog = FmToolsCatalog(
            Path(__file__).parent.parent / "test" / "test-data"
        )
        self.assertTrue(
            utils.is_hors_concours(
                fm_tools_catalog, "cbmc", 2025, Competition.SV_COMP, Track.Verification
            ),
        )

    def test_is_hors_concours_cbmc_false(self):
        fm_tools_catalog = FmToolsCatalog(
            Path(__file__).parent.parent / "test" / "test-data"
        )
        self.assertFalse(
            utils.is_hors_concours(
                fm_tools_catalog, "cbmc", 2023, Competition.SV_COMP, Track.Verification
            ),
        )

    def test_get_participation_labels_inactive_cbmc(self):
        fm_tools_catalog = FmToolsCatalog(
            Path(__file__).parent.parent / "test" / "test-data"
        )
        labels = utils.get_participation_labels(
            fm_tools_catalog, "cbmc", 2025, Competition.SV_COMP, Track.Verification
        )
        self.assertEqual(
            labels,
            set(["inactive"]),
        )

    def test_get_participation_labels_none_cbmc(self):
        fm_tools_catalog = FmToolsCatalog(
            Path(__file__).parent.parent / "test" / "test-data"
        )
        labels = utils.get_participation_labels(
            fm_tools_catalog, "cbmc", 2023, Competition.SV_COMP, Track.Verification
        )
        self.assertEqual(
            labels,
            set(),
        )

    def test_get_participation_labels_inactive_fshellwitness2test(self):
        fm_tools_catalog = FmToolsCatalog(
            Path(__file__).parent.parent / "test" / "test-data"
        )
        labels = utils.get_participation_labels(
            fm_tools_catalog,
            "fshell-witness2test",
            2025,
            Competition.SV_COMP,
            Track.Validation_Violation_1_0,
        )
        self.assertEqual(
            labels,
            set(["inactive"]),
        )
