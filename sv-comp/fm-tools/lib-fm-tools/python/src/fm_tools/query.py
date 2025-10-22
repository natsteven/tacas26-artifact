# This file is part of lib-fm-tools, a library for interacting with FM-Tools files:
# https://gitlab.com/sosy-lab/benchmarking/fm-tools
#
# SPDX-FileCopyrightText: 2024 Dirk Beyer <https://www.sosy-lab.org>
#
# SPDX-License-Identifier: Apache-2.0

from typing import List

from fm_tools.competition_participation import Competition, Track
from fm_tools.fmtoolscatalog import FmToolsCatalog


class Query:
    """
    Queries concerning all of the fm-data files at once.
    """

    def __init__(
        self,
        fm_tools: FmToolsCatalog,
        competition: Competition,
        year: int,
        track: Track = Track.Any,
    ):
        self.fm_tools = fm_tools
        self.competition = competition
        self.track = track
        self.year = year

    def set_defaults(func):
        def wrapper(self, *args, competition=None, track=None, year=None, **kwargs):
            if competition is None:
                competition = self.competition
            if track is None:
                track = self.track
            if year is None:
                year = self.year
            return func(self, *args, competition=competition, track=track, year=year, **kwargs)

        return wrapper

    @set_defaults
    def verifiers(self, competition: Competition, year: int, track: Track) -> List[str]:
        verifiers_list = []

        for data in self.fm_tools:
            if data.competition_participations.competition(competition, year, error=False).competes_in(track):
                verifiers_list.append(data)

        return [verifier.id for verifier in verifiers_list]

    @set_defaults
    def validators(
        self,
        competition: Competition = None,
        year: int = None,
        track: Track = None,
    ) -> List[str]:
        validators_list = []

        for data in self.fm_tools:
            competition_participation = data.competition_participations.competition(competition, year, error=False)
            if not competition_participation.competes_in(Track.AnyValidation):
                continue

            for track in competition_participation.validation_tracks:
                validator_id = data.get("id")
                track_name = track.track
                combined = f"{validator_id} {track_name}".lower().replace(" ", "-").replace("validation-of", "validate")
                validators_list.append(combined)
        return validators_list
