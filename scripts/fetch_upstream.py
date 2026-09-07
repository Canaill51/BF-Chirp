#!/usr/bin/env python3
# This file is part of bfchirp.
#
# Copyright (C) 2026 Cedric
#
# bfchirp is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option)
# any later version.
#
# bfchirp is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along
# with this program. If not, see <https://www.gnu.org/licenses/>.

"""Fetch the upstream sources that docs/reference/ is derived from.

None of their code is committed here — docs/reference/ contains our own prose,
citing upstream by path and commit SHA. Not for licence reasons (bfchirp is
GPL-3.0-or-later, as they are) but because a committed copy cannot tell you
when it has gone stale. This script pulls the real files into a gitignored
vendor/ directory so a claim can be checked against its source.

    python scripts/fetch_upstream.py            # download the pinned revisions
    python scripts/fetch_upstream.py --check    # report drift against master
    python scripts/fetch_upstream.py --list     # print the manifest as markdown

--check is the point of the exercise. A reference page that silently stops
matching the firmware is worse than no page at all, so drift is made visible
rather than left to be discovered by a wrong answer.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "scripts" / "upstream_sources.json"
VENDOR = ROOT / "vendor" / "upstream"

RAW = "https://raw.githubusercontent.com/{repo}/{ref}/{path}"


def load_manifest() -> dict:
    with MANIFEST.open(encoding="utf-8") as handle:
        return json.load(handle)["repos"]


def slug(url: str) -> str:
    """github.com/betaflight/betaflight -> betaflight/betaflight."""
    return url.removeprefix("https://github.com/")


def fetch(repo: str, ref: str, path: str) -> bytes:
    url = RAW.format(repo=repo, ref=ref, path=urllib.parse.quote(path))
    with urllib.request.urlopen(url, timeout=60) as response:
        return response.read()


def download(manifest: dict) -> int:
    failures = 0
    for name, spec in manifest.items():
        repo = slug(spec["url"])
        for path in spec["files"]:
            target = VENDOR / name / path
            try:
                blob = fetch(repo, spec["commit"], path)
            except urllib.error.HTTPError as exc:
                print(f"FAIL {name}/{path}: HTTP {exc.code}", file=sys.stderr)
                failures += 1
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(blob)
            print(f"  {len(blob):>8,} B  {name}/{path}")
    print(f"\nFetched into {VENDOR.relative_to(ROOT)}/ (gitignored).")
    return failures


def check(manifest: dict) -> int:
    """Compare each pinned file against the repository's default branch."""
    drifted = 0
    for name, spec in manifest.items():
        repo = slug(spec["url"])
        for path in spec["files"]:
            try:
                pinned = fetch(repo, spec["commit"], path)
                head = fetch(repo, "master", path)
            except urllib.error.HTTPError as exc:
                print(f"FAIL {name}/{path}: HTTP {exc.code}", file=sys.stderr)
                drifted += 1
                continue
            state = "same " if pinned == head else "DRIFT"
            if pinned != head:
                drifted += 1
            print(f"  [{state}] {name}/{path}")
    if drifted:
        print(
            f"\n{drifted} file(s) changed upstream since the pin. Re-read the"
            "\naffected docs/reference/ pages, then update the commit and"
            "\n'checked' date in scripts/upstream_sources.json."
        )
    else:
        print("\nNo drift: every pinned file still matches upstream master.")
    return drifted


def render(manifest: dict) -> int:
    print("| Upstream | Licence | Pinned commit | Checked | Files |")
    print("|---|---|---|---|---|")
    for name, spec in manifest.items():
        files = "<br>".join(f"`{path}`" for path in spec["files"])
        short = spec["commit"][:12]
        print(
            f"| [{name}]({spec['url']}) | {spec['license']} | "
            f"`{short}` | {spec['checked']} | {files} |"
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--check", action="store_true",
                       help="report files that changed upstream since the pin")
    group.add_argument("--list", action="store_true",
                       help="print the manifest as a markdown table")
    args = parser.parse_args(argv)

    manifest = load_manifest()
    if args.list:
        return render(manifest)
    if args.check:
        return 1 if check(manifest) else 0
    return 1 if download(manifest) else 0


if __name__ == "__main__":
    raise SystemExit(main())
