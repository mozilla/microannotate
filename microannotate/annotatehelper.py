# -*- coding: utf-8 -*-
# Copyright 2016 The Chromium Authors. All rights reserved.
# This file comes from https://chromium.googlesource.com/chromium/tools/depot_tools.git/+/refs/heads/master/git_hyper_blame.py, with minor modifications.

import collections

from microannotate import utils


class Commit(object):
    """Info about a commit."""

    def __init__(self, commithash):
        self.commithash = commithash
        self.author = None
        self.author_mail = None
        self.author_time = None
        self.author_tz = None
        self.committer = None
        self.committer_mail = None
        self.committer_time = None
        self.committer_tz = None
        self.summary = None
        self.boundary = None
        self.previous = None
        self.filename = None

    def __repr__(self):  # pragma: no cover
        return "<Commit %s>" % self.commithash


BlameLine = collections.namedtuple(
    "BlameLine", "commit context lineno_then lineno_now modified"
)


def parse_blame(repo, blameoutput):
    """Parses the output of git blame -p into a data structure."""
    lines = blameoutput.split("\n")
    i = 0
    commits = {}

    while i < len(lines):
        # Read a commit line and parse it.
        line = lines[i]
        i += 1
        if not line.strip():
            continue
        commitline = line.split()
        commithash = utils.get_original_hash(repo, commitline[0])
        lineno_then = int(commitline[1])
        lineno_now = int(commitline[2])

        try:
            commit = commits[commithash]
        except KeyError:
            commit = Commit(commithash)
            commits[commithash] = commit

        # Read commit details until we find a context line.
        while i < len(lines):
            line = lines[i]
            i += 1
            if line.startswith("\t"):
                break

            try:
                key, value = line.split(" ", 1)
            except ValueError:
                key = line
                value = True
            setattr(commit, key.replace("-", "_"), value)

        context = line[1:]

        yield BlameLine(commit, context, lineno_then, lineno_now, False)
