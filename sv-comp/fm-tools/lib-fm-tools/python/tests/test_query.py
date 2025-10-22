# This file is part of lib-fm-tools, a library for interacting with FM-Tools files:
# https://gitlab.com/sosy-lab/benchmarking/fm-tools
#
# SPDX-FileCopyrightText: 2024 Dirk Beyer <https://www.sosy-lab.org>
#
# SPDX-License-Identifier: Apache-2.0

import subprocess
from pathlib import Path

import pytest

from fm_tools.fmtoolscatalog import FmToolsCatalog
from fm_tools.query import Competition, Track


@pytest.fixture(
    params=[
        (2025, Competition.SV_COMP, Track.Verification),
        (2025, Competition.TEST_COMP, Track.Test_Generation),
        (2024, Competition.SV_COMP, Track.Validation_Correct_1_0),
    ]
)
def setup_params(request):
    """Fixture to set up the base path and parameters."""
    fm_tools = FmToolsCatalog((Path(__file__).parent.parent.parent.parent / "data").resolve())
    competition = Competition.SV_COMP
    year, competition, track = request.param
    return fm_tools, competition, track, year


def test_fm_tools_basics(setup_params):
    """Test the basic functionality of fm_tools."""
    fm_tools, competition, track, year = setup_params

    assert fm_tools.base_dir.is_dir(), "Base directory must be a directory"
    assert len(fm_tools.data) > 0, "Data must be loaded"
    assert all([fm_data.id for fm_data in fm_tools]), "All fm_data files must have an id attribute"

    assert "cpachecker" in fm_tools, "cpachecker must be in the data"
    assert "schema" not in fm_tools, "schema must not be in the data"

    assert fm_tools.cpachecker.id == "cpachecker", "cpachecker must have the id cpachecker"

    assert fm_tools.get("cpachecker").id == "cpachecker", "get should return the same as attribute access"
    assert fm_tools["cpachecker"].id == "cpachecker", "getitem should return the same as attribute access"

    assert fm_tools.cpachecker == fm_tools.get("cpachecker"), "Attribute access and get should return the same object"
    assert fm_tools.cpachecker == fm_tools["cpachecker"], "Attribute access and getitem should return the same object"


def test_yq_and_query_verifiers_output(setup_params):
    """Test if yq and Query.verifiers produce the same output."""
    fm_tools, competition, track, year = setup_params

    base_path = fm_tools.base_dir
    # Run the yq command
    yq_command = (
        f"yq --raw-output --slurp 'map( "
        f'select( .competition_participations[]? | .competition=="{competition.value} {year}" '
        f'and .track=="{track.value}" ) ) | sort_by([.input_languages[0], .id]) [] .id\' '
        f"{base_path}/*.yml"
    )

    print(yq_command)

    result = subprocess.run(yq_command, shell=True, capture_output=True, text=True)

    assert result.returncode == 0, f"yq command failed with error: {result.stderr}"

    yq_output = result.stdout.strip().split("\n")

    assert len(yq_output) > 0, "Test Parameters must produce some output"

    # Use Query.verifiers to get the output
    query_output = fm_tools.query(competition=competition, track=track, year=year).verifiers()

    # Compare the outputs
    assert sorted(yq_output) == sorted(query_output), "Outputs from yq and Query.verifiers do not match."


def test_yq_and_query_validators_output(setup_params):
    """Test if yq and Query.validators produce the same output."""
    fm_tools, competition, track, year = setup_params

    base_path = fm_tools.base_dir
    # Run the yq command
    validation_prefix = "Validation"
    yq_command = (
        f"yq --raw-output --slurp 'map( "
        f'.id as $id  | .competition_participations[]? | select( .competition=="{competition.value} {year}" '
        f'and (.track | startswith("{validation_prefix}")) ) | [$id, .track] | join(" "'
        ') | ascii_downcase | gsub(" "; "-") | sub("validation-of"; "validate") ) []\' '
        f"{base_path}/*.yml"
    )

    result = subprocess.run(yq_command, shell=True, capture_output=True, text=True)

    assert result.returncode == 0, f"yq command failed with error: {result.stderr}"

    yq_output = result.stdout.strip().split("\n")
    assert len(yq_output) > 0, "Test Parameters must produce some output"

    # Use Query.validators to get the output
    query_output = fm_tools.query(competition=competition, track=track, year=year).validators()

    # Compare the outputs
    assert sorted(yq_output) == sorted(query_output), "Outputs from yq and Query.validators do not match."
