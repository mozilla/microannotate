# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import os
import subprocess

import hglib
import pygit2
import pytest

from microannotate import generator, utils


@pytest.fixture
def fake_hg_repo(tmpdir):
    tmp_path = tmpdir.strpath
    dest = os.path.join(tmp_path, "repos")
    local = os.path.join(dest, "local")
    os.makedirs(local)
    hglib.init(local)

    os.environ["USER"] = "app"
    hg = hglib.open(local)

    hg.branch(b"central")

    yield hg, local

    hg.close()


def add_file(hg, repo_dir, name, contents):
    path = os.path.join(repo_dir, name)

    with open(path, "w") as f:
        f.write(contents)

    hg.add(files=[bytes(path, "ascii")])


def remove_file(hg, repo_dir, name):
    path = os.path.join(repo_dir, name)

    hg.remove(files=[bytes(path, "ascii")])


def commit(hg):
    commit_message = "Commit {}".format(
        " ".join([elem.decode("ascii") for status in hg.status() for elem in status])
    )

    i, revision = hg.commit(message=commit_message, user="Moz Illa <milla@mozilla.org>")

    return str(revision, "ascii")


def test_generate_tokenized(fake_hg_repo, tmpdir):
    hg, local = fake_hg_repo

    git_repo = os.path.join(tmpdir.strpath, "repo")

    add_file(
        hg,
        local,
        "file.cpp",
        """#include <iostream>

/* main */
int main() {
    return 0;
}""",
    )
    revision1 = commit(hg)

    add_file(
        hg,
        local,
        "file.cpp",
        """#include <iostream>

/* main */
int main() {
    cout << "Hello, world!";
    return 0;
}""",
    )
    add_file(
        hg,
        local,
        "file.jsm",
        """function ciao(str) {
  // Comment one
  console.log(str);
}""",
    )
    revision2 = commit(hg)

    generator.generate(
        local,
        git_repo,
        rev_start=0,
        rev_end="tip",
        limit=None,
        tokenize=True,
        remove_comments=False,
    )

    repo = pygit2.Repository(git_repo)
    commits = list(
        repo.walk(
            repo.head.target, pygit2.GIT_SORT_TOPOLOGICAL | pygit2.GIT_SORT_REVERSE
        )
    )

    assert (
        commits[0].message
        == f"""Commit A file.cpp

UltraBlame original commit: {revision1}"""
    )

    assert (
        commits[1].message
        == f"""Commit M file.cpp A file.jsm

UltraBlame original commit: {revision2}"""
    )

    with open(os.path.join(git_repo, "file.cpp"), "r") as f:
        cpp_file = f.read()
        assert (
            cpp_file
            == """#
include
<
iostream
>
/
*
main
*
/
int
main
(
)
{
cout
<
<
"
Hello
world
!
"
;
return
0
;
}
"""
        )

    with open(os.path.join(git_repo, "file.jsm"), "r") as f:
        js_file = f.read()
        assert (
            js_file
            == """function
ciao
(
str
)
{
/
/
Comment
one
console
.
log
(
str
)
;
}
"""
        )

    assert utils.get_original_hash(repo, "HEAD") == revision2
    assert utils.get_original_hash(repo, commits[0].hex) == revision1
    assert utils.get_original_hash(repo, commits[1].hex) == revision2
    transformed_to_original, original_to_transformed = utils.get_commit_mapping(
        git_repo
    )
    assert transformed_to_original[commits[0].hex] == revision1
    assert transformed_to_original[commits[1].hex] == revision2
    assert original_to_transformed[revision1] == commits[0].hex
    assert original_to_transformed[revision2] == commits[1].hex


def test_generate_progressive(fake_hg_repo, tmpdir):
    hg, local = fake_hg_repo

    git_repo = os.path.join(tmpdir.strpath, "repo")

    add_file(
        hg,
        local,
        "file.cpp",
        """#include <iostream>

/* main */
int main() {
    return 0;
}""",
    )
    revision1 = commit(hg)

    add_file(
        hg,
        local,
        "file.cpp",
        """#include <iostream>

/* main */
int main() {
    cout << "Hello, world!";
    return 0;
}""",
    )
    add_file(
        hg,
        local,
        "file.jsm",
        """function ciao(str) {
  // Comment one
  console.log(str);
}""",
    )
    revision2 = commit(hg)

    generator.generate(
        local,
        git_repo,
        rev_start=0,
        rev_end=revision1,
        limit=None,
        tokenize=True,
        remove_comments=False,
    )

    repo = pygit2.Repository(git_repo)
    commits = list(
        repo.walk(
            repo.head.target, pygit2.GIT_SORT_TOPOLOGICAL | pygit2.GIT_SORT_REVERSE
        )
    )

    assert len(commits) == 1

    assert (
        commits[0].message
        == f"""Commit A file.cpp

UltraBlame original commit: {revision1}"""
    )

    with open(os.path.join(git_repo, "file.cpp"), "r") as f:
        cpp_file = f.read()
        assert (
            cpp_file
            == """#
include
<
iostream
>
/
*
main
*
/
int
main
(
)
{
return
0
;
}
"""
        )

    assert not os.path.exists(os.path.join(git_repo, "file.jsm"))

    generator.generate(
        local,
        git_repo,
        rev_start=0,
        rev_end="tip",
        limit=None,
        tokenize=True,
        remove_comments=False,
    )

    repo = pygit2.Repository(git_repo)
    commits = list(
        repo.walk(
            repo.head.target, pygit2.GIT_SORT_TOPOLOGICAL | pygit2.GIT_SORT_REVERSE
        )
    )

    assert len(commits) == 2

    assert (
        commits[0].message
        == f"""Commit A file.cpp

UltraBlame original commit: {revision1}"""
    )

    assert (
        commits[1].message
        == f"""Commit M file.cpp A file.jsm

UltraBlame original commit: {revision2}"""
    )

    with open(os.path.join(git_repo, "file.cpp"), "r") as f:
        cpp_file = f.read()
        assert (
            cpp_file
            == """#
include
<
iostream
>
/
*
main
*
/
int
main
(
)
{
cout
<
<
"
Hello
world
!
"
;
return
0
;
}
"""
        )

    with open(os.path.join(git_repo, "file.jsm"), "r") as f:
        js_file = f.read()
        assert (
            js_file
            == """function
ciao
(
str
)
{
/
/
Comment
one
console
.
log
(
str
)
;
}
"""
        )


def test_generate_comments_removed(fake_hg_repo, tmpdir):
    hg, local = fake_hg_repo

    git_repo = os.path.join(tmpdir.strpath, "repo")

    add_file(
        hg,
        local,
        "file.cpp",
        """#include <iostream>

/* main */
int main() {
    return 0;
}""",
    )
    revision1 = commit(hg)

    add_file(
        hg,
        local,
        "file.cpp",
        """#include <iostream>

/* main */
int main() {
    cout << "Hello, world!";
    return 0;
}""",
    )
    add_file(
        hg,
        local,
        "file.jsm",
        """function ciao(str) {
// Comment one
  console.log(str);
}""",
    )
    revision2 = commit(hg)

    generator.generate(
        local,
        git_repo,
        rev_start=0,
        rev_end="tip",
        limit=None,
        tokenize=False,
        remove_comments=True,
    )

    repo = pygit2.Repository(git_repo)
    commits = list(
        repo.walk(
            repo.head.target, pygit2.GIT_SORT_TOPOLOGICAL | pygit2.GIT_SORT_REVERSE
        )
    )

    assert (
        commits[0].message
        == f"""Commit A file.cpp

UltraBlame original commit: {revision1}"""
    )

    assert (
        commits[1].message
        == f"""Commit M file.cpp A file.jsm

UltraBlame original commit: {revision2}"""
    )

    with open(os.path.join(git_repo, "file.cpp"), "r") as f:
        cpp_file = f.read()
        assert (
            cpp_file
            == """#include <iostream>


int main() {
    cout << "Hello, world!";
    return 0;
}"""
        )

    with open(os.path.join(git_repo, "file.jsm"), "r") as f:
        js_file = f.read()
        assert (
            js_file
            == """function ciao(str) {

  console.log(str);
}"""
        )


def test_generate_tokenized_and_comments_removed(fake_hg_repo, tmpdir):
    hg, local = fake_hg_repo

    git_repo = os.path.join(tmpdir.strpath, "repo")

    add_file(
        hg,
        local,
        "file.cpp",
        """#include <iostream>

/* main */
int main() {
    return 0;
}""",
    )
    revision1 = commit(hg)

    add_file(
        hg,
        local,
        "file.cpp",
        """#include <iostream>

/* main */
int main() {
    cout << "Hello, world!";
    return 0;
}""",
    )
    add_file(
        hg,
        local,
        "file.jsm",
        """function ciao(str) {
// Comment one
  console.log(str);
}""",
    )
    revision2 = commit(hg)

    generator.generate(
        local,
        git_repo,
        rev_start=0,
        rev_end="tip",
        limit=None,
        tokenize=True,
        remove_comments=True,
    )

    repo = pygit2.Repository(git_repo)
    commits = list(
        repo.walk(
            repo.head.target, pygit2.GIT_SORT_TOPOLOGICAL | pygit2.GIT_SORT_REVERSE
        )
    )

    assert (
        commits[0].message
        == f"""Commit A file.cpp

UltraBlame original commit: {revision1}"""
    )

    assert (
        commits[1].message
        == f"""Commit M file.cpp A file.jsm

UltraBlame original commit: {revision2}"""
    )

    with open(os.path.join(git_repo, "file.cpp"), "r") as f:
        cpp_file = f.read()
        assert (
            cpp_file
            == """#
include
<
iostream
>
int
main
(
)
{
cout
<
<
"
Hello
world
!
"
;
return
0
;
}
"""
        )

    with open(os.path.join(git_repo, "file.jsm"), "r") as f:
        js_file = f.read()
        assert (
            js_file
            == """function
ciao
(
str
)
{
console
.
log
(
str
)
;
}
"""
        )


def test_generate_comments_removed_no_comments(fake_hg_repo, tmpdir):
    hg, local = fake_hg_repo

    git_repo = os.path.join(tmpdir.strpath, "repo")

    add_file(
        hg,
        local,
        "file.cpp",
        """#include <iostream>

int main() {
    return 0;
}""",
    )
    revision1 = commit(hg)

    generator.generate(
        local,
        git_repo,
        rev_start=0,
        rev_end="tip",
        limit=None,
        tokenize=False,
        remove_comments=True,
    )

    repo = pygit2.Repository(git_repo)
    commits = list(
        repo.walk(
            repo.head.target, pygit2.GIT_SORT_TOPOLOGICAL | pygit2.GIT_SORT_REVERSE
        )
    )

    assert (
        commits[0].message
        == f"""Commit A file.cpp

UltraBlame original commit: {revision1}"""
    )

    with open(os.path.join(git_repo, "file.cpp"), "r") as f:
        cpp_file = f.read()
        assert (
            cpp_file
            == """#include <iostream>

int main() {
    return 0;
}"""
        )


def test_generate_tokenized_and_comments_removed_no_comments(fake_hg_repo, tmpdir):
    hg, local = fake_hg_repo

    git_repo = os.path.join(tmpdir.strpath, "repo")

    add_file(
        hg,
        local,
        "file.cpp",
        """#include <iostream>

int main() {
    return 0;
}""",
    )
    revision1 = commit(hg)

    generator.generate(
        local,
        git_repo,
        rev_start=0,
        rev_end="tip",
        limit=None,
        tokenize=True,
        remove_comments=True,
    )

    repo = pygit2.Repository(git_repo)
    commits = list(
        repo.walk(
            repo.head.target, pygit2.GIT_SORT_TOPOLOGICAL | pygit2.GIT_SORT_REVERSE
        )
    )

    assert (
        commits[0].message
        == f"""Commit A file.cpp

UltraBlame original commit: {revision1}"""
    )

    with open(os.path.join(git_repo, "file.cpp"), "r") as f:
        cpp_file = f.read()
        assert (
            cpp_file
            == """#
include
<
iostream
>
int
main
(
)
{
return
0
;
}
"""
        )


def test_generate_comments_removed_unusupported_extension(fake_hg_repo, tmpdir):
    hg, local = fake_hg_repo

    git_repo = os.path.join(tmpdir.strpath, "repo")

    add_file(
        hg,
        local,
        "file.surely_unsupported",
        """#include <iostream>

/* main */
int main() {
    return 0;
}""",
    )
    revision1 = commit(hg)

    generator.generate(
        local,
        git_repo,
        rev_start=0,
        rev_end="tip",
        limit=None,
        tokenize=False,
        remove_comments=True,
    )

    repo = pygit2.Repository(git_repo)
    commits = list(
        repo.walk(
            repo.head.target, pygit2.GIT_SORT_TOPOLOGICAL | pygit2.GIT_SORT_REVERSE
        )
    )

    assert (
        commits[0].message
        == f"""Commit A file.surely_unsupported

UltraBlame original commit: {revision1}"""
    )

    with open(os.path.join(git_repo, "file.surely_unsupported"), "r") as f:
        cpp_file = f.read()
        assert (
            cpp_file
            == """#include <iostream>

/* main */
int main() {
    return 0;
}"""
        )


def test_generate_tokenized_and_comments_removed_unusupported_extension(
    fake_hg_repo, tmpdir
):
    hg, local = fake_hg_repo

    git_repo = os.path.join(tmpdir.strpath, "repo")

    add_file(
        hg,
        local,
        "file.surely_unsupported",
        """#include <iostream>

/* main */
int main() {
    return 0;
}""",
    )
    revision1 = commit(hg)

    generator.generate(
        local,
        git_repo,
        rev_start=0,
        rev_end="tip",
        limit=None,
        tokenize=True,
        remove_comments=True,
    )

    repo = pygit2.Repository(git_repo)
    commits = list(
        repo.walk(
            repo.head.target, pygit2.GIT_SORT_TOPOLOGICAL | pygit2.GIT_SORT_REVERSE
        )
    )

    assert (
        commits[0].message
        == f"""Commit A file.surely_unsupported

UltraBlame original commit: {revision1}"""
    )

    with open(os.path.join(git_repo, "file.surely_unsupported"), "r") as f:
        cpp_file = f.read()
        assert (
            cpp_file
            == """#
include
<
iostream
>
/
*
main
*
/
int
main
(
)
{
return
0
;
}
"""
        )


def test_generate_removed_file(fake_hg_repo, tmpdir):
    hg, local = fake_hg_repo

    git_repo = os.path.join(tmpdir.strpath, "repo")

    add_file(
        hg,
        local,
        "file.cpp",
        """#include <iostream>

/* main */
int main() {
    return 0;
}""",
    )
    revision1 = commit(hg)

    remove_file(hg, local, "file.cpp")
    revision2 = commit(hg)

    assert not os.path.exists(os.path.join(local, "file.cpp"))

    generator.generate(
        local,
        git_repo,
        rev_start=0,
        rev_end="tip",
        limit=None,
        tokenize=True,
        remove_comments=True,
    )

    repo = pygit2.Repository(git_repo)
    commits = list(
        repo.walk(
            repo.head.target, pygit2.GIT_SORT_TOPOLOGICAL | pygit2.GIT_SORT_REVERSE
        )
    )

    assert (
        commits[0].message
        == f"""Commit A file.cpp

UltraBlame original commit: {revision1}"""
    )

    assert (
        commits[1].message
        == f"""Commit R file.cpp

UltraBlame original commit: {revision2}"""
    )

    assert not os.path.exists(os.path.join(git_repo, "file.cpp"))

    proc = subprocess.run(
        ["git", "show", "HEAD"], cwd=git_repo, capture_output=True, check=True
    )
    assert b"diff --git a/file.cpp b/file.cpp\ndeleted file mode 100644" in proc.stdout


def test_generate_copied_and_moved_file(fake_hg_repo, tmpdir):
    hg, local = fake_hg_repo

    git_repo = os.path.join(tmpdir.strpath, "repo")

    add_file(
        hg,
        local,
        "file.cpp",
        """#include <iostream>

/* main */
int main() {
    return 0;
}""",
    )
    add_file(
        hg,
        local,
        "file2.cpp",
        """#include <stdio.h>

/* main2 */
void main() {
    return 42;
}""",
    )
    revision1 = commit(hg)

    hg.copy(
        bytes(os.path.join(local, "file.cpp"), "ascii"),
        bytes(os.path.join(local, "filecopy.cpp"), "ascii"),
    )
    revision2 = commit(hg)

    hg.move(
        bytes(os.path.join(local, "file2.cpp"), "ascii"),
        bytes(os.path.join(local, "file2move.cpp"), "ascii"),
    )
    revision3 = commit(hg)

    assert os.path.exists(os.path.join(local, "file.cpp"))
    assert os.path.exists(os.path.join(local, "filecopy.cpp"))
    assert not os.path.exists(os.path.join(local, "file2.cpp"))
    assert os.path.exists(os.path.join(local, "file2move.cpp"))

    generator.generate(
        local,
        git_repo,
        rev_start=0,
        rev_end="tip",
        limit=None,
        tokenize=False,
        remove_comments=True,
    )

    repo = pygit2.Repository(git_repo)
    commits = list(
        repo.walk(
            repo.head.target, pygit2.GIT_SORT_TOPOLOGICAL | pygit2.GIT_SORT_REVERSE
        )
    )

    assert (
        commits[0].message
        == f"""Commit A file.cpp A file2.cpp

UltraBlame original commit: {revision1}"""
    )

    assert (
        commits[1].message
        == f"""Commit A filecopy.cpp

UltraBlame original commit: {revision2}"""
    )

    assert (
        commits[2].message
        == f"""Commit A file2move.cpp R file2.cpp

UltraBlame original commit: {revision3}"""
    )

    with open(os.path.join(git_repo, "file.cpp"), "r") as f:
        cpp_file = f.read()
        assert (
            cpp_file
            == """#include <iostream>


int main() {
    return 0;
}"""
        )

    assert not os.path.exists(os.path.join(git_repo, "file2.cpp"))

    with open(os.path.join(git_repo, "filecopy.cpp"), "r") as f:
        cpp_file = f.read()
        assert (
            cpp_file
            == """#include <iostream>


int main() {
    return 0;
}"""
        )

    with open(os.path.join(git_repo, "file2move.cpp"), "r") as f:
        cpp_file = f.read()
        assert (
            cpp_file
            == """#include <stdio.h>


void main() {
    return 42;
}"""
        )


def test_generate_comments_removed_utf_char(fake_hg_repo, tmpdir):
    hg, local = fake_hg_repo

    git_repo = os.path.join(tmpdir.strpath, "repo")

    add_file(
        hg,
        local,
        "file.cpp",
        """#include <iostream>

/* Á main */
int main() {
    cout << "Á" << endl;
    return 0;
}""",
    )
    revision = commit(hg)

    generator.generate(
        local,
        git_repo,
        rev_start=0,
        rev_end="tip",
        limit=None,
        tokenize=False,
        remove_comments=True,
    )

    repo = pygit2.Repository(git_repo)
    commits = list(
        repo.walk(
            repo.head.target, pygit2.GIT_SORT_TOPOLOGICAL | pygit2.GIT_SORT_REVERSE
        )
    )

    assert (
        commits[0].message
        == f"""Commit A file.cpp

UltraBlame original commit: {revision}"""
    )

    with open(os.path.join(git_repo, "file.cpp"), "r") as f:
        cpp_file = f.read()
        assert (
            cpp_file
            == """#include <iostream>


int main() {
    cout << "Á" << endl;
    return 0;
}"""
        )


def test_generate_tokenized_operators(fake_hg_repo, tmpdir):
    hg, local = fake_hg_repo

    git_repo = os.path.join(tmpdir.strpath, "repo")

    add_file(
        hg,
        local,
        "file.cpp",
        """#include <iostream>

/* main */
int main() {
    if (ciao > 0 && ciao.obj <= 7 && ciao.obj->prova < 42 || !bo) {
      int x = ciao ? 1 : 2;
      return 1 + 1 * 41 + 0 / ~3 + 3 % 5 - x ^ 3;
    }
    return 0;
}""",
    )
    revision = commit(hg)

    generator.generate(
        local,
        git_repo,
        rev_start=0,
        rev_end="tip",
        limit=None,
        tokenize=True,
        remove_comments=False,
    )

    repo = pygit2.Repository(git_repo)
    commits = list(
        repo.walk(
            repo.head.target, pygit2.GIT_SORT_TOPOLOGICAL | pygit2.GIT_SORT_REVERSE
        )
    )

    assert (
        commits[0].message
        == f"""Commit A file.cpp

UltraBlame original commit: {revision}"""
    )

    with open(os.path.join(git_repo, "file.cpp"), "r") as f:
        cpp_file = f.read()
        assert (
            cpp_file
            == """#
include
<
iostream
>
/
*
main
*
/
int
main
(
)
{
if
(
ciao
>
0
&
&
ciao
.
obj
<
=
7
&
&
ciao
.
obj
-
>
prova
<
42
|
|
!
bo
)
{
int
x
=
ciao
?
1
:
2
;
return
1
+
1
*
41
+
0
/
~
3
+
3
%
5
-
x
^
3
;
}
return
0
;
}
"""
        )


def test_generate_tokenized_python(fake_hg_repo, tmpdir):
    hg, local = fake_hg_repo

    git_repo = os.path.join(tmpdir.strpath, "repo")

    add_file(
        hg,
        local,
        "file.py",
        """import sys

if sys:
    print("hello")
else:
    
    print("nope")
""",
    )
    revision = commit(hg)

    generator.generate(
        local,
        git_repo,
        rev_start=0,
        rev_end="tip",
        limit=None,
        tokenize=True,
        remove_comments=False,
    )

    repo = pygit2.Repository(git_repo)
    commits = list(
        repo.walk(
            repo.head.target, pygit2.GIT_SORT_TOPOLOGICAL | pygit2.GIT_SORT_REVERSE
        )
    )

    assert (
        commits[0].message
        == f"""Commit A file.py

UltraBlame original commit: {revision}"""
    )

    with open(os.path.join(git_repo, "file.py"), "r") as f:
        py_file = f.read()
        print(py_file)
        assert (
            py_file
            == """import
sys
if
sys
:
    
print
(
"
hello
"
)
else
:
    
print
(
"
nope
"
)
"""  # noqa
        )
