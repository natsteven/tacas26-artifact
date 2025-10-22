# This file is part of lib-fm-tools, a library for interacting with FM-Tools files:
# https://gitlab.com/sosy-lab/benchmarking/fm-tools
#
# SPDX-FileCopyrightText: 2024 Dirk Beyer <https://www.sosy-lab.org>
#
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

import yaml

from fm_tools.competition_participation import (
    Competition,
    CompetitionTrack,
    JuryMember,
    Track,
)
from fm_tools.fmtool import FmTool
from fm_tools.fmtoolversion import FmToolVersion

TEST_FILES_DIR = Path(__file__).parent / "resources"
CPACHECKER_YAML = Path(TEST_FILES_DIR / "cpachecker.yml").read_text(encoding="utf-8")
GDART_YAML = Path(TEST_FILES_DIR / "gdart.yml").read_text(encoding="utf-8")
NACPA_YAML = Path(TEST_FILES_DIR / "nacpa.yml").read_text(encoding="utf-8")


def test_competition_participation_cpachecker():
    config = yaml.safe_load(CPACHECKER_YAML)
    fm_tool = FmTool(config)

    assert fm_tool.name == "CPAchecker"
    assert fm_tool.id == "cpachecker"
    assert fm_tool.input_languages == ["C"]

    assert fm_tool.competition_participations.sv_comp(2023).verification.tool_version == "2.2"

    assert fm_tool.competition_participations.sv_comp(2024).competes_in(Track.Verification)
    assert fm_tool.competition_participations.sv_comp(2024).competes_in(Track.Validation_Correct_1_0)
    assert fm_tool.competition_participations.sv_comp(2024).competes_in(Track.Any)

    assert fm_tool.competition_participations.sv_comp(2025).labels() == frozenset()
    assert fm_tool.competition_participations.sv_comp(2025).labels(track=Track.Verification) == frozenset()

    val_tracks = fm_tool.competition_participations.sv_comp(2025).validation_tracks

    jury_member = JuryMember(
        orcid="0000-0002-8172-3184",
        name="Marian Lingsch-Rosenfeld",
        institution="LMU Munich",
        country="Germany",
        url="https://www.sosy-lab.org/people/lingsch-rosenfeld/",
    )

    should_be = [
        CompetitionTrack(
            Track.Validation_Correct_1_0.value,
            "4.0-validation-correctness",
            jury_member,
            [],
        ),
        CompetitionTrack(
            Track.Validation_Correct_2_0.value,
            "4.0-validation-correctness",
            jury_member,
            [],
        ),
        CompetitionTrack(
            Track.Validation_Violation_1_0.value,
            "4.0-validation-violation",
            jury_member,
            [],
        ),
        CompetitionTrack(
            Track.Validation_Violation_2_0.value,
            "4.0-validation-violation",
            jury_member,
            [],
        ),
    ]

    assert sorted(val_tracks, key=lambda x: x.track) == sorted(should_be, key=lambda x: x.track)


def test_competition_participation_nacpa():
    config = yaml.safe_load(NACPA_YAML)
    fm_tool = FmTool(config)
    fm_tool_version = FmToolVersion(fm_tool, "1.0.0")

    assert fm_tool_version.get_tool_name_with_version() == "Nacpa-1.0.0"
    assert fm_tool.name == "Nacpa"
    assert fm_tool.id == "nacpa"
    assert fm_tool.input_languages == ["C"]

    assert fm_tool.competition_participations.sv_comp(2025).verification.tool_version == "1.0.0"

    assert fm_tool.competition_participations.sv_comp(2025).competes_in(Track.Verification)
    assert not fm_tool.competition_participations.sv_comp(2025).competes_in(Track.Validation_Correct_1_0)
    assert fm_tool.competition_participations.sv_comp(2025).competes_in(Track.Any)

    assert fm_tool.competition_participations.sv_comp(2025).verification.labels == ["meta_tool"]
    assert fm_tool.competition_participations.competition(Competition.SV_COMP, 2025).labels() == {"meta_tool"}
    assert fm_tool.competition_participations.competition(Competition.SV_COMP, 2025).labels(
        track=Track.Verification
    ) == {"meta_tool"}

    assert fm_tool.competition_participations.competition(Competition.TEST_COMP, 2025, error=False).labels() == set()


def test_competition_participation_gdart():
    config = yaml.safe_load(GDART_YAML)
    fm_tool = FmTool(config)

    assert fm_tool.id == "gdart"
    assert fm_tool.input_languages == ["Java"]

    assert fm_tool.competition_participations.sv_comp(2025).verification.tool_version == "svcomp25"

    assert fm_tool.competition_participations.sv_comp(2025).competes_in(Track.Verification)
    assert not fm_tool.competition_participations.sv_comp(2025).competes_in(Track.Validation_Correct_1_0)
    assert fm_tool.competition_participations.sv_comp(2025).competes_in(Track.Any)

    jury = JuryMember(
        name="Falk Howar",
        institution="TU Dortmund",
        country="Germany",
        url="https://falkhowar.de",
    )
    assert fm_tool.competition_participations.sv_comp(2025).verification.jury_member == jury
