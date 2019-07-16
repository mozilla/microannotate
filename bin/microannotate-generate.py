#!/usr/bin/env python
# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import argparse
import os

from microannotate import generator

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "repository_dir", help="Path to the input repository", action="store"
    )
    parser.add_argument(
        "repository_out_dir", help="Path to the output repository", action="store"
    )
    parser.add_argument(
        "--rev-start",
        help="Which revision to start with (0 by default)",
        action="store",
        default="0",
    )
    parser.add_argument(
        "--rev-end",
        help="Which revision to end with (tip by default)",
        action="store",
        default="tip",
    )
    parser.add_argument("--tokenize", action="store_true", default=True)
    parser.add_argument("--remove-comments", action="store_true", default=False)
    args = parser.parse_args()

    repo_out_dir = os.path.realpath(args.repository_out_dir)

    generator.generate(
        args.repository_dir,
        repo_out_dir,
        args.rev_start,
        args.rev_end,
        args.tokenize,
        args.remove_comments,
    )
