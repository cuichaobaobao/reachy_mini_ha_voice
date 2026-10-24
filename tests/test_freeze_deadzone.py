"""Listening freeze moves a near-vertical antenna pair onto the +/-10° bias.

Holding at 0° sits in the gearbox's unstable equilibrium and shakes (PR #952).
The breathing waveform itself is untouched; only the static listening hold moves.
"""
import itertools
import math

import numpy as np
import pytest

from reachy_mini_ha_voice.motion import (
    FREEZE_ADJUST_SECONDS,
    FREEZE_BIAS,
    Motion,
    deadzone_safe_antennas,
)

DEG = math.radians


def breathing_motion():
    motion = Motion()
    motion.sample(0.0)
    motion.sample(0.31)  # idle delay elapsed, BreathingMove queued
    motion.sample(0.32)  # move starts, phase 1 runs until 1.32
    return motion


@pytest.mark.parametrize('raw,expected', [
    ((0.0, 0.0), (-FREEZE_BIAS, FREEZE_BIAS)),
    ((DEG(3), -DEG(3)), (FREEZE_BIAS, -FREEZE_BIAS)),
    ((DEG(-3), DEG(3)), (-FREEZE_BIAS, FREEZE_BIAS)),
    ((DEG(6), -DEG(6)), (FREEZE_BIAS, -FREEZE_BIAS)),
    ((DEG(7.9), -DEG(7.9)), (FREEZE_BIAS, -FREEZE_BIAS)),
    ((DEG(8), -DEG(8)), (DEG(8), -DEG(8))),
    ((DEG(12), -DEG(12)), (DEG(12), -DEG(12))),
    ((DEG(-12), DEG(12)), (DEG(-12), DEG(12))),
])
def test_freeze_avoids_vertical_deadzone(raw, expected):
    motion = breathing_motion()
    motion.command_sent(raw)
    motion.event({'event': 'listening'}, 2.0)
    _, antennas = motion.sample(2.0 + FREEZE_ADJUST_SECONDS + 0.01)
    np.testing.assert_allclose(antennas, expected, atol=1e-12)


def test_freeze_starts_from_the_last_sent_value():
    raw = (DEG(5), -DEG(5))
    motion = breathing_motion()
    motion.command_sent(raw)
    motion.event({'event': 'wake_word_detected'}, 2.0)
    _, antennas = motion.sample(2.0)
    np.testing.assert_allclose(antennas, raw, atol=1e-12)


def test_adjustment_is_short_smooth_and_overshoot_free():
    raw = (DEG(4), -DEG(4))
    motion = breathing_motion()
    motion.command_sent(raw)
    motion.event({'event': 'listening'}, 2.0)
    values = [motion.sample(2.0 + i * 0.01)[1][0] for i in range(21)]
    assert values[0] == pytest.approx(raw[0])
    assert values[-1] == pytest.approx(FREEZE_BIAS)
    assert all(b >= a - 1e-12 for a, b in itertools.pairwise(values))
    assert max(values) <= FREEZE_BIAS + 1e-12
    # The whole move is inside the configured window, not a one-frame jump.
    assert values[10] < FREEZE_BIAS - 1e-6


def test_head_breathing_continues_while_antennas_settle():
    motion = breathing_motion()
    motion.command_sent((0.0, 0.0))
    motion.event({'event': 'wake_word_detected'}, 2.0)
    head_start, antennas_start = motion.sample(2.0)
    head_end, antennas_end = motion.sample(2.1)
    assert head_end[2, 3] != pytest.approx(head_start[2, 3])
    assert antennas_end != pytest.approx(antennas_start)


def test_unfreeze_begins_from_the_adjusted_bias():
    motion = breathing_motion()
    motion.command_sent((0.0, 0.0))
    motion.event({'event': 'listening'}, 2.0)
    motion.sample(2.0 + FREEZE_ADJUST_SECONDS)
    motion.event({'event': 'thinking'}, 2.0 + FREEZE_ADJUST_SECONDS)
    _, antennas = motion.sample(2.0 + FREEZE_ADJUST_SECONDS)
    np.testing.assert_allclose(antennas, (-FREEZE_BIAS, FREEZE_BIAS), atol=1e-12)


def test_leaving_mid_adjustment_does_not_jump():
    motion = breathing_motion()
    motion.command_sent((DEG(7), -DEG(7)))
    motion.event({'event': 'listening'}, 2.0)
    _, midway = motion.sample(2.1)
    motion.event({'event': 'thinking'}, 2.1)
    _, after = motion.sample(2.1)
    np.testing.assert_allclose(after, midway, atol=1e-12)


def test_deadzone_bias_keeps_left_right_symmetry():
    left, right = deadzone_safe_antennas((DEG(5), -DEG(5)))
    assert left == pytest.approx(-right)
    assert abs(left) == pytest.approx(FREEZE_BIAS)
