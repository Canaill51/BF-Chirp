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

"""Locating and driving ``blackbox_decode``."""

from __future__ import annotations

import glob
import os
import shutil
import subprocess

from .log import Config, FlightLog

#: Places ``blackbox_decode`` commonly lives. PIDtoolbox ships one.
DECODER_CANDIDATES = (
    "~/.local/share/PIDtoolboxProV094/blackbox_decode",
    "~/.local/share/PIDtoolbox/blackbox_decode",
    "/usr/local/bin/blackbox_decode",
    "/usr/bin/blackbox_decode",
)


def find_decoder(explicit: str | None = None) -> str:
    """Return a usable ``blackbox_decode`` path, or raise with guidance."""
    if explicit:
        if not os.path.isfile(explicit):
            raise FileNotFoundError(f"decoder not found: {explicit}")
        return explicit
    for candidate in DECODER_CANDIDATES:
        path = os.path.expanduser(candidate)
        if os.path.isfile(path):
            return path
    found = shutil.which("blackbox_decode")
    if found:
        return found
    raise FileNotFoundError(
        "blackbox_decode not found. Pass --decoder PATH, or install "
        "blackbox-tools / PIDtoolbox."
    )


def decode(bbl_path: str, decoder: str, workdir: str) -> list[FlightLog]:
    """Decode one ``.bbl`` and return a :class:`FlightLog` per flight segment.

    A single ``.bbl`` often holds several arm/disarm segments; each becomes its
    own log with its own header.

    No unit conversion is requested from the decoder. This matters: passing
    ``--unit-rotation deg/s`` converts ``gyroADC`` but leaves ``gyroUnfilt``
    in raw units, and the two silently stop being comparable — which is
    precisely the comparison the noise analysis rests on.
    """
    stem = os.path.splitext(os.path.basename(bbl_path))[0]
    out_dir = os.path.join(workdir, stem)
    os.makedirs(out_dir, exist_ok=True)

    result = subprocess.run(
        [decoder, "--save-headers", "--output-dir", out_dir, bbl_path],
        capture_output=True, text=True,
    )
    csvs = sorted(
        p for p in glob.glob(os.path.join(out_dir, "*.csv"))
        if not p.endswith(".headers.csv")
    )
    if not csvs:
        raise RuntimeError(
            f"could not decode {bbl_path}\n{result.stderr[:400] or result.stdout[:400]}"
        )

    logs = []
    for csv_path in csvs:
        header_path = csv_path[:-4] + ".headers.csv"
        config = Config.from_csv(header_path) if os.path.exists(header_path) else Config()
        index = os.path.basename(csv_path)[:-4].rsplit(".", 1)[-1]
        label = stem if len(csvs) == 1 else f"{stem}#{index}"
        logs.append(FlightLog(csv_path, config, label))
    return logs
