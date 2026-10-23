import asyncio
import json
import threading
from queue import Queue
from unittest.mock import Mock

from reachy_mini_ha_voice.motion import Motion
from reachy_mini_ha_voice.runtime import VENDOR, command, events, stop_voice


def test_conversation_and_interrupt():
    motion = Motion()
    for event, expected in [
        ("listening", "listening"),
        ("thinking", "thinking"),
        ("tts_speaking", "speaking"),
        ("tts_finished", "idle"),
        ("tts_speaking", "speaking"),
        ("pipeline_error", "idle"),
        ("tts_speaking", "speaking"),
        ("disconnected", "idle"),
    ]:
        motion.event({"event": event})
        assert motion.state == expected
    motion.event({"event": "snapshot", "data": {"ha_connected": True}})
    assert motion.connected
    motion.event({"event": "disconnected"})
    assert not motion.connected


def test_bounds_continuity_and_listening_freeze():
    motion = Motion()
    previous = tuple(motion.pose)
    for i in range(1800):
        motion.event({"event": ["tts_speaking", "thinking", "idle"][i // 600]})
        pose = motion.sample(i / 30, 1 / 30)
        assert max(abs(x) for x in pose[:3]) <= 5
        assert max(abs(x) for x in pose[3:]) <= 15
        assert (
            max(abs(a - b) for a, b in zip(pose, previous))
            <= (50 if motion.state == "idle" else 25) / 30 + 1e-9
        )
        previous = pose
    motion.event({"event": "listening"})
    assert motion.sample(100, 10) == previous
    motion.event({"event": "tts_speaking"})
    assert max(abs(a - b) for a, b in zip(motion.sample(100, 10), previous)) <= 1.25


def test_invalid_events():
    motion = Motion()
    for value in [
        None,
        [],
        "invalid",
        {"event": "snapshot", "data": []},
        {"event": "snapshot", "data": "invalid"},
        {"event": "unknown"},
    ]:
        motion.event(value)
    assert motion.state == "idle"


def test_assets_and_command(tmp_path):
    for name in ["okay_nabu", "stop"]:
        config = json.loads((VENDOR / "wakewords" / f"{name}.json").read_text())
        assert (VENDOR / "wakewords" / config["model"]).stat().st_size > 1000
    assert (VENDOR / "sounds/wake_word_triggered.flac").exists()
    args = command(tmp_path, {"name": "Reachy test", "audio_input_device": "ReSpeaker"})
    assert args[args.index("--peripheral-host") + 1] == "127.0.0.1"
    assert args[args.index("--preferences-file") + 1] == str(
        tmp_path / "preferences.json"
    )
    assert args[args.index("--audio-input-device") + 1] == "ReSpeaker"


def test_child_cleanup():
    import subprocess

    process = Mock()
    process.poll.return_value = None
    process.wait.side_effect = [subprocess.TimeoutExpired("lva", 8), 0]
    stop_voice(process)
    process.terminate.assert_called_once()
    process.kill.assert_called_once()
    assert process.wait.call_count == 2


def test_real_websocket_events_and_shutdown():
    from websockets.server import serve

    async def exercise():
        stop = threading.Event()
        queue = Queue()

        async def handler(socket):
            await socket.send("not json")
            for event in ["listening", "thinking", "tts_speaking", "tts_finished"]:
                await socket.send(json.dumps({"event": event}))
            await socket.wait_closed()

        async with serve(handler, "127.0.0.1", 6055):
            task = asyncio.create_task(events(stop, queue))
            try:
                for _ in range(100):
                    if queue.qsize() >= 4:
                        break
                    await asyncio.sleep(0.02)
                assert [queue.get_nowait()["event"] for _ in range(4)] == [
                    "listening",
                    "thinking",
                    "tts_speaking",
                    "tts_finished",
                ]
            finally:
                stop.set()
                await asyncio.wait_for(task, 3)

    asyncio.run(exercise())


def test_official_idle_breathing_and_wake_freeze():
    import math

    motion = Motion()
    motion.sample(100, 0)
    motion.sample(103.8, 1 / 30)  # 0.3 s idle delay + 1 s blend + 2.5 s phase
    assert abs(motion.z - 0.005) < 1e-9
    assert abs(motion.pose[3] - 15) < 1e-9
    assert abs(motion.pose[4] + 15) < 1e-9
    motion.sample(108.8, 1 / 30)
    assert abs(motion.z + 0.005) < 1e-9
    pose, z = tuple(motion.pose), motion.z
    motion.event({"event": "wake_word_detected"})
    assert motion.sample(109, 1 / 30) == pose
    assert motion.z == z
    motion.event({"event": "idle"})
    assert motion.sample(110, 1 / 30) == pose
    assert motion.z == z
    for i in range(1000):
        motion.sample(110 + i / 30, 1 / 30)
        assert abs(motion.z) <= 0.005 + 1e-9
        assert all(math.isfinite(x) for x in motion.pose)


def test_speaking_has_no_synthetic_oscillation():
    motion = Motion()
    motion.event({"event": "tts_speaking"})
    for now in (0, 1, 2, 10):
        assert motion.sample(now, 1 / 30) == (0,) * 5
        assert motion.z == 0
