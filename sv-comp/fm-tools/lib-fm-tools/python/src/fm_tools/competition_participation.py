# This file is part of lib-fm-tools, a library for interacting with FM-Tools files:
# https://gitlab.com/sosy-lab/benchmarking/fm-tools
#
# SPDX-FileCopyrightText: 2024 Dirk Beyer <https://www.sosy-lab.org>
#
# SPDX-License-Identifier: Apache-2.0

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, FrozenSet, Iterable, List, Tuple

if TYPE_CHECKING:
    from fm_tools.fmtool import FmTool


class Competition(Enum):
    SV_COMP = "SV-COMP"
    TEST_COMP = "Test-Comp"


def string_to_Competition(string: str) -> Competition:
    for elem in Competition:
        if elem.value == string:
            return elem
    raise ValueError(f"{string} is not a value for the 'Competition' enum")


class Track(Enum):
    Verification = "Verification"
    Test_Generation = "Test Generation"
    Validation_Correct_1_0 = "Validation of Correctness Witnesses 1.0"
    Validation_Violation_1_0 = "Validation of Violation Witnesses 1.0"
    Validation_Correct_2_0 = "Validation of Correctness Witnesses 2.0"
    Validation_Violation_2_0 = "Validation of Violation Witnesses 2.0"
    Test_Validation_Clang_Formatted = "Validation of Test Suites Clang Formatted"
    Test_Validation_GCC_Formatted = "Validation of Test Suites GCC Formatted"
    Test_Validation_Clang_Unformatted = "Validation of Test Suites Clang Unformatted"
    Test_Validation_GCC_Unformatted = "Validation of Test Suites GCC Unformatted"
    Any = "Any"
    AnyValidation = "Validation of"


@dataclass(frozen=True)
class JuryMember:
    orcid: str | None = None
    name: str | None = None
    institution: str | None = None
    country: str | None = None
    url: str | None = None


@dataclass(frozen=True)
class CompetitionTrack:
    track: str
    tool_version: str
    jury_member: JuryMember
    labels: Tuple[str, ...]


class TrackList:
    def __init__(self, tracks: Dict[str, CompetitionTrack]):
        self.tracks = tracks

    def __getattr__(self, item: str) -> CompetitionTrack:
        if item in {"__getstate__", "__setstate__"}:
            return object.__getattr__(self, item)  # type: ignore[return-value]

        try:
            return self.tracks[item]
        except KeyError:
            raise AttributeError(f"Track '{item}' not found") from KeyError

    @property
    def verification(self) -> CompetitionTrack:
        return self.tracks[Track.Verification.value]

    @property
    def validation_tracks(self) -> Iterable[CompetitionTrack]:
        return (track for track in self.tracks.values() if track.track.startswith(Track.AnyValidation.value))

    def competes_in(self, track: Track) -> bool:
        if track == Track.Any:
            return len(self.tracks) > 0

        if track == Track.AnyValidation:
            return any(track_name.startswith(track.value) for track_name in self.tracks)

        return track.value in self.tracks

    def __getitem__(self, key: str) -> CompetitionTrack:
        return self.tracks[key]

    def __iter__(self) -> Iterable[str]:
        return iter(self.tracks)

    def __len__(self) -> int:
        return len(self.tracks)

    def __contains__(self, item: str) -> bool:
        return item in self.tracks

    def labels(self, track: Track = Track.Any) -> FrozenSet[str]:
        if track == Track.Any:
            return frozenset(label for track in self.tracks.values() for label in track.labels)
        try:
            return frozenset(self[track.value].labels)
        except KeyError as e:
            raise KeyError(f"Tool does not participate in track '{track}'.") from e


class CompetitionParticipation:
    def __init__(self, data: "FmTool"):
        self.data = data
        self.competitions = self._parse_competitions(self.data._config["competition_participations"])

    def _parse_competitions(self, competition_data: List[dict[str, Any]]) -> Dict[str, TrackList]:
        competitions = {}
        for entry in competition_data:
            competition_name = entry["competition"]
            if competition_name not in competitions:
                competitions[competition_name] = {}
            jury_member = JuryMember(**entry["jury_member"])
            track = CompetitionTrack(
                entry["track"],
                entry["tool_version"],
                jury_member,
                entry.get("label", []),
            )
            competitions[competition_name][track.track] = track
        return {name: TrackList(tracks) for name, tracks in competitions.items()}

    def _competition_by_name(self, competition_name: str, error: bool) -> TrackList:
        try:
            return self.competitions[competition_name]
        except KeyError:
            if not error:
                return TrackList({})
            raise ValueError(f"{self.data.id} does not participate in competition {competition_name}.") from None

    def sv_comp(self, year: int, error=True) -> TrackList:
        """
        Get the tracks where the tool competes in SV-COMP for a specific year.

        :param year: The year of the SV-COMP competition.
        :param error: Whether to raise an error if the tool does not participate in SV-COMP.
                     If False, returns an empty TrackList instead.
        :return: A TrackList containing the competition tracks for SV-COMP in the given year.
        :raises ValueError: If the tool does not participate in SV-COMP for the given year and error is True.
        """
        competition_name = f"SV-COMP {year}"
        return self._competition_by_name(competition_name, error)

    def test_comp(self, year: int, error=True) -> TrackList:
        """
        Get the tracks where the tool competes in Test-Comp for a specific year.

        :param year: The year of the Test-Comp competition.
        :param error: Whether to raise an error if the tool does not participate in Test-Comp.
                    If False, returns an empty TrackList instead.
        :return: A TrackList containing the competition tracks for Test-Comp in the given year.
        :raises ValueError: If the tool does not participate in Test-Comp for the given year and error is True.
        """
        competition_name = f"Test-Comp {year}"
        return self._competition_by_name(competition_name, error)

    def competition(self, competition: Competition, year: int, error=True) -> TrackList:
        """
        Get the tracks where the tool competes for the given competition and year.
        If error is False, return an empty TrackList if the tool does not participate in the competition
        instead of raising a ValueError.

        :param competition: The competition to get the tracks for.
        :param year: The year of the competition.
        :param error: Whether to raise an error if the tool does not participate in the competition.
        :return: The tracks where the tool competes.
        :raises ValueError: If the tool does not participate in the competition and error is True.
        """
        if competition == Competition.SV_COMP:
            return self.sv_comp(year, error)
        elif competition == Competition.TEST_COMP:
            return self.test_comp(year, error)

        raise ValueError(f"Unknown competition {competition}") from None
