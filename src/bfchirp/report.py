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

"""Plain-text rendering of the analysis results.

Every table is written to be read without a manual: units are on the figures,
and each block ends with the one or two sentences needed to interpret it.
Nothing here computes anything — rendering stays separate from analysis so the
same results can be serialised to JSON instead.
"""

from __future__ import annotations

import numpy as np

from .chirp import EDGE_HZ, ChirpResult
from .log import FlightLog
from .noise import NoiseResult
from .step import StepResult

WIDTH = 78


def rule(char: str = "=", width: int = WIDTH) -> str:
    return char * width


def num(value, spec: str = "6.2f", absent: str = "  —") -> str:
    """Format a number, degrading to a dash rather than printing ``nan``."""
    if value is None:
        return absent
    try:
        return absent if not np.isfinite(value) else format(value, spec)
    except (TypeError, ValueError):
        return absent


def bar(fraction: float, width: int = 20) -> str:
    """A proportional bar; saturates rather than overflowing the column."""
    if not np.isfinite(fraction):
        return ""
    return "█" * max(0, min(width, int(round(fraction * width))))


# --------------------------------------------------------------------------
# Header
# --------------------------------------------------------------------------

def report_header(log: FlightLog, out=print) -> None:
    config = log.config
    out(rule())
    out(f"  {log.label}   —   {config.craft}")
    out(rule())
    out(f"  {config.firmware}")
    out(f"  board {config.board} · loop {config.loop_hz:.0f} Hz "
        f"· {config.motor_poles} poles")
    out(f"  log {log.fs:.0f} Hz (Nyquist {log.nyquist:.0f} Hz) "
        f"· {log.duration:.1f} s · {log.n} samples")

    pids = [config.get("rollPID"), config.get("pitchPID"), config.get("yawPID")]
    if any(pids):
        out(f"  PID   roll {pids[0]} · pitch {pids[1]} · yaw {pids[2]}")
    if config.get("ff_weight"):
        out(f"  FF {config.get('ff_weight')} · d_max {config.get('d_max')} "
            f"(gain {config.get('d_max_gain')})")

    gyro_lpf1 = config.get("gyro_lpf1_dyn_hz") or config.get("gyro_lpf1_static_hz")
    out(f"  gyro  lpf1 {gyro_lpf1} · lpf2 {config.get('gyro_lpf2_static_hz')}")
    out(f"  dterm lpf1 {config.get('dterm_lpf1_dyn_hz')} "
        f"· lpf2 {config.get('dterm_lpf2_static_hz')}")
    out(f"  notch {config.get('dyn_notch_count')}× q{config.get('dyn_notch_q')} "
        f"{config.get('dyn_notch_min_hz')}-{config.get('dyn_notch_max_hz')} Hz "
        f"| rpm filter {config.get('rpm_filter_harmonics')} harm. "
        f"from {config.get('rpm_filter_min_hz')} Hz")

    if log.nyquist < 900:
        out(f"  ! logged at {log.fs:.0f} Hz: nothing above {log.nyquist:.0f} Hz "
            f"is observable. Raise the logging rate to see motor harmonics.")
    out("")


# --------------------------------------------------------------------------
# Noise
# --------------------------------------------------------------------------

def report_noise(result: NoiseResult, out=print) -> None:
    out("GYRO NOISE — raw → filtered RMS per band (deg/s), attenuation in dB")
    out(rule("-"))

    if result.rpm:
        rpm = result.rpm
        out(f"  rotor {rpm['mean']:.0f} rpm "
            f"(p5 {rpm['p5']:.0f} · p95 {rpm['p95']:.0f} · max {rpm['max']:.0f})")
        harmonics = " · ".join(
            f"{name} {lo:.0f}-{hi:.0f} Hz" for name, (lo, hi) in rpm["harmonics"].items())
        out(f"  motor harmonics: {harmonics}")

    if not result.per_axis:
        out("  no raw/filtered gyro pair in this log "
            "(needs debug_mode = GYRO_SCALED or a gyroUnfilt field).")
        out("")
        return

    out("  axis   " + "".join(f"{f'{lo:.0f}-{hi:.0f} Hz':>17}" for lo, hi in result.bands))
    for name, entry in result.per_axis.items():
        line = f"  {name:<7}"
        for band in entry["bands"]:
            line += (f"{band['raw']:>7.2f}→{band['filtered']:<5.2f}"
                     f"({band['attenuation_db']:>+5.1f})")
        out(line)
        if entry["peaks_raw"]:
            out("         raw peaks: " + ", ".join(f"{f:.0f} Hz" for f in entry["peaks_raw"]))
        if entry["peaks_filtered"]:
            out("         survives filtering: "
                + ", ".join(f"{f:.0f} Hz" for f in entry["peaks_filtered"]))
        if "dterm_rms" in entry:
            out(f"         D term: RMS {entry['dterm_rms']:.1f} "
                f"· above 80 Hz {entry['dterm_hf']:.2f}")

    if result.motor:
        motor = result.motor
        out(f"  motors: median {motor['median']:.0f} · p99 {motor['p99']:.0f} "
            f"/ {motor['range'][1]:.0f} · RMS {motor['rms']:.0f} "
            f"· saturated {result.saturation_pct:.1f} % of the time")
        out("          noise reaching the ESCs: "
            + " · ".join(f"{b['lo']:.0f}-{b['hi']:.0f} Hz {b['rms']:.1f}"
                         for b in motor["bands"]))
    out("  A large attenuation is filtering you are paying latency for; a small")
    out("  raw figure in the same band means that filtering is buying little.")
    out("")


# --------------------------------------------------------------------------
# Step response
# --------------------------------------------------------------------------

def report_step(result: StepResult, out=print) -> None:
    out("STEP RESPONSE — Wiener deconvolution of setpoint into gyro")
    out(rule("-"))
    out(f"  {'axis':<7}{'rise':>10}{'overshoot':>12}{'delay':>9}"
        f"{'settle':>9}{'err/SP':>9}{'windows':>9}")

    for name, entry in result.per_axis.items():
        if not entry.get("ok"):
            out(f"  {name:<7}  not enough stick movement "
                f"({entry['windows']} usable windows)")
            continue
        out(f"  {name:<7}{entry['rise_ms']:>8.1f}ms{entry['overshoot_pct']:>11.1f}%"
            f"{entry['delay_ms']:>7.1f}ms{entry['settle']:>9.3f}"
            f"{entry['error_normalised']:>9.3f}{entry['windows']:>9}")

    out(f"  time resolution of this log: {result.quantisation_ms:.2f} ms per sample")
    if result.quantisation_ms > 1.0:
        out("  ! delays are quantised to that resolution — only compare them")
        out("    between logs recorded at the same rate.")
    out("  err/SP = RMS tracking error normalised by how hard the flight was flown,")
    out("  which is what makes two different flights comparable.")
    out("")


# --------------------------------------------------------------------------
# Chirp
# --------------------------------------------------------------------------

def report_chirp(result: ChirpResult, out=print) -> None:
    settings = result.settings
    amplitude = settings["amplitude"]

    out("FREQUENCY SWEEP — closed-loop response, setpoint into gyro")
    out(rule("-"))
    out(f"  {result.n_segments} sweeps · {settings['start_hz']:.1f} → "
        f"{settings['end_hz']:.1f} Hz in {settings['time_s']:.0f} s "
        f"· amplitude {amplitude['Roll']:.0f}/{amplitude['Pitch']:.0f}/"
        f"{amplitude['Yaw']:.0f} deg/s")

    lag, lead = settings["lag_hz"], settings["lead_hz"]
    if lead:
        out(f"  lead/lag compensator {lag:.0f} Hz / {lead:.0f} Hz → excitation floors "
            f"at {100 * lag / lead:.0f} % of nominal above the zero")
    out(f"  usable band {result.band[0]:.1f} → {result.band[1]:.1f} Hz "
        f"(below {EDGE_HZ} Hz the firmware attenuates the excitation itself)")
    out("")

    if not result.per_axis:
        out("  no axis carried a usable sweep.")
        out("")
        return

    out(f"  {'axis':<7}{'delay':>10}{'R²':>7}{'peak':>21}{'φ margin':>10}"
        f"{'gain top':>12}{'φ top':>8}")
    for name, entry in result.per_axis.items():
        peak = (f"flat (±{entry['span_db'] / 2:.2f} dB)" if entry["flat"]
                else f"{entry['peak_db']:+.2f} dB @ {entry['peak_hz']:.1f} Hz")
        margin = num(entry["phase_margin_deg"], "9.1f", "        —")
        out(f"  {name:<7}{entry['tau_ms']:>8.1f}ms{entry['tau_r2']:>7.3f}{peak:>21}"
            f"{margin}°{entry['gain_top_db']:>+10.2f}dB{entry['phase_top_deg']:>7.0f}°")

    out("  minimum coherence: "
        + " · ".join(f"{n} {e['coherence_min']:.3f}" for n, e in result.per_axis.items()))
    out("  Coherence below ~0.8 means the response there is not trustworthy —")
    out("  usually too little excitation, not a real feature of the craft.")
    out("")

    out("  Stability limit extrapolated from the fitted pure delay:")
    for name, entry in result.per_axis.items():
        f180 = entry["f180_hz"]
        if not np.isfinite(f180):
            continue
        covered = 100 * result.band[1] / f180
        warning = "   ! outside the sweep" if covered < 90 else ""
        out(f"    {name:<7} −180° near {f180:>5.0f} Hz — "
            f"{covered:>3.0f} % of the critical band was actually observed{warning}")
    out("    Optimistic by construction: filters and structural modes add phase")
    out("    beyond the measured band, so the real limit arrives earlier.")
    out("")

    _report_excitation(result, out)
    _report_motor_load(result, out)


def _report_excitation(result: ChirpResult, out) -> None:
    rows = result.excitation.get("rows")
    if not rows:
        return
    nominal = result.excitation["nominal"]
    out("  EXCITATION ACTUALLY INJECTED (roll)")
    for row in rows:
        percent = 100 * row["amplitude"] / nominal if nominal else float("nan")
        out(f"    {row['lo']:>6.2f}-{row['hi']:<6.2f} Hz  {row['amplitude']:>5.0f} deg/s"
            f"  {num(percent, '5.0f')} %  {bar(percent / 100)}")
    out(f"    configured nominal: {nominal:.0f} deg/s")
    out("    Never flat, and that is by design. A weak gain reading where the")
    out("    excitation is 15 % of nominal says little about the craft.")
    out("")


def _report_motor_load(result: ChirpResult, out) -> None:
    load = result.motor_load
    rows = load.get("rows")
    if not rows:
        return

    out("  MOTOR LOAD DURING THE SWEEP (amplitude of the swept component)")
    columns = [c for c in ("setpoint", "gyro", "P", "D", "F", "motor", "rpm")
               if c in rows[0]]
    out("    " + f"{'f (Hz)':>13}" + "".join(f"{c:>9}" for c in columns) + f"{'following':>16}")
    for row in rows:
        line = f"    {row['lo']:>5.1f}-{row['hi']:<7.1f}"
        for column in columns:
            line += num(row[column], "9.0f", "        —")
        line += num(row.get("following"), "11.1f", "          —") + " rpm/step"
        out(line)

    out(f"    motor median {load['motor_median']:.0f} · p99 {load['motor_p99']:.0f} "
        f"· headroom {load['headroom']:.0f} steps "
        f"· saturated {load['saturation_pct']:.2f} %")
    out("    'following' falling with frequency is the safety fact: past the rotor's")
    out("    bandwidth the command stops producing acceleration and becomes current")
    out("    ripple, so the low end of the sweep is its most demanding part.")
    if load.get("feedforward_active"):
        out("    ! FEEDFORWARD WAS ACTIVE during this sweep. Its output grows with")
        out("      frequency and the lead/lag does not bound it. Zero the F terms")
        # ff_weight is the blackbox header key, not a CLI setting: the settings
        # are the per-axis F gains. Naming the header key here sent people to a
        # 'set' command that does not exist.
        out("      (set f_roll / f_pitch / f_yaw = 0) before widening the sweep.")
    else:
        out("    feedforward is off: the precondition for widening the sweep is met.")
    out("")


# --------------------------------------------------------------------------
# JSON view
# --------------------------------------------------------------------------

def to_jsonable(value):
    """Convert results to plain JSON types, arrays included."""
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(v) for v in value]
    if isinstance(value, np.ndarray):
        return [to_jsonable(v) for v in value.tolist()]
    if isinstance(value, (np.floating, float)):
        # JSON has no NaN; null round-trips through every parser.
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    return value
