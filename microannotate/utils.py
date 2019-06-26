# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import re

import pygit2

ORIGINAL_COMMIT_REGEX = re.compile("UltraBlame original commit: ([0-9a-f]{40})")


def get_original_hash(repo, rev):
    if pygit2.reference_is_valid_name(rev):
        commit = repo.lookup_reference(rev).peel()
    else:
        commit = repo[rev]

    return ORIGINAL_COMMIT_REGEX.search(commit.message).group(1)
