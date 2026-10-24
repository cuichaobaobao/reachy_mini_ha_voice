"""Wake direction comes from the utterance, not from a single noisy sample."""
import math

import pytest

from reachy_mini_ha_voice.direction import SPEECH_WINDOW, DirectionReader


def reading(angle, speech=True, yaw=0.2):
    return {"doa": {"angle": angle, "speech_detected": speech},
            "head_pose": {"yaw": yaw}}


def test_speech_median_rejects_a_noise_spike():
    now = [10.0]
    reader = DirectionReader(clock=lambda: now[0])
    for angle in (1.20, 1.25, 1.18):
        reader.update(reading(angle), now[0])
    reader.update(reading(0.20), now[0])  # single-sample jump
    direction = reader.snapshot()["direction"]
    assert direction["source"] == "speech"
    assert direction["samples"] == 4
    assert direction["angle"] == pytest.approx(1.19, abs=0.05)


def test_median_survives_the_zero_pi_wraparound():
    now = [10.0]
    reader = DirectionReader(clock=lambda: now[0])
    for angle in (3.12, 3.10, 0.02, 0.01):
        reader.update(reading(angle), now[0])
    angle = reader.snapshot()["direction"]["angle"]
    assert min(angle, math.pi - angle) < 0.1


def test_no_speech_samples_fall_back_to_recent_values():
    now = [10.0]
    reader = DirectionReader(clock=lambda: now[0])
    for angle in (0.90, 0.92, 0.88):
        reader.update(reading(angle, speech=False), now[0])
    direction = reader.snapshot()["direction"]
    assert direction["source"] == "recent"
    assert direction["angle"] == pytest.approx(0.90, abs=0.05)


def test_samples_older_than_the_window_are_ignored():
    now = [10.0]
    reader = DirectionReader(clock=lambda: now[0])
    reader.update(reading(1.0), now[0])
    now[0] = 10.0 + SPEECH_WINDOW + 0.01
    assert reader.snapshot() == {}


def test_playback_suppresses_and_clears_direction():
    now = [10.0]
    playing = [False]
    reader = DirectionReader(playing=lambda: playing[0], clock=lambda: now[0])
    reader.update(reading(1.0), now[0])
    playing[0] = True
    assert reader.snapshot() == {}


def test_two_speech_samples_seed_a_nearby_cluster():
    now = [10.0]
    reader = DirectionReader(clock=lambda: now[0])
    reader.update(reading(1.20), now[0])
    reader.update(reading(1.22), now[0])
    reader.update(reading(1.18, speech=False), now[0])
    reader.update(reading(0.20, speech=False), now[0])  # far outlier
    direction = reader.snapshot()["direction"]
    assert direction["source"] == "mixed"
    assert direction["samples"] == 3
    assert direction["angle"] == pytest.approx(1.20, abs=0.05)


def test_window_covers_a_longer_utterance():
    now = [10.0]
    reader = DirectionReader(clock=lambda: now[0])
    reader.update(reading(1.30), now[0])
    now[0] = 10.7
    direction = reader.snapshot()["direction"]
    assert direction["angle"] == pytest.approx(1.30, abs=1e-12)
