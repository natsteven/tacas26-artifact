#!/bin/bash

# Enable exit on error
set -euo pipefail

echo "Calculating files that were changed by the MR."
if [[ -n "${CI_PROJECT_PATH:-}" ]]; then
  echo "CI_PROJECT_PATH: ${CI_PROJECT_PATH:-}"
fi

if [[ -n "${CI_MERGE_REQUEST_DIFF_BASE_SHA:-}" ]]; then
  echo "GitLab CI pipeline for MR"
  echo "CI_MERGE_REQUEST_SOURCE_PROJECT_PATH: ${CI_MERGE_REQUEST_SOURCE_PROJECT_PATH:-}"
  echo "CI_MERGE_REQUEST_SOURCE_BRANCH_NAME: ${CI_MERGE_REQUEST_SOURCE_BRANCH_NAME:-}"
  echo "CI_MERGE_REQUEST_DIFF_BASE_SHA: ${CI_MERGE_REQUEST_DIFF_BASE_SHA:-}"

  if [[ -n "${CI_MERGE_REQUEST_SOURCE_BRANCH_SHA:-}" ]]; then
    echo "This is a merge-result pipeline."
    # The argument to pass to git-diff has to contain the two ends of the branch.
    # Illustration: 2023-11-12_dbeyer_diff-calculation.pdf
    DIFF_ARG="$CI_MERGE_REQUEST_DIFF_BASE_SHA..$CI_MERGE_REQUEST_SOURCE_BRANCH_SHA"
    echo "Fetch the source-branch commit (which is a parent of the current merge commit)."
    git fetch origin "$CI_MERGE_REQUEST_SOURCE_BRANCH_SHA"
  else
    echo "This is a merge-request pipeline."
    DIFF_ARG="$CI_MERGE_REQUEST_DIFF_BASE_SHA"
  fi

  # GitLab tells us exactly the origin of the branch, just make sure it is present locally.
  echo "Fetch the merge-base commit."
  git fetch origin "$CI_MERGE_REQUEST_DIFF_BASE_SHA"

else
  if [[ "${CI_PROJECT_PATH:-}" = sosy-lab/* ]]; then
    echo "GitLab CI pipeline (not for MR) in main repo"
    # We just compare against main branch after making sure it is present locally.
    TARGET_REPO=origin
    TARGET_BRANCH="$CI_DEFAULT_BRANCH"

  elif [[ -n "${CI_PROJECT_PATH:-}" ]]; then
    echo "GitLab CI pipeline (not for MR) in fork"
    # Compare against main branch of upstream project, but we need to fetch it first.
    git remote add upstream https://gitlab.com/sosy-lab/benchmarking/fm-tools.git || git remote set-url upstream https://gitlab.com/sosy-lab/benchmarking/fm-tools.git
    TARGET_REPO=upstream
    TARGET_BRANCH=main

  else
    echo "Not in GitLab CI"
    # We just compare against main branch after making sure it is present locally,
    # assuming that the user has a standard git checkout with "origin".
    TARGET_REPO=origin
    TARGET_BRANCH=main
  fi

  DIFF_ARG="$TARGET_REPO/$TARGET_BRANCH..."

  # In order to compute the merge base, git needs not only the relevant trees,
  # but also the history. Let's fetch 200 commits back from the tips of the
  # current branch the the comparison branch and hope this is enough.
  echo "Fetch the source history."
  git fetch --depth=200 origin HEAD
  echo "Fetch the target history."
  git fetch --depth=200 "$TARGET_REPO" "$TARGET_BRANCH"
fi

echo "Comparing for '$DIFF_ARG'."
CHANGED_YML_FILES=$(git diff --name-only --diff-filter=d "$DIFF_ARG" -- data/*.yml | { grep -v 'schema.yml' || true ; } )
echo "Changed YML files:"
echo "$CHANGED_YML_FILES"
