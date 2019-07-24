# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import re
import socket

import pygit2

ORIGINAL_COMMIT_REGEX = re.compile("UltraBlame original commit: ([0-9a-f]{40})")


def get_original_hash(repo, rev):
    if pygit2.reference_is_valid_name(rev):
        commit = repo.lookup_reference(rev).peel()
    else:
        commit = repo[rev]

    return ORIGINAL_COMMIT_REGEX.search(commit.message).group(1)


def get_commit_mapping(repo_path):
    transformed_to_original = {}
    original_to_transformed = {}

    repo = pygit2.Repository(repo_path)
    for commit in repo.walk(
        repo.head.target, pygit2.GIT_SORT_TOPOLOGICAL | pygit2.GIT_SORT_REVERSE
    ):
        original_hash = get_original_hash(repo, commit.hex)
        transformed_to_original[commit.hex] = original_hash
        original_to_transformed[original_hash] = commit.hex

    return (transformed_to_original, original_to_transformed)


def get_free_tcp_port():
    tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp.bind(("", 0))
    addr, port = tcp.getsockname()
    tcp.close()
    return port
