# This file is part of lib-fm-tools, a library for interacting with FM-Tools files:
# https://gitlab.com/sosy-lab/benchmarking/fm-tools
#
# SPDX-FileCopyrightText: 2024 Dirk Beyer <https://www.sosy-lab.org>
#
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

import pytest

from fm_tools.competition_participation import Competition, Track
from fm_tools.fmtoolscatalog import FmToolsCatalog


def test_get_participation_nonexisting_tool():
    fm_tools_catalog = FmToolsCatalog(Path(__file__).parent / "resources")
    with pytest.raises(KeyError, match="cpacheckerX"):
        fm_tools_catalog["cpacheckerX"]


def test_get_participation_nonparticipating_tool():
    fm_tools_catalog = FmToolsCatalog(Path(__file__).parent / "resources")
    with pytest.raises(ValueError, match="Test-Comp 2024"):
        fm_tools_catalog["cpachecker"].competition_participations.competition(Competition.TEST_COMP, 2024)


def test_get_participation_nonparticipating_tool_pass():
    fm_tools_catalog = FmToolsCatalog(Path(__file__).parent / "resources")
    fm_tools_catalog["cpachecker"].competition_participations.competition(Competition.TEST_COMP, 2024, error=False)


def test_get_participation_labels_cpachecker_none():
    fm_tools_catalog = FmToolsCatalog(Path(__file__).parent / "resources")
    tool = "cpachecker"
    competition_name = Competition.SV_COMP
    competition_year = 2024
    track_list = fm_tools_catalog["cpachecker"].competition_participations.competition(
        competition_name, competition_year
    )
    assert len(track_list) > 0, f"Tool '{tool}' does not participate in '{competition_name}', '{competition_year}'."
    assert len(track_list.labels(Track.Verification)) == 0


def test_get_participation_labels_cpachecker_wrong_track():
    fm_tools_catalog = FmToolsCatalog(Path(__file__).parent / "resources")
    track_list = fm_tools_catalog["cpachecker"].competition_participations.competition(Competition.SV_COMP, 2024)
    with pytest.raises(KeyError):
        track_list.labels(Track.Test_Generation)
