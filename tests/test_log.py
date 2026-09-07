"""Column access, unit conversion and chirp detection."""

import numpy as np

from bfchirp.log import Config


def test_columns_resolve_with_and_without_units(noise_log):
    """blackbox_decode writes "time (us)"; both spellings must work."""
    assert noise_log.has("time")
    assert noise_log.has("time (us)")
    assert np.allclose(noise_log["time"], noise_log["time (us)"])


def test_sample_rate_and_duration(noise_log):
    assert np.isclose(noise_log.fs, 2000.0)
    assert np.isclose(noise_log.nyquist, 1000.0)
    assert 19.9 < noise_log.duration < 20.1


def test_erpm_scaling_is_mechanical_rpm(noise_log):
    """eRPM is electrical RPM / 100 over pole pairs — 1800 at 12 poles is 30000."""
    assert np.isclose(np.mean(noise_log.rpm), 1800.0 * 100.0 / 6.0, rtol=0.01)


def test_mean_rpm_cancels_a_differential_excitation(chirp_log):
    """The regression that made the rotor look like it stopped following.

    A roll sweep drives the motors in opposite directions. Only motor 0 is
    modulated in this fixture, so the four-motor mean sees a quarter of it;
    on a real craft it cancels almost entirely.
    """
    single = np.std(chirp_log.motor_rpm(0))
    mean = np.std(chirp_log.rpm)
    assert single > 4 * mean


def test_chirp_detection(chirp_log, noise_log):
    assert chirp_log.is_chirp
    assert not noise_log.is_chirp


def test_chirp_band_is_read_as_deci_hz():
    config = Config({"chirp_frequency_start_deci_hz": "2",
                     "chirp_frequency_end_deci_hz": "150"})
    assert config.chirp_band_hz == (0.2, 15.0)


def test_config_helpers_tolerate_missing_and_malformed_keys():
    config = Config({"rollPID": "45,80,30", "broken": "n/a"})
    assert config.nums("rollPID") == [45.0, 80.0, 30.0]
    assert config.num("rollPID") == 45.0
    assert config.num("absent", 7.0) == 7.0
    assert config.num("broken", -1.0) == -1.0
    assert config.craft == "(unnamed)"
