"""Official BreathingMove checkpoints and listening freeze contract."""
import math

import pytest

from reachy_mini_ha_voice.motion import (
    CONTROL_LOOP_HZ,
    NEUTRAL_ANTENNAS,
    Motion,
    tick_delay,
)


def test_official_two_phase_breathing_checkpoints():
    m = Motion()
    m.pose[3:] = [-20, 20]
    m.sample(0, 0)
    assert m.sample(.8, .8)[3:] == pytest.approx([(-20 + NEUTRAL_ANTENNAS[0]) / 2, (20 + NEUTRAL_ANTENNAS[1]) / 2])
    # Upstream's second phase is zero-centred, including its boundary at t=1s.
    assert m.sample(1.3, .5)[3:] == pytest.approx([0, 0])
    for t in (1.8, 2.3, 2.8, 3.3, 3.8):
        pose = m.sample(t, .5)
        assert pose[3:] == pytest.approx([15 * math.sin(math.pi * (t - 1.3)), -15 * math.sin(math.pi * (t - 1.3))])
        assert m.z == pytest.approx(.005 * math.sin(.2 * math.pi * (t - 1.3)))


def test_listening_freezes_even_near_zero_without_invented_bias():
    m = Motion()
    m.sample(0, 0)
    before = m.sample(2.3, 1 / 60)
    z = m.z
    m.event({'event': 'listening'})
    for t in (3, 4, 5):
        assert m.sample(t, 1 / 60) == before
        assert m.z == z
    assert abs(before[3]) < .001


def test_thinking_speaking_and_idle_use_same_official_background():
    results = []
    for state in ('thinking', 'tts_speaking', 'idle'):
        m = Motion()
        m.event({'event': state})
        m.sample(0, 0)
        results.append((m.sample(3.8, 3.8), m.z))
    assert results[0] == results[1] == results[2]


def test_official_sixty_hz_accounts_for_compute():
    assert CONTROL_LOOP_HZ == 60
    assert tick_delay(1, 1.005) == pytest.approx(1 / 60 - .005)
    assert tick_delay(1, 1.1) == 0


def test_unfreeze_reaches_one_after_point_four_seconds():
    m = Motion()
    m.event({'event': 'listening'})
    m.event({'event': 'tts_speaking'})
    for i in range(24):
        m.sample(i / 60, 1 / 60)
    assert m._unfreeze_elapsed == pytest.approx(.4)
