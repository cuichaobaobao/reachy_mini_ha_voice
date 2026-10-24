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


def test_worker_cleanup():
    worker = Mock()
    stop_voice(worker)
    worker.stop.assert_called_once()


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


