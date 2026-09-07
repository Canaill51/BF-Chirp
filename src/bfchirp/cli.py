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

"""Command-line entry point."""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import tempfile

from . import __version__
from .chirp import analyse_chirp
from .decode import decode, find_decoder
from .log import Config, FlightLog
from .noise import analyse_noise
from .report import (report_chirp, report_header, report_noise, report_step,
                     to_jsonable)
from .step import analyse_step

ANALYSES = ("noise", "step", "chirp")


def open_csv(csv_path: str) -> FlightLog:
    """Load an already-decoded CSV, picking up its ``.headers.csv`` sidecar."""
    header_path = csv_path[:-4] + ".headers.csv"
    config = Config.from_csv(header_path) if os.path.exists(header_path) else Config()
    return FlightLog(csv_path, config, os.path.basename(csv_path)[:-4])


def collect(targets: list[str]) -> list[str]:
    """Expand directories into the logs they hold, keeping the order given."""
    paths: list[str] = []
    for target in targets:
        if os.path.isdir(target):
            found = sorted(glob.glob(os.path.join(target, "*.bbl")))
            found += sorted(p for p in glob.glob(os.path.join(target, "*.csv"))
                            if not p.endswith(".headers.csv"))
            if not found:
                print(f"! no .bbl or .csv in {target}", file=sys.stderr)
            paths.extend(found)
        else:
            paths.append(target)
    return paths


def load(path: str, decoder: str | None, workdir: str) -> list[FlightLog]:
    """Turn one path into flight logs, decoding a ``.bbl`` only when needed."""
    if path.lower().endswith(".csv"):
        return [open_csv(path)]
    return decode(path, find_decoder(decoder), workdir)


def analyse(log: FlightLog, wanted: set[str]) -> dict:
    """Run the requested analyses, skipping any the log cannot support."""
    results: dict = {}
    if "noise" in wanted:
        results["noise"] = analyse_noise(log)
    if "step" in wanted:
        results["step"] = analyse_step(log)
    # A chirp analysis on a log without a sweep would produce confident-looking
    # numbers from noise, so it is gated on the data, not on the request.
    if "chirp" in wanted and log.is_chirp:
        results["chirp"] = analyse_chirp(log)
    return results


def render(log: FlightLog, results: dict, wanted: set[str], out=print) -> None:
    report_header(log, out)
    if "noise" in results:
        report_noise(results["noise"], out)
    if "step" in results:
        report_step(results["step"], out)
    if "chirp" in results:
        report_chirp(results["chirp"], out)
    elif "chirp" in wanted:
        out("FREQUENCY SWEEP — no chirp sweep in this log.")
        out("  Set debug_mode = CHIRP and arm the sweep to record one.")
        out("")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bfchirp",
        description="Quantitative analysis of Betaflight blackbox logs: "
                    "noise, step response and chirp frequency identification.",
        epilog="Give it .bbl files, already-decoded .csv files, or directories "
               "holding either.",
    )
    parser.add_argument("logs", nargs="+", metavar="LOG",
                        help=".bbl / .csv file, or a directory of them")
    parser.add_argument("--only", metavar="LIST",
                        help=f"comma-separated subset of: {', '.join(ANALYSES)}")
    parser.add_argument("--decoder", metavar="PATH",
                        help="path to blackbox_decode (auto-detected otherwise)")
    parser.add_argument("--workdir", metavar="DIR",
                        help="where decoded CSVs are kept (a temp dir otherwise)")
    parser.add_argument("--json", metavar="PATH",
                        help="also write every result as JSON ('-' for stdout)")
    parser.add_argument("--segment", type=int, metavar="N",
                        help="analyse only flight segment N of each .bbl (1-based)")
    parser.add_argument("--version", action="version", version=f"bfchirp {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    wanted = set(ANALYSES)
    if args.only:
        wanted = {name.strip().lower() for name in args.only.split(",") if name.strip()}
        unknown = wanted - set(ANALYSES)
        if unknown:
            print(f"unknown analysis: {', '.join(sorted(unknown))}", file=sys.stderr)
            return 2

    paths = collect(args.logs)
    if not paths:
        print("nothing to analyse", file=sys.stderr)
        return 2

    # JSON goes to stdout only when asked for by name, so the text report can
    # still be piped without the two interleaving.
    to_stdout = args.json == "-"
    emit = (lambda line: None) if to_stdout else print
    payload: dict = {}
    failures = 0
    analysed = 0

    with tempfile.TemporaryDirectory(prefix="bfchirp-") as scratch:
        workdir = args.workdir or scratch
        if args.workdir:
            os.makedirs(workdir, exist_ok=True)

        for path in paths:
            try:
                logs = load(path, args.decoder, workdir)
            except (FileNotFoundError, RuntimeError, OSError) as error:
                print(f"! {os.path.basename(path)}: {error}", file=sys.stderr)
                failures += 1
                continue

            if args.segment is not None:
                if not 1 <= args.segment <= len(logs):
                    print(f"! {os.path.basename(path)}: no segment {args.segment} "
                          f"({len(logs)} available)", file=sys.stderr)
                    failures += 1
                    continue
                logs = [logs[args.segment - 1]]

            for log in logs:
                # Short segments are arm/disarm noise, not flights.
                if log.duration < 2.0:
                    print(f"! {log.label}: {log.duration:.1f} s, too short to analyse",
                          file=sys.stderr)
                    continue
                results = analyse(log, wanted)
                render(log, results, wanted, emit)
                analysed += 1
                if args.json:
                    payload[log.label] = {
                        "file": log.path,
                        "craft": log.config.craft,
                        "firmware": log.config.firmware,
                        "sample_rate_hz": log.fs,
                        "duration_s": log.duration,
                        **{name: to_jsonable(vars(result))
                           for name, result in results.items()},
                    }

    if args.json:
        text = json.dumps(payload, indent=2, ensure_ascii=False)
        if to_stdout:
            print(text)
        else:
            with open(args.json, "w", encoding="utf-8") as handle:
                handle.write(text + "\n")
            print(f"JSON written to {args.json}")

    # A partial run still delivers its reports; only a run that analysed
    # nothing at all is a failure.
    return 1 if failures and not analysed else 0


if __name__ == "__main__":
    raise SystemExit(main())
