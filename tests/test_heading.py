import math

import pytest

from reachy_mini_ha_voice.direction import DirectionReader
from reachy_mini_ha_voice.heading import Heading
from reachy_mini_ha_voice.motion import NEUTRAL_ANTENNAS, Motion


def wake(now, relative=30, measured=0):
    return {"event": "wake_word_detected", "data": {"direction": {
        "angle": math.radians(90 - relative),
        "head_yaw": math.radians(measured), "sampled_at": now,
    }}}


def test_full_angle_duration_and_deadband():
    for relative, duration in [(5, None), (30, .65), (40, .65), (90, 1.2)]:
        h = Heading()
        h.event(wake(10, relative), 10)
        if duration is None:
            assert h.sample(12) == 0
        else:
            assert h.sample(10 + duration / 2) == pytest.approx(relative / 2)
            assert h.sample(10 + duration) == pytest.approx(relative)
    h.event(wake(12, -80, 90), 12)
    assert h.sample(12 + (80 / 75) / 2) == pytest.approx(50)
    assert h.sample(14) == pytest.approx(10)


def test_hold_reply_completion_duplicate_idle_and_return():
    h = Heading()
    h.event(wake(0), 0)
    assert h.sample(1) == pytest.approx(30)
    h.event({"event": "tts_speaking"}, 2)
    assert h.sample(25) == pytest.approx(30)  # Playback start does not start return countdown.
    h.event({"event": "tts_finished"}, 25)
    h.event({"event": "idle"}, 25.1)
    assert h.sample(29.9) == pytest.approx(30)
    assert h.sample(30) == pytest.approx(30)
    h.event({"event": "idle"}, 30.2)  # Does not postpone an existing return.
    assert h.sample(30.75) == pytest.approx(15)
    assert h.sample(31.5) == 0
    assert not h.active


def test_changed_source_during_hold_and_during_return():
    h = Heading()
    h.event(wake(0), 0)
    h.sample(1)
    h.event({"event": "tts_finished"}, 2)
    # Already facing +30; a source 60 degrees to its right is world -30.
    h.event(wake(4, relative=-60, measured=30), 4)
    assert h.sample(4) == pytest.approx(30)
    assert h.sample(4.4) == pytest.approx(0)
    assert h.sample(4.8) == pytest.approx(-30)
    assert h.sample(8) == pytest.approx(-30)  # Old deadline (7) cancelled.
    h.event({"event": "idle"}, 9)
    h.sample(14)
    half = h.sample(14.75)
    assert half == pytest.approx(-15)
    h.event(wake(14.75, 45, half), 14.75)
    assert h.sample(14.75) == half  # No pose jump.
    assert h.sample(16) == pytest.approx(30)
    assert h.active


def test_continued_listening_cancels_return_and_errors_recover():
    h = Heading()
    h.event(wake(0), 0)
    h.sample(1)
    h.event({"event": "tts_finished"}, 2)
    h.event({"event": "listening"}, 2)
    assert h.sample(10) == pytest.approx(30)
    h.event({"event": "pipeline_error"}, 11)
    h.sample(16)
    assert h.sample(17.5) == 0
    h.event(wake(20), 20)
    h.sample(21)
    h.sample(141)  # Lost final event watchdog.
    assert h.sample(142.5) == 0


@pytest.mark.parametrize('change', [
    {"angle": float('nan')}, {"angle": -1}, {"head_yaw": float('inf')},
    {"sampled_at": -10}, {"sampled_at": 20},
])
def test_invalid_direction_does_not_turn(change):
    h = Heading()
    message = wake(10)
    message['data']['direction'].update(change)
    h.event(message, 10)
    assert h.sample(12) == 0


def test_missing_direction_cancels_return_at_current_heading():
    h = Heading()
    h.event(wake(0), 0)
    h.sample(1)
    h.event({'event': 'idle'}, 2)
    h.sample(7)
    current = h.sample(7.75)
    h.event({'event': 'wake_word_detected'}, 7.75)
    assert h.sample(10) == current
    assert h.active


def test_wake_reader_accepts_fresh_direction_after_hardware_vad_ends():
    now = [10.0]
    reader = DirectionReader(clock=lambda: now[0])
    payload = {'doa': {'angle': math.pi / 3, 'speech_detected': True},
               'head_pose': {'yaw': .2}}
    reader.update(payload, 10)
    assert reader.snapshot()['direction']['head_yaw'] == .2
    payload['doa']['speech_detected'] = False
    reader.update(payload, 10.4)
    now[0] = 10.7
    assert reader.snapshot()["direction"]["speech_detected"] is False
    now[0] = 11.1  # Still reject genuinely stale direction.
    reader.update({'doa': None}, 10.7)
    assert reader.snapshot() == {}


def test_breathing_waits_until_return_complete():
    motion = Motion()
    motion.sample(0, 0)
    assert motion.sample(10, .03, allow_breathing=False) == (0, 0, 0, *NEUTRAL_ANTENNAS)
    assert motion.z == 0
    motion.sample(11, .03)
    motion.sample(14.8, .03)
    assert motion.z == pytest.approx(.005)


@pytest.mark.parametrize("sdk_doa", [False, True])
def test_real_daemon_http_polling_playback_suppression_and_cleanup(sdk_doa):
    import json
    import threading
    import time
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    playing = [False]

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps({
                'doa': None if sdk_doa else {'angle': math.pi / 4, 'speech_detected': True},
                'head_pose': {'yaw': .3},
            }).encode())

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    reader = DirectionReader(playing=lambda: playing[0],
                             url=f'http://127.0.0.1:{server.server_port}/api/state/full',
                             doa=(lambda: (math.pi / 4, True)) if sdk_doa else None)
    try:
        reader.start()
        for _ in range(100):
            if reader.snapshot():
                break
            time.sleep(.01)
        assert reader.snapshot()['direction']['head_yaw'] == .3
        playing[0] = True
        assert reader.snapshot() == {}
    finally:
        reader.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
    assert not reader._thread.is_alive()


def test_long_tts_never_returns_before_playback_completion():
    h = Heading()
    h.event(wake(0), 0)
    h.sample(1)
    h.event({"event": "tts_speaking"}, 2)
    assert h.sample(200) == pytest.approx(30)
    assert h.active
    h.event({"event": "tts_finished"}, 201)
    assert h.sample(205) == pytest.approx(30)
    h.sample(206)
    assert h.sample(207.5) == 0


@pytest.mark.parametrize('measured,relative,expected', [(130, 60, 160), (-130, -60, -160), (70, 60, 130)])
def test_full_world_heading_uses_only_body_boundary(measured, relative, expected):
    h = Heading()
    h.event(wake(10, relative, measured), 10)
    assert h.sample(11.25) == pytest.approx(expected)


def test_sdk_pose_sampler_has_no_http_and_follows_new_source():
    import threading
    import time
    from unittest.mock import Mock

    sampled = threading.Event()
    values = [math.pi / 6, math.radians(30)]

    def pose():
        yaw = values[1]
        sampled.set()
        return [[math.cos(yaw), -math.sin(yaw)], [math.sin(yaw), math.cos(yaw)]]

    reader = DirectionReader(doa=lambda: (values[0], True), pose=pose)
    reader._opener = Mock()
    reader.start()
    try:
        assert sampled.wait(1)
        for _ in range(100):
            first = reader.snapshot()
            if first:
                break
            time.sleep(.005)
        assert first['direction']['head_yaw'] == pytest.approx(math.radians(30))
        h = Heading()
        h.event({'event': 'wake_word_detected', 'data': first}, time.monotonic())
        assert h.sample(time.monotonic() + 2) == pytest.approx(90)
        values[:] = [math.pi, math.radians(90)]
        for _ in range(100):
            latest = reader.snapshot()
            if latest.get('direction', {}).get('angle') == math.pi:
                break
            time.sleep(.005)
        assert latest['direction']['angle'] == math.pi
        reader._opener.open.assert_not_called()
    finally:
        reader.close()
    assert not reader._thread.is_alive()


def test_turn_diagnostics_distinguish_requested_and_measured_heading(caplog):
    import logging
    from types import SimpleNamespace

    h = Heading()
    robot = SimpleNamespace(get_current_head_pose=lambda: [[0, -1], [1, 0]],
                            get_current_joint_positions=lambda: ([math.pi / 2] * 7, [0, 0]))
    with caplog.at_level(logging.INFO):
        h.event(wake(0, relative=90), 0)
        h.report_measured(robot, 2)
    assert 'head/body target 90.0°' in caplog.text
    assert 'head 90.0°, body 90.0°' in caplog.text
    assert h._report is None
