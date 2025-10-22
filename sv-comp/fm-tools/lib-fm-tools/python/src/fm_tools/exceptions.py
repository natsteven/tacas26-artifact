# This file is part of lib-fm-tools, a library for interacting with FM-Tools files:
# https://gitlab.com/sosy-lab/benchmarking/fm-tools
#
# SPDX-FileCopyrightText: 2024 Dirk Beyer <https://www.sosy-lab.org>
#
# SPDX-License-Identifier: Apache-2.0


class FmDataException(Exception): ...


class ToolInfoNotResolvedError(FmDataException): ...


class DownloadUnsuccessfulException(FmDataException): ...


class InvalidDataException(FmDataException): ...


class UnsupportedDOIException(InvalidDataException): ...


class MissingKeysException(FmDataException): ...


class VersionConflictException(FmDataException): ...


class EmptyVersionException(VersionConflictException): ...
