#!/bin/bash

# This file is part of lib-fm-tools, a library for interacting with FM-Tools files:
# https://gitlab.com/sosy-lab/benchmarking/fm-tools
#
# SPDX-FileCopyrightText: 2024 Dirk Beyer <https://www.sosy-lab.org>
#
# SPDX-License-Identifier: Apache-2.0

# Guide to use this script:
# 1. version as a parameter. It should be new, i.e, different than the one in the init file.
#    This is automatically updated in the init file.
# 2. Update the change log with the contents of this version.
# 3. There should be no local changes. Either commit or stash them.

set -e

if [ -z "$1" ]; then
  echo "Please specify to-be-released version as parameter."
  exit 1
fi

OLD_VERSION="$(hatch version)"
VERSION="$1"
if [ $(expr match "$VERSION" ".*dev") -gt 0 ]; then
  echo "Cannot release development version."
  exit 1
fi
if [ "$VERSION" = "$OLD_VERSION" ]; then
  echo "Version already exists."
  exit 1
fi
if [ ! -z "$(git status -uno -s)" ]; then
  echo "Cannot release with local changes, please stash them."
  exit 1
fi

# Prepare files with new version number
hatch version "$VERSION"
git commit src/fm_tools/__init__.py -m "Release $VERSION"

git tag -s "lib-py-$VERSION" -m "Release of lib-fm-tool python $VERSION"

git push --tags

read -p "Please enter next version number:  " -r
hatch version "$REPLY"
git commit src/fm_tools/__init__.py -m "Prepare version number for next development cycle."

git push
echo
