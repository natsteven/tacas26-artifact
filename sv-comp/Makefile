# This file is part of the competition environment.
#
# SPDX-FileCopyrightText: 2011-2020 Dirk Beyer <https://www.sosy-lab.org>
#
# SPDX-License-Identifier: Apache-2.0

GIT_REPOS := sv-benchmarks fm-tools benchexec scripts coveriteam sv-witnesses
GIT_STORES := $(foreach g,$(GIT_REPOS),$(g)/.git)

init: $(GIT_STORES)

$(GIT_STORES):
	git submodule update --init $(@D)

update: | update-repos
	@echo "\n# Updating" bench-defs
	git checkout main
	git pull --rebase --prune

update-repos: $(foreach g,$(GIT_REPOS),$(g)/.update)

%/.update: %/.git
	@echo "\n# Updating" $(@D)
	cd $(@D) && \
		git checkout main || git checkout master || git checkout trunk && \
		git pull --rebase --prune || true

