#!/bin/bash

# This file is part of fm-tools:
# https://gitlab.com/sosy-lab/benchmarking/fm-tools
# (The script was copied from git@gitlab.ifi.lmu.de:sosy-lab/admin/tex.git)
# SPDX-FileCopyrightText: 2018-2024 Dirk Beyer <https://www.sosy-lab.org>
#
# SPDX-License-Identifier: Apache-2.0

# Explain to the user where we are:
echo "CI_PROJECT_PATH: $CI_PROJECT_PATH"
echo "CI_MERGE_REQUEST_SOURCE_PROJECT_PATH: $CI_MERGE_REQUEST_SOURCE_PROJECT_PATH"
echo "CI_MERGE_REQUEST_SOURCE_BRANCH_NAME: $CI_MERGE_REQUEST_SOURCE_BRANCH_NAME"
if [[ "$SSH_PRIVATE_KEY_BASE64" != "" ]]; then
  echo "SSH_PRIVATE_KEY_BASE64 is set."
fi

set -e # exit with nonzero exit code if anything fails
set -x # show run commands

REPO_DIR=pages
BRANCH_NAME=pages

rm -rf "$REPO_DIR" || true
cp -r website "$REPO_DIR"

# we need to tell git who we are
git config --global user.name "${GIT_NAME}"
git config --global user.email "${GIT_EMAIL}"

cd "$REPO_DIR"
git init

# The first and only commit to this new Git repo contains all the
# files present with the commit message "Deploy to Pages".
git add .
git commit -m "Deploy to Pages"

# Setup for pushing to the repository:
eval "$(ssh-agent -s)"
echo "$SSH_PRIVATE_KEY_BASE64" | base64 -d | ssh-add -
mkdir -p ~/.ssh
chmod 700 ~/.ssh
cp "$SSH_KNOWN_HOSTS" ~/.ssh/known_hosts
chmod 644 ~/.ssh/known_hosts

# Force push from the current repo's HEAD to the remote
# repo's pages branch. (All previous history on the branch
# will be lost, since we are overwriting it.)
git push --ipv4 --force --quiet "git@gitlab.com:sosy-lab/benchmarking/fm-tools.git" HEAD:"$BRANCH_NAME"
