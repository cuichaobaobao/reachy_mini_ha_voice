"""Mechanical rest bias, continuous breathing and official-rate scheduling."""
import math

import pytest

from reachy_mini_ha_voice.motion import CONTROL_LOOP_HZ, Motion, tick_delay


def test_rest_and_hold_do_not_command_vertical_antennas():
    m = Motion()
    assert m.pose[3:] == [-10, 10]
    for i in range(60):
        assert m.sample(i / 60, 1 / 60, allow_breathing=False)[3:] == (-10, 10)


def test_breathing_transition_has_no_ten_degree_jump():
    m = Motion()
    m.sample(0, 0)
    previous = tuple(m.pose)
    for i in range(1, 900):
        pose = m.sample(i / 60, 1 / 60)
        assert max(abs(a - b) for a, b in zip(pose, previous)) < 1.1
        assert abs(m.z) <= .005 + 1e-9
        previous = pose
    # Steady antenna trajectory: original 15° amplitude, 2-second period,
    # with a persistent ±10° offset rather than a discontinuous zero baseline.
    for t in (3.8, 4.3, 4.8, 5.3):
        pose = m.sample(t, 1 / 60)
        assert pose[3] == pytest.approx(-10 + 15 * math.sin(math.pi * (t - .3)))
        assert pose[4] == -pose[3]
        assert m.z == pytest.approx(.005 * math.sin(.2 * math.pi * (t - .3)))


def test_exact_listening_freeze_and_point_four_second_unfreeze():
    m = Motion()
    m.sample(0, 0)
    before = m.sample(2.8, 1 / 60)
    z = m.z
    m.event({'event': 'listening'})
    for t in (3, 4, 5):
        assert m.sample(t, 1 / 60) == before
        assert m.z == z
    m.event({'event': 'thinking'})
    for i in range(1, 25):
        pose = m.sample(5 + i / 60, 1 / 60)
        blend = min(i / 24, 1)
        assert pose[3] == pytest.approx(before[3] + blend * (-15 - before[3]))
        assert pose[4] == pytest.approx(before[4] + blend * (15 - before[4]))


def test_official_sixty_hz_accounts_for_compute_and_never_catches_up():
    assert CONTROL_LOOP_HZ == 60
    assert tick_delay(1, 1.005) == pytest.approx(1 / 60 - .005)
    assert tick_delay(1, 1.1) == 0


def test_unfreeze_timer_includes_breathing_start_delay():
    m = Motion()
    m.event({'event': 'listening'})
    m.event({'event': 'tts_speaking'})
    for i in range(25):
        m.sample(i / 60, 1 / 60)
    assert m._unfreeze_elapsed == pytest.approx(.4)
