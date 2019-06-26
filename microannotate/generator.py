# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import concurrent.futures
import itertools
import os
import re

import hglib
import pygit2
from tqdm import tqdm

from microannotate import utils


class Commit:
    def __init__(self, node, parents, desc):
        self.node = node
        self.parents = parents
        self.desc = desc

    def __eq__(self, other):
        assert isinstance(other, Commit)
        return self.node == other.node

    def __hash__(self):
        return hash(self.node)


def _init(repo_dir):
    global HG
    os.chdir(repo_dir)
    HG = hglib.open(".")


def set_modified_files(commit):
    template = '{join(files,"|")}\\0{join(file_copies,"|")}\\0'
    args = hglib.util.cmdbuilder(
        b"log", template=template, rev=commit.node.encode("ascii")
    )
    x = HG.rawcommand(args)
    files_str, file_copies_str = x.split(b"\x00")[:-1]

    commit.file_copies = file_copies = {}
    for file_copy in file_copies_str.split(b"|"):
        if not file_copy:
            continue

        parts = file_copy.split(b" (")
        copied = parts[0]
        orig = parts[1][:-1]
        file_copies[orig] = copied

    commit.files = files_str.split(b"|")


SPLIT_WORD_REGEX = re.compile(rb"(\w+|{|}|\[|\]|\"|'|\(|\)|\\\\|\*|#|/)")


def convert(repo, commit):
    set_modified_files(commit)

    copy_target_paths = set(commit.file_copies.values())

    before_after_paths = []
    for path in commit.files:
        if path in commit.file_copies:
            before_after_paths.append((path, commit.file_copies[path]))
        elif path in copy_target_paths:
            pass
        else:
            before_after_paths.append((path, path))

    print(commit.node)

    index = repo.index

    for _, after_path in before_after_paths:
        _, ext = os.path.splitext(after_path)

        try:
            after = HG.cat([after_path], rev=commit.node)
        except hglib.error.CommandError as e:
            if b"no such file in rev" in e.err:
                # The file was removed.
                index.remove(after_path)
                continue
            else:
                raise

        after_path = after_path.decode("ascii")

        os.makedirs(
            os.path.dirname(os.path.join(repo.workdir, after_path)), exist_ok=True
        )

        with open(os.path.join(repo.workdir, after_path), "wb") as f:
            f.writelines(
                word.group(0) + b"\n" for word in SPLIT_WORD_REGEX.finditer(after)
            )

        index.add(after_path)

    # TODO: Support merges?
    if repo.head_is_unborn:
        parent = []
    else:
        parent = [repo.head.target]

    index.write()
    tree = index.write_tree()

    # TODO: Use hg author!
    author = pygit2.Signature("Marco Castelluccio", "mcastelluccio@mozilla.com")

    repo.create_commit(
        "HEAD",
        author,
        author,
        f"{commit.desc}\n\nUltraBlame original commit: {commit.node}",
        tree,
        parent,
    )


def hg_log(hg, revs):
    template = "{node}\\0{p1node}\\0{desc}\\0"

    args = hglib.util.cmdbuilder(
        b"log", template=template, rev=revs[0] + b":" + revs[-1]
    )
    x = hg.rawcommand(args)
    out = x.split(b"\x00")[:-1]

    revs = []
    for rev in hglib.util.grouper(template.count("\\0"), out):
        revs.append(
            Commit(
                node=rev[0].decode("ascii"),
                parents=rev[1].decode("ascii").split(" "),
                desc=rev[2].decode("utf-8"),
            )
        )

    return revs


def _hg_log(revs):
    return hg_log(HG, revs)


def get_revs(hg, rev_start=0, rev_end="tip"):
    print(f"Getting revs from {rev_start} to {rev_end}...")

    args = hglib.util.cmdbuilder(
        b"log",
        template="{node}\n",
        no_merges=True,
        branch="central",
        rev=f"{rev_start}:{rev_end}",
    )
    x = hg.rawcommand(args)
    return x.splitlines()


def generate(repo_dir, repo_out_dir, rev_start=0, rev_end="tip", limit=None):
    if os.path.exists(repo_out_dir):
        repo = pygit2.Repository(repo_out_dir)
        try:
            last_commit_hash = utils.get_original_hash(repo, "HEAD")
            rev_start = f"children({last_commit_hash})"
        except KeyError:
            pass
    else:
        os.makedirs(repo_out_dir)
        repo = pygit2.init_repository(repo_out_dir)

    with hglib.open(repo_dir) as hg:
        revs = get_revs(hg, rev_start, rev_end)

        assert (
            len(revs) > 0
        ), "There should definitely be more than 0 commits, something is wrong"

    if limit is not None:
        revs = revs[:limit]

    print(f"Mining {len(revs)} commits...")

    CHUNK_SIZE = 256
    revs_groups = [revs[i : (i + CHUNK_SIZE)] for i in range(0, len(revs), CHUNK_SIZE)]

    with concurrent.futures.ProcessPoolExecutor(
        initializer=_init, initargs=(repo_dir,)
    ) as executor:
        commits = executor.map(_hg_log, revs_groups, chunksize=20)
        commits = tqdm(commits, total=len(revs_groups))
        commits = list(itertools.chain.from_iterable(commits))

    commits_num = len(commits)

    print(f"Converting {commits_num} commits...")

    cwd = os.getcwd()

    with open("errors.txt", "a", buffering=1) as f:
        _init(repo_dir)
        for commit in tqdm(commits):
            try:
                convert(repo, commit)
            except Exception:
                f.write(f"{commit.node} - {commit.parents}\n")

    os.chdir(cwd)
