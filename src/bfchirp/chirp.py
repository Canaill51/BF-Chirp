"""Frequency-response identification from Betaflight chirp sweeps.

Betaflight's chirp generator (PR #13105) adds an exponential frequency sweep
to ``currentPidSetpoint`` and logs its state on the debug channels:

===========  ==========================================  =================
channel      contents                                    scaling
===========  ==========================================  =================
``debug[0]`` sweep phase argument                         ``5000 * sinarg``
``debug[1]`` excited axis, ``-1`` when idle               raw axis index
``debug[2]`` instantaneous frequency                      ``10 * f`` (deci-Hz)
``debug[3]`` normalised excitation                        ``1000 * chirp``
===========  ==========================================  =================

The logged ``setpoint`` includes the injected chirp, so ``gyro / setpoint`` is
the true closed-loop response and any upstream shaping cancels out of it.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .log import AXES, FlightLog
from .spectral import fit_pure_delay, log_bins, phase_margin_from_peak

#: Below 1 Hz the firmware deliberately scales the excitation down
#: (``chirp.c``: ``if (fchirp < 1.0f) exc = fchirp * exc``) to stop the gyro
#: integrating too much angle, and an analysis window holds only a couple of
#: cycles there. Nothing below this is trustworthy.
EDGE_HZ = 1.5

#: A gain maximum sitting within this fraction of the band's low edge is an
#: edge artefact, not a resonance.
EDGE_FRACTION = 0.12

#: Peak-to-peak gain below this is a flat response with no identifiable peak.
FLAT_SPAN_DB = 1.0


@dataclass
class ChirpResult:
    band: tuple[float, float]
    per_axis: dict
    excitation: dict
    motor_load: dict
    n_segments: int
    settings: dict


def chirp_segments(log: FlightLog, min_seconds: float = 2.5) -> list[tuple[int, int, int]]:
    """Split the log into sweeps, returning ``(start, end, axis)`` for each."""
    freq = log["debug[2]"]
    axis = log["debug[1]"]
    active = freq > 0
    transitions = np.diff(active.astype(int))
    starts = np.where(transitions == 1)[0] + 1
    ends = np.where(transitions == -1)[0] + 1
    if active[0]:
        starts = np.r_[0, starts]
    if active[-1]:
        ends = np.r_[ends, len(active)]

    minimum = int(log.fs * min_seconds)
    return [
        (int(s), int(e), int(round(float(np.median(axis[s:e])))))
        for s, e in zip(starts, ends) if e - s >= minimum
    ]


def analyse_chirp(log: FlightLog, tail_s: float = 1.0,
                  window_s: float = 4.0) -> ChirpResult:
    """Estimate the closed-loop frequency response, averaged over all sweeps.

    Cross- and auto-spectra are accumulated across every sweep of an axis
    before the ratio is taken (``H = <Yx*> / <|X|^2>``), which is far steadier
    than averaging individual transfer-function estimates. Coherence comes
    from the same accumulators and is the measurement's own quality check.
    """
    fs = log.fs
    segments = chirp_segments(log)
    f_start, f_end = log.config.chirp_band_hz
    if f_end <= 0 and log.has("debug[2]"):
        f_end = float(np.max(log["debug[2]"]) / 10.0)
    f_top = min(f_end, log.nyquist * 0.95)

    length = int(fs * window_s)
    tail = int(fs * tail_s)
    per_axis: dict = {}

    for index, name in enumerate(AXES):
        sp_col, gyro_col = f"setpoint[{index}]", f"gyroADC[{index}]"
        if not (log.has(sp_col) and log.has(gyro_col)):
            continue

        cross = auto_in = auto_out = None
        used = 0
        for start, end, axis in segments:
            if axis != index:
                continue
            # The response keeps ringing after the sweep stops; include a tail.
            stop = min(end + tail, log.n)
            x = log[sp_col][start:stop].astype(float)
            y = log[gyro_col][start:stop].astype(float)
            if len(x) < length:
                pad = length - len(x)
                x = np.r_[x, np.zeros(pad)]
                y = np.r_[y, np.zeros(pad)]
            x, y = x[:length], y[:length]

            # Taper only the extreme edges: a full window would suppress the
            # low-frequency start of the sweep, which is where it lives.
            weight = np.ones(length)
            edge = np.hanning(128)
            weight[:64] *= edge[:64]
            weight[-64:] *= edge[64:]

            X = np.fft.rfft(x * weight)
            Y = np.fft.rfft(y * weight)
            cross = Y * np.conj(X) if cross is None else cross + Y * np.conj(X)
            auto_in = np.abs(X) ** 2 if auto_in is None else auto_in + np.abs(X) ** 2
            auto_out = np.abs(Y) ** 2 if auto_out is None else auto_out + np.abs(Y) ** 2
            used += 1

        if used == 0:
            continue

        freqs = np.fft.rfftfreq(length, 1 / fs)
        response = cross / auto_in
        coherence = np.abs(cross) ** 2 / (auto_in * auto_out)

        keep = (freqs >= max(EDGE_HZ, f_start)) & (freqs <= f_top)
        f_kept = freqs[keep]
        gain_db = 20 * np.log10(np.abs(response[keep]))
        phase_deg = np.degrees(np.unwrap(np.angle(response[keep])))
        coherence_kept = np.real(coherence[keep])

        tau_ms, r2 = fit_pure_delay(f_kept, phase_deg, 2.0, f_top * 0.95)

        peak_index = int(np.argmax(gain_db))
        log_span = np.log(f_kept[-1]) - np.log(f_kept[0])
        at_edge = (np.log(f_kept[peak_index]) - np.log(f_kept[0])) < EDGE_FRACTION * log_span
        span_db = float(np.max(gain_db) - np.min(gain_db))
        flat = bool(span_db < FLAT_SPAN_DB or at_edge)

        per_axis[name] = {
            "f": f_kept, "gain_db": gain_db, "phase_deg": phase_deg,
            "coherence": coherence_kept, "n_sweeps": used,
            "tau_ms": tau_ms, "tau_r2": r2,
            "peak_db": float(gain_db[peak_index]),
            "peak_hz": float(f_kept[peak_index]),
            "peak_is_edge_artefact": bool(at_edge),
            "flat": flat,
            "span_db": span_db,
            "phase_margin_deg": (float("nan") if at_edge
                                 else phase_margin_from_peak(float(gain_db[peak_index]))),
            "gain_top_db": float(gain_db[-1]),
            "phase_top_deg": float(phase_deg[-1]),
            "coherence_min": float(np.min(coherence_kept)),
            # Where a pure delay of tau would reach -180 degrees. Optimistic:
            # filters and structural modes add lag beyond the measured band,
            # so the real crossing comes earlier.
            "f180_hz": (float(0.5 / (tau_ms / 1000.0))
                        if np.isfinite(tau_ms) and tau_ms > 0 else float("nan")),
        }

    return ChirpResult(
        band=(max(EDGE_HZ, f_start), f_top),
        per_axis=per_axis,
        excitation=excitation_profile(log, segments),
        motor_load=motor_load(log, segments),
        n_segments=len(segments),
        settings={
            "start_hz": f_start, "end_hz": f_end,
            "time_s": log.config.num("chirp_time_seconds", 0),
            "amplitude": {a: log.config.num(f"chirp_amplitude_{a.lower()}", 0) for a in AXES},
            "lag_hz": log.config.num("chirp_lag_freq_hz", 0),
            "lead_hz": log.config.num("chirp_lead_freq_hz", 0),
        },
    )


def excitation_profile(log: FlightLog, segments, axis: int = 0, bins: int = 14) -> dict:
    """Amplitude actually injected into the loop, versus frequency.

    Never flat: the firmware attenuates below 1 Hz, then the lead/lag
    compensator rolls the amplitude off between its pole and zero. Knowing the
    real profile is what separates "the craft did nothing there" from "we
    barely asked it to".
    """
    column = f"setpoint[{axis}]"
    if not log.has(column) or not segments:
        return {}
    freq = log["debug[2]"] / 10.0
    setpoint = log[column]
    positive = freq[freq > 0]
    if positive.size == 0:
        return {}

    rows = []
    for lo, hi in log_bins(max(float(np.min(positive)), 0.05), float(np.max(freq)), bins):
        mask = np.zeros(log.n, dtype=bool)
        for start, end, seg_axis in segments:
            if seg_axis != axis:
                continue
            mask[start:end] |= (freq[start:end] >= lo) & (freq[start:end] < hi)
        if mask.sum() < 50:
            continue
        rows.append({"lo": lo, "hi": hi,
                     "amplitude": float(np.percentile(np.abs(setpoint[mask]), 97))})

    return {"rows": rows,
            "nominal": log.config.num(f"chirp_amplitude_{AXES[axis].lower()}", 0)}


def _amplitude_at_sweep(series: np.ndarray, start: int, end: int,
                        segment_freq: np.ndarray, fs: float,
                        mask: np.ndarray) -> float:
    """Amplitude of the component tracking the sweep's instantaneous frequency.

    The reference phase is rebuilt by integrating frequency *within one
    segment*. Accumulating it across segments would destroy the phase
    reference and produce meaningless amplitudes.
    """
    phase = 2 * np.pi * np.cumsum(segment_freq) / fs
    values = series[start:end][mask]
    if len(values) < 40:
        return float("nan")
    reference = np.exp(-1j * phase[mask])
    return float(2 * np.abs(np.mean((values - values.mean()) * reference)))


def motor_load(log: FlightLog, segments, axis: int = 0, bins: int = 7) -> dict:
    """What each frequency costs the motors.

    Reports command amplitude alongside the resulting RPM oscillation. Their
    ratio is the mechanical following gain, and it falling with frequency is
    the key safety fact: past the rotor's bandwidth the command stops
    producing acceleration and becomes current ripple, so a wider sweep is
    mechanically gentler than the low-frequency part already being flown.
    """
    if not segments or not log.has("motor[0]") or not log.has("debug[2]"):
        return {}
    freq_all = log["debug[2]"] / 10.0
    selected = [(s, e, a) for s, e, a in segments if a == axis]
    if not selected:
        return {}

    channels = {"setpoint": f"setpoint[{axis}]", "gyro": f"gyroADC[{axis}]",
                "P": f"axisP[{axis}]", "D": f"axisD[{axis}]", "F": f"axisF[{axis}]",
                "motor": "motor[0]"}
    channels = {k: v for k, v in channels.items() if log.has(v)}
    # Pair the RPM with the *same* motor whose command is being measured. A
    # roll or pitch sweep drives the motors differentially, so the four-motor
    # mean cancels the oscillation and makes the rotor look like it stops
    # following far earlier than it does.
    rpm = log.motor_rpm(0)
    regime = log.rpm

    rows = []
    for lo, hi in log_bins(max(1.0, float(np.min(freq_all[freq_all > 0]))),
                           float(np.max(freq_all)), bins):
        collected: dict[str, list[float]] = {k: [] for k in channels}
        collected["rpm"] = []
        for start, end, _ in selected:
            segment_freq = freq_all[start:end]
            mask = (segment_freq >= lo) & (segment_freq < hi)
            if mask.sum() < 40:
                continue
            for key, column in channels.items():
                collected[key].append(
                    _amplitude_at_sweep(log[column], start, end, segment_freq, log.fs, mask))
            collected["rpm"].append(
                _amplitude_at_sweep(rpm, start, end, segment_freq, log.fs, mask))
        if not collected.get("motor"):
            continue
        row = {"lo": lo, "hi": hi}
        for key, values in collected.items():
            finite = [v for v in values if np.isfinite(v)]
            row[key] = float(np.median(finite)) if finite else float("nan")
        if row.get("motor"):
            row["following"] = row["rpm"] / row["motor"] if row["motor"] else float("nan")
        rows.append(row)

    motors = log.motors
    active = np.zeros(log.n, dtype=bool)
    for start, end, _ in selected:
        active[start:end] = True
    _, upper = log.config.motor_range

    return {
        "rows": rows,
        "motor_median": float(np.median(motors[:, active])) if motors.size else float("nan"),
        "motor_p99": float(np.percentile(motors[:, active], 99)) if motors.size else float("nan"),
        "headroom": (float(upper - np.percentile(motors[:, active], 99))
                     if motors.size else float("nan")),
        "saturation_pct": (100.0 * float(np.mean(np.max(motors[:, active], axis=0) > upper - 40))
                           if motors.size else 0.0),
        "rpm_median": float(np.median(regime[active])),
        # Feedforward differentiates the setpoint, so its output grows with
        # frequency without the lead/lag bounding it. It must be zero for a
        # wide sweep to stay safe.
        "feedforward_active": log.config.num("ff_weight", 0) > 0,
    }
