# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import collections
import os
import random
import subprocess

import hglib
import pygit2

from microannotate import annotatehelper, utils


def html(repository_dir, microannotated_repository_dir, rev, path):
    microannotated_repository_dir = os.path.realpath(microannotated_repository_dir)

    repo = pygit2.Repository(microannotated_repository_dir)

    proc = subprocess.run(
        ["git", "blame", "--porcelain", rev, path],
        cwd=microannotated_repository_dir,
        check=True,
        capture_output=True,
    )
    blame_output = proc.stdout.decode("utf-8")

    original_commit_hash = utils.get_original_hash(repo, rev)
    os.chdir(repository_dir)
    hg = hglib.open(".")
    original_file_content = hg.cat(
        [path.encode("ascii")], rev=original_commit_hash.encode("ascii")
    )

    current_line = 0
    lines = collections.defaultdict(list)

    start = -1
    prev_blame_line = None
    for blame_line in annotatehelper.parse_blame(repo, blame_output):
        new_start = original_file_content.find(
            blame_line.context.encode("utf-8"), start + 1
        )
        if start == -1:
            start = 0

        content = original_file_content[start:new_start].decode("utf-8")
        content_lines = content.splitlines()
        for i, line in enumerate(content_lines):
            lines[current_line].append((prev_blame_line, line))
            if i != len(content_lines) - 1:
                current_line += 1

        if content.endswith("\n"):
            current_line += 1

        start = new_start
        prev_blame_line = blame_line

    content = original_file_content[start:].decode("utf-8")
    content_lines = content.splitlines()
    for i, line in enumerate(content_lines):
        lines[current_line].append((prev_blame_line, line))
        if i != len(content_lines) - 1:
            current_line += 1

    html = """
    <html>
    <head>
    <title>Blame</title>
    </head>
    <body>
    <pre>
    """

    colors = {}
    for line_no, blame_info in lines.items():
        for prev_blame, content in blame_info:
            if prev_blame is None:
                continue

            colors[
                prev_blame.commit.commithash
            ] = f"#{hex(random.randint(0, 0xFFFFFF))[2:]}"

    for line_no, blame_info in lines.items():
        for prev_blame, content in blame_info:
            if prev_blame is None:
                html += f"{content}"
            else:
                commit_hash = prev_blame.commit.commithash
                html += f'<a href="{commit_hash}" style="color: {colors[commit_hash]};">{content}</a>'
        html += "\n"

    html += """
    </pre>
    </body>
    </html>
    """

    return html
