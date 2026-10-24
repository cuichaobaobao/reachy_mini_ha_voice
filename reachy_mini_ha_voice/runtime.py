"""Own the upstream LVA worker and consume its public peripheral API."""

import asyncio
import json
import logging
import sys
import threading
from pathlib import Path

from websockets.client import connect
from websockets.exceptions import WebSocketException

_LOG = logging.getLogger(__name__)
VENDOR = Path(__file__).parent / "vendor" / "lva"


def command(data_dir, settings):
    args = [
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


class VoiceWorker:
    """One cancellable LVA event loop sharing the application's SDK instance."""

    def __init__(self, args, robot, runner=None):
        self.returncode = None
        self._loop = None
        self._task = None
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._run, args=(args, robot, runner), name="ha-voice-runtime", daemon=True
        )
        self._thread.start()

    def _run(self, args, robot, runner):
        try:
            if runner is None:
                if str(VENDOR) not in sys.path:
                    sys.path.insert(0, str(VENDOR))
                from linux_voice_assistant.__main__ import main
                runner = main

            async def run():
                self._loop = asyncio.get_running_loop()
                self._task = asyncio.current_task()
                if self._stop.is_set():
                    return
                await runner(argv=args, robot=robot, install_signals=False)

            asyncio.run(run())
            self.returncode = 0
        except asyncio.CancelledError:
            self.returncode = 0
        except (Exception, SystemExit):  # noqa: BLE001 - report worker failure to app
            _LOG.exception("LVA worker failed")
            self.returncode = 1

    def poll(self):
        return self.returncode

    def stop(self):
        self._stop.set()
        loop, task = self._loop, self._task
        if loop is not None and task is not None:
            try:
                loop.call_soon_threadsafe(task.cancel)
            except RuntimeError:
                pass  # Loop already finished.
        self._thread.join(timeout=10)
        if self._thread.is_alive():
            raise RuntimeError("LVA worker did not finish cleanup within 10 seconds")


def start_voice(data_dir, settings, robot):
    if sys.platform != "linux":
        raise RuntimeError("Voice runtime requires Linux on Reachy Mini Wireless.")
    data_dir.mkdir(parents=True, exist_ok=True)
    return VoiceWorker(command(data_dir, settings), robot)


def stop_voice(worker):
    worker.stop()


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
