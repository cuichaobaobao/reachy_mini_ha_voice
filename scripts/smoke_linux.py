"""Boot the real LVA runtime against a virtual Linux audio device and ESPHome client."""

import asyncio
import os
import sys
import tempfile
from pathlib import Path

from aioesphomeapi import APIClient

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "reachy_mini_ha_voice/vendor/lva"


async def main():
    with tempfile.TemporaryDirectory(prefix="ha-voice-smoke-") as directory:
        env = dict(os.environ, PYTHONPATH=str(VENDOR), PYTHONUNBUFFERED="1")
        child = await asyncio.create_subprocess_exec(
            *[
                sys.executable,
                "-m",
                "linux_voice_assistant",
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
            await client.connect(login=True)
            info = await client.device_info()
            assert info.friendly_name == "Reachy CI", info
            entities, _services = await client.list_entities_services()
            assert entities, "Expected ESPHome entities"
            print(
                f"ESPHome handshake successful: {info.name}, {len(entities)} entities"
            )
            import json

            from websockets.client import connect

            async with connect("ws://127.0.0.1:6055") as socket:
                snapshot = json.loads(await asyncio.wait_for(socket.recv(), 5))
                assert snapshot["event"] == "snapshot"
                assert snapshot["data"]["ha_connected"]
                print("Peripheral snapshot confirms connected HA-compatible client")
        finally:
            await client.disconnect()
            child.terminate()
            try:
                await asyncio.wait_for(child.wait(), 10)
            except TimeoutError:
                child.kill()
                await child.wait()


asyncio.run(main())
