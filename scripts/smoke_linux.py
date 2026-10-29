"""Boot the real LVA runtime against a virtual Linux audio device and ESPHome client."""

import asyncio
import ctypes.util
import os
import sys
import tempfile
from pathlib import Path

from aioesphomeapi import APIClient

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "reachy_mini_ha_voice/vendor/lva"


async def first_announcement(client):
    """HA-style first announcement must fetch HTTP audio without manual retry."""
    import io
    import wave
    from aioesphomeapi.api_pb2 import VoiceAssistantAnnounceRequest, VoiceAssistantAnnounceFinished

    stream = io.BytesIO()
    with wave.open(stream, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16000)
        output.writeframes(b"\0\0" * 3200)
    body = stream.getvalue()
    fetched = asyncio.Event()
    requests = []

    async def serve(reader, writer):
        try:
            headers = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 5)
            requests.append(headers.split(b"\r\n", 1)[0])
            fetched.set()  # Same success criterion as HA's connection_test view.
            await asyncio.sleep(.3)  # Cold/slow response must not finish early.
            writer.write((f"HTTP/1.1 200 OK\r\nContent-Type: audio/wav\r\nContent-Length: {len(body)}\r\nConnection: close\r\n\r\n").encode() + body)
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    async with await asyncio.start_server(serve, "127.0.0.1", 0) as server:
        port = server.sockets[0].getsockname()[1]
        url = f"http://127.0.0.1:{port}/api/assist_satellite/connection_test/first"
        request = asyncio.create_task(client._get_connection().send_message_await_response(
            VoiceAssistantAnnounceRequest(media_id=url), VoiceAssistantAnnounceFinished, timeout=10))
        try:
            await asyncio.wait_for(fetched.wait(), 10)
            assert not request.done(), "Announcement completed before response audio arrived"
            await asyncio.wait_for(request, 10)
            assert len(requests) == 1, requests
            assert requests[0].startswith(b"GET /api/assist_satellite/connection_test/first ")
        finally:
            if not request.done():
                request.cancel()
                await asyncio.gather(request, return_exceptions=True)
    print("First ESPHome announcement -> HTTP test audio fetched and completed without retry")


async def direction_controls(client, entities):
    """Manual direction entities are listed after LVA's own and round-trip over ESPHome."""
    from aioesphomeapi import ButtonInfo, NumberInfo

    by_id = {entity.object_id: entity for entity in entities}
    sliders = [by_id[name] for name in ("body_turn", "head_turn", "head_tilt")]
    center = by_id["center_pose"]
    assert all(isinstance(slider, NumberInfo) for slider in sliders), sliders
    assert isinstance(center, ButtonInfo), center
    assert [s.max_value for s in sliders] == [160, 65, 40]
    ours = {"body_turn", "head_turn", "head_tilt", "center_pose"}
    lva_keys = [entity.key for entity in entities if entity.object_id not in ours]
    assert min(by_id[name].key for name in ours) > max(lva_keys), "LVA entity keys must stay first"
    states = {}
    changed = asyncio.Event()

    def on_state(state):
        states[state.key] = getattr(state, "state", None)
        changed.set()

    client.subscribe_states(on_state)

    async def until(expected):
        for _ in range(50):
            if all(states.get(key) == value for key, value in expected.items()):
                return
            changed.clear()
            await asyncio.wait_for(changed.wait(), 5)
        raise AssertionError(states)

    await until({s.key: 0 for s in sliders})
    client.number_command(sliders[0].key, 300)
    client.number_command(sliders[2].key, -12)
    await until({sliders[0].key: 160, sliders[2].key: -12})
    client.button_command(center.key)
    await until({s.key: 0 for s in sliders})
    print("Manual direction controls: listed after LVA entities, clamped, centered")


async def main():
    assert ctypes.util.find_library("mpv") is None, "Regression must run without libmpv"
    assert not __import__("subprocess").run(["pgrep", "-x", "pulseaudio"], capture_output=True).returncode == 0
    print("No PulseAudio server or libmpv; real SDK pipeline with virtual endpoints + LVA startup")
    with tempfile.TemporaryDirectory(prefix="ha-voice-smoke-") as directory:
        env = dict(os.environ, PYTHONPATH=os.pathsep.join((str(VENDOR), str(ROOT / "scripts"))), PYTHONUNBUFFERED="1")
        child = await asyncio.create_subprocess_exec(
            *[
                sys.executable,
                str(ROOT / "scripts/run_virtual_voice.py"),
                "--host",
                "127.0.0.1",
                "--network-interface",
                "eth0",
                "--name",
                "Reachy CI",
                "--preferences-file",
                str(Path(directory) / "preferences.json"),
                "--download-dir",
                directory,
                "--peripheral-host",
                "127.0.0.1",
            ],
            cwd=VENDOR,
            env=env,
        )
        client = APIClient("127.0.0.1", 6053, "")
        try:
            for _ in range(60):
                if child.returncode is not None:
                    raise RuntimeError(f"LVA exited {child.returncode}")
                try:
                    _reader, writer = await asyncio.open_connection("127.0.0.1", 6053)
                    writer.close()
                    await writer.wait_closed()
                    break
                except OSError:
                    await asyncio.sleep(1)
            else:
                raise TimeoutError("LVA startup timed out")
            for _ in range(60):
                if child.returncode is not None:
                    raise RuntimeError(f"LVA exited {child.returncode}")
                try:
                    _reader, writer = await asyncio.open_connection("127.0.0.1", 6055)
                    writer.close()
                    await writer.wait_closed()
                    break
                except OSError:
                    await asyncio.sleep(1)
            else:
                raise TimeoutError("Peripheral API startup timed out")
            await client.connect(login=True)
            info = await client.device_info()
            assert info.friendly_name == "Reachy CI", info
            entities, _services = await client.list_entities_services()
            assert entities, "Expected ESPHome entities"
            print(
                f"ESPHome handshake successful: {info.name}, {len(entities)} entities"
            )
            await direction_controls(client, entities)
            await first_announcement(client)
            # Three-minute connected run, repeated real playback and fresh API
            # requests. No disconnect before stop: exercise production cleanup.
            for cycle in range(6):
                await asyncio.sleep(30)
                assert child.returncode is None, child.returncode
                await client.device_info()
                await first_announcement(client)
            print("180-second connected LVA/audio soak passed; 7 announcements completed")
            import json

            from websockets.client import connect

            async with connect("ws://127.0.0.1:6055") as socket:
                snapshot = json.loads(await asyncio.wait_for(socket.recv(), 5))
                assert snapshot["event"] == "snapshot"
                assert snapshot["data"]["ha_connected"]
                print("Peripheral snapshot confirms connected HA-compatible client")
        finally:
            # Keep HA connected during shutdown: this used to deadlock wait_closed.
            # Also exercise shutdown after the upstream peripheral startup wait.
            await asyncio.sleep(2.5)
            child.terminate()
            try:
                await asyncio.wait_for(child.wait(), 10)
            except TimeoutError:
                child.kill()
                await child.wait()
                raise AssertionError("LVA required SIGKILL instead of clean shutdown")
            await client.disconnect()
            assert child.returncode == 0, child.returncode


asyncio.run(main())
