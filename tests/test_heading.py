import math

import pytest

from reachy_mini_ha_voice.direction import DirectionReader
from reachy_mini_ha_voice.heading import Heading
from reachy_mini_ha_voice.motion import Motion


def wake(now, relative=30, measured=0):
    return {"event": "wake_word_detected", "data": {"direction": {
        "angle": math.radians(90 - relative),
        "head_yaw": math.radians(measured), "sampled_at": now,
    }}}


def test_full_angle_duration_and_deadband():
    for relative, duration in [(5, None), (30, .65), (40, .65), (90, .65)]:
        h = Heading()
        h.event(wake(10, relative), 10)
        if duration is None:
            assert h.sample(12) == 0
        else:
            assert h.sample(10 + duration / 2) == pytest.approx(min(relative, 40) / 2)
            assert h.sample(10 + duration) == pytest.approx(min(relative, 40))
    h.event(wake(12, -80, 40), 12)
    assert h.sample(12 + (80 / 75) / 2) == pytest.approx(0)
    assert h.sample(14) == -40


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


def test_reader_requires_fresh_speech_and_measured_pose():
    now = [10.0]
    reader = DirectionReader(clock=lambda: now[0])
    payload = {'doa': {'angle': math.pi / 3, 'speech_detected': True},
               'head_pose': {'yaw': .2}}
    reader.update(payload, 10)
    assert reader.snapshot()['direction']['head_yaw'] == .2
    payload['doa']['speech_detected'] = False
    reader.update(payload, 10.4)
    now[0] = 10.7
    assert reader.snapshot() == {}  # Silence must not refresh stale data.
    reader.update({'doa': None}, 10.7)
    assert reader.snapshot() == {}


def test_breathing_waits_until_return_complete():
    motion = Motion()
    motion.sample(0, 0)
    assert motion.sample(10, .03, allow_breathing=False) == (0,) * 5
    assert motion.z == 0
    motion.sample(11, .03)
    motion.sample(14.8, .03)
    assert motion.z == pytest.approx(.005)


def test_real_daemon_http_polling_playback_suppression_and_cleanup():
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
                'doa': {'angle': math.pi / 4, 'speech_detected': True},
                'head_pose': {'yaw': .3},
            }).encode())

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    reader = DirectionReader(playing=lambda: playing[0],
                             url=f'http://127.0.0.1:{server.server_port}/api/state/full')
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
