"""Noise, step and chirp analyses against logs with known contents."""

import numpy as np

from bfchirp.chirp import analyse_chirp, chirp_segments
from bfchirp.noise import analyse_noise
from bfchirp.step import analyse_step


# -- noise ------------------------------------------------------------------

def test_noise_sees_the_filter_removing_the_tone(noise_log):
    """The fixture puts a 500 Hz tone in raw only, so 400-800 must show it gone."""
    result = analyse_noise(noise_log)
    roll = result.per_axis["Roll"]
    band = next(b for b in roll["bands"] if (b["lo"], b["hi"]) == (400, 800))
    assert band["raw"] > 5 * band["filtered"]
    assert band["attenuation_db"] < -12
    assert any(abs(f - 500) < 15 for f in roll["peaks_raw"])


def test_noise_reports_motor_harmonics(noise_log):
    result = analyse_noise(noise_log)
    h1_lo, h1_hi = result.rpm["harmonics"]["H1"]
    assert h1_lo <= result.rpm["mean"] / 60.0 <= h1_hi
    assert result.saturation_pct == 0.0


def test_noise_drops_bands_beyond_nyquist(noise_log):
    result = analyse_noise(noise_log)
    assert all(hi <= noise_log.nyquist + 1e-6 for _, hi in result.bands)


# -- step -------------------------------------------------------------------

def test_step_reports_a_plausible_response(noise_log):
    result = analyse_step(noise_log)
    roll = result.per_axis["Roll"]
    assert roll["ok"] and roll["windows"] >= 3
    assert roll["rise_ms"] > 0
    assert np.isclose(result.quantisation_ms, 0.5)


def test_step_declines_when_the_sticks_never_moved(noise_log):
    result = analyse_step(noise_log, min_excitation=10_000.0)
    assert all(not entry["ok"] for entry in result.per_axis.values())


# -- chirp ------------------------------------------------------------------

def test_segments_are_found_and_attributed_to_their_axis(chirp_log):
    segments = chirp_segments(chirp_log)
    assert len(segments) == 4
    assert all(axis == 0 for _, _, axis in segments)
    assert all(end > start for start, end, _ in segments)


def test_measured_delay_matches_the_lag_that_was_injected(chirp_log):
    """The fixture's loop is a 15 ms first-order lag and nothing else.

    Below its corner the phase of such a lag is very nearly that of a 15 ms
    pure delay, so the fitted tau must land close to it. This is the check
    that the whole transfer-function path is wired up correctly.
    """
    result = analyse_chirp(chirp_log)
    roll = result.per_axis["Roll"]
    assert roll["n_sweeps"] == 4
    assert 11.0 < roll["tau_ms"] < 19.0
    assert roll["tau_r2"] > 0.95
    assert roll["coherence_min"] > 0.9


def test_gain_tracks_the_response_that_was_injected(chirp_log):
    """Magnitude accuracy, and the estimator's ripple made explicit.

    The fixture's magnitude is a 2 ms lag — essentially flat across the sweep,
    never above 0 dB. Two limitations show up against that known truth, and
    both are asserted rather than hidden:

    * roughly ±0.8 dB of ripple with only four sweeps, enough to manufacture
      an apparent resonant peak. The Air65 reference log, with 21, settles
      well below that.
    * a bias that grows toward the top of the band, reaching ~1.7 dB at
      15 Hz. An exponential sweep barely dwells there, and coherence does not
      catch it: it stays at 0.999 in this noiseless fixture.
    """
    roll = analyse_chirp(chirp_log).per_axis["Roll"]
    freqs = roll["f"]
    truth = -20 * np.log10(np.sqrt(1 + (2 * np.pi * freqs * 0.002) ** 2))
    error = np.abs(roll["gain_db"] - truth)

    interior = freqs <= 10.0
    assert np.max(error[interior]) < 0.9
    # The top of the band is the least trustworthy part of the measurement,
    # which is exactly where a tuner most wants to read it.
    assert error[-1] > np.max(error[interior])
    assert roll["coherence_min"] > 0.99   # and coherence gives no warning
    assert not roll["peak_is_edge_artefact"]
    assert roll["gain_top_db"] < 0        # a lag only ever attenuates


def test_band_and_settings_come_from_the_header(chirp_log):
    result = analyse_chirp(chirp_log)
    assert result.settings["start_hz"] == 0.2
    assert result.settings["end_hz"] == 15.0
    assert result.settings["amplitude"]["Yaw"] == 180.0
    assert result.band[0] >= 1.5          # the firmware attenuates below this
    assert result.band[1] <= 15.0


def test_excitation_profile_is_measured_not_assumed(chirp_log):
    profile = analyse_chirp(chirp_log).excitation
    assert profile["nominal"] == 230.0
    assert len(profile["rows"]) > 5
    assert all(row["amplitude"] > 0 for row in profile["rows"])


def test_motor_load_pairs_the_command_with_its_own_rotor(chirp_log):
    """Only motor 0 is modulated in the fixture, and it is the one measured."""
    load = analyse_chirp(chirp_log).motor_load
    assert load["rows"]
    assert load["feedforward_active"] is False
    assert load["saturation_pct"] == 0.0
    followings = [row["following"] for row in load["rows"]
                  if np.isfinite(row.get("following", np.nan))]
    assert followings and all(f > 0 for f in followings)
