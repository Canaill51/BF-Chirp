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

"""Rendering and the command-line entry point."""

import json

import numpy as np
import pytest

from bfchirp.chirp import analyse_chirp
from bfchirp.cli import main
from bfchirp.noise import analyse_noise
from bfchirp.report import bar, num, report_chirp, report_header, to_jsonable


def render(function, *args) -> str:
    lines: list[str] = []
    function(*args, lines.append)
    return "\n".join(lines)


def test_reports_never_print_raw_nan(chirp_log):
    text = render(report_header, chirp_log) + render(report_chirp, analyse_chirp(chirp_log))
    assert "nan" not in text.lower()
    assert "TestCraft" in text


def test_chirp_report_states_the_measured_band_and_load(chirp_log):
    text = render(report_chirp, analyse_chirp(chirp_log))
    assert "FREQUENCY SWEEP" in text
    assert "EXCITATION ACTUALLY INJECTED" in text
    assert "MOTOR LOAD DURING THE SWEEP" in text
    assert "feedforward is off" in text


def test_num_and_bar_degrade_instead_of_failing():
    assert num(float("nan")).strip() == "—"
    assert num(None).strip() == "—"
    assert num(1.5, "4.1f") == " 1.5"
    assert bar(float("nan")) == ""
    assert bar(2.0, width=10) == "█" * 10       # saturates, never overflows
    assert bar(0.5, width=10) == "█" * 5


def test_jsonable_replaces_nan_with_null_and_unwraps_arrays():
    payload = to_jsonable({"a": np.array([1.0, np.nan]), "b": np.float64(2.0),
                           "c": np.bool_(True), "d": (np.int64(3),)})
    assert json.loads(json.dumps(payload)) == {"a": [1.0, None], "b": 2.0,
                                               "c": True, "d": [3]}


def test_cli_runs_end_to_end_and_writes_json(chirp_log, tmp_path, capsys):
    out = tmp_path / "result.json"
    assert main([chirp_log.path, "--json", str(out)]) == 0
    printed = capsys.readouterr().out
    assert "FREQUENCY SWEEP" in printed and "GYRO NOISE" in printed

    payload = json.loads(out.read_text())
    entry = payload["chirp"]
    assert entry["craft"] == "TestCraft"
    assert entry["chirp"]["per_axis"]["Roll"]["tau_ms"] > 0
    assert len(entry["chirp"]["per_axis"]["Roll"]["f"]) > 10


def test_cli_only_selects_a_subset(noise_log, capsys):
    assert main([noise_log.path, "--only", "noise"]) == 0
    printed = capsys.readouterr().out
    assert "GYRO NOISE" in printed
    assert "STEP RESPONSE" not in printed


def test_cli_says_so_when_a_log_has_no_sweep(noise_log, capsys):
    assert main([noise_log.path, "--only", "chirp"]) == 0
    assert "no chirp sweep in this log" in capsys.readouterr().out


def test_cli_rejects_an_unknown_analysis(noise_log, capsys):
    assert main([noise_log.path, "--only", "banana"]) == 2
    assert "unknown analysis" in capsys.readouterr().err


def test_cli_reports_a_missing_file_without_crashing(tmp_path, capsys):
    assert main([str(tmp_path / "absent.csv")]) == 1
    assert "absent.csv" in capsys.readouterr().err


def test_cli_expands_a_directory(chirp_log, capsys):
    directory = str(chirp_log.path.rsplit("/", 1)[0])
    assert main([directory, "--only", "noise"]) == 0
    assert "GYRO NOISE" in capsys.readouterr().out


def test_cli_needs_at_least_one_log():
    with pytest.raises(SystemExit):
        main([])
