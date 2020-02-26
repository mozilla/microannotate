#!/usr/bin/env python
# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import argparse

from microannotate import viewer

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "repository_dir", help="Path to the input repository", action="store"
    )
    parser.add_argument(
        "microannotated_repository_dir",
        help="Path to the microannotated repository",
        action="store",
    )
    parser.add_argument(
        "path", help="Path to the file in the repository", action="store"
    )
    parser.add_argument(
        "rev", help="Start annotating from this revision", action="store"
    )
    args = parser.parse_args()

    print(
        viewer.html(
            args.repository_dir, args.microannotated_repository_dir, args.rev, args.path
        )
    )
