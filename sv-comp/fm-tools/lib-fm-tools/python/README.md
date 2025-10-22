<!--
This file is part of lib-fm-tools, a library for interacting with FM-Tools files:
https://gitlab.com/sosy-lab/benchmarking/fm-tools

SPDX-FileCopyrightText: 2024 Dirk Beyer <https://www.sosy-lab.org>

SPDX-License-Identifier: Apache-2.0
-->

# fm-tools

Parse, use, and modify fm-tools metadata. It is meant to be used with fm-data files from the [fm-tools repository](https://gitlab.com/sosy-lab/benchmarking/fm-tools).

## Description

This library provides convenient access to fm-data through a simple API.

The fm-data file format specifies the download location, maintainers, command-line options,
as well as other related information. An fm-data file for a specific tool is a YAML document with a
precisely defined set of keys (a schema for the metadata of formal-methods tools is available in the repository).

fm-actor can also download and unzip tools specified in the fm-tools repository.