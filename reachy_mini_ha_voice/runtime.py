"""Own the upstream LVA process and consume its public peripheral API."""

import asyncio
import json
import logging
import os
import subprocess
import sys
from pathlib import Path

from websockets.client import connect
from websockets.exceptions import WebSocketException

_LOG = logging.getLogger(__name__)
VENDOR = Path(__file__).parent / "vendor" / "lva"


def command(data_dir, settings):
    args = [
        sys.executable,
        "-m",
        "linux_voice_assistant",
        "--name",
        settings.get("name", "Reachy Mini HA Voice"),
        "--peripheral-host",
        "127.0.0.1",
        "--peripheral-port",
        "6055",
        "--preferences-file",
        str(data_dir / "preferences.json"),
        "--download-dir",
        str(data_dir / "downloads"),
    ]
    for key in (
        "audio_input_device",
        "audio_output_device",
        "wake_model",
        "network_interface",
    ):
        value = settings.get(key)
        if value:
            args += ["--" + key.replace("_", "-"), str(value)]
    return args


def start_voice(data_dir, settings):
    if sys.platform != "linux":
        raise RuntimeError("Voice runtime requires Linux on Reachy Mini Wireless.")
    data_dir.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join((str(VENDOR), str(VENDOR.parents[2])))
    environment["PYTHONUNBUFFERED"] = "1"
    return subprocess.Popen(command(data_dir, settings), cwd=VENDOR, env=environment)


def stop_voice(process):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)


async def events(stop, queue):
    while not stop.is_set():
        try:
            async with connect(
                "ws://127.0.0.1:6055", open_timeout=2, close_timeout=1, max_size=65536
            ) as socket:
                while not stop.is_set():
                    try:
                        raw = await asyncio.wait_for(socket.recv(), timeout=0.25)
                    except TimeoutError:
                        continue
                    try:
                        message = json.loads(raw)
                    except (ValueError, TypeError):
                        _LOG.warning("Ignoring invalid LVA event")
                        continue
                    queue.put(message)
        except (TimeoutError, OSError, WebSocketException) as error:
            if stop.is_set():
                break
            _LOG.warning("LVA event connection lost: %s", error)
            queue.put({"event": "disconnected"})
            for _ in range(10):
                if stop.is_set():
                    return
                await asyncio.sleep(0.1)
