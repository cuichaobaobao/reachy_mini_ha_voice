"""Official Reachy Mini app: HA Assist voice with conversation gestures."""

import asyncio
import json
import math
import os
import threading
import time
from pathlib import Path
from queue import Empty, Queue

from reachy_mini import ReachyMiniApp
from reachy_mini.utils import create_head_pose

from .motion import Motion
from .runtime import events, start_voice, stop_voice


class ReachyMiniHaVoice(ReachyMiniApp):
    request_media_backend = "no_media"
    custom_app_url = None

    def run(self, reachy_mini, stop_event):
        data_dir = Path(
            os.environ.get(
                "REACHY_HA_DATA_DIR",
                str(Path.home() / ".local/share/reachy_mini_ha_voice"),
            )
        )
        config_path = data_dir / "config.json"
        settings = json.loads(config_path.read_text()) if config_path.exists() else {}
        if not isinstance(settings, dict):
            raise TypeError("config.json must contain a JSON object")
        process = start_voice(data_dir, settings)
        reader_stop = threading.Event()
        queue = Queue()
        reader = threading.Thread(
            target=lambda: asyncio.run(events(reader_stop, queue)),
            name="ha-voice-events",
        )
        motion = Motion()
        awake = False
        try:
            reader.start()
            reachy_mini.wake_up()
            awake = True
            reachy_mini.goto_target(
                head=create_head_pose(), antennas=[0, 0], duration=1.0
            )
            if settings.get("head_tracking", False) is True:
                reachy_mini.start_head_tracking(weight=1.0)
            else:
                reachy_mini.stop_head_tracking()
            previous = time.monotonic()
            while not stop_event.is_set():
                if process.poll() is not None:
                    raise RuntimeError(
                        f"LVA stopped with exit code {process.returncode}; see app logs"
                    )
                now = time.monotonic()
                for _ in range(100):
                    try:
                        motion.event(queue.get_nowait())
                    except Empty:
                        break
                roll, pitch, yaw, right, left = motion.sample(now, now - previous)
                reachy_mini.set_target(
                    head=create_head_pose(
                        z=motion.z,
                        roll=roll,
                        pitch=pitch,
                        yaw=yaw,
                        degrees=True,
                        mm=False,
                    ),
                    antennas=[math.radians(right), math.radians(left)],
                )
                previous = now
                stop_event.wait(1 / 30)
        finally:
            reader_stop.set()
            stop_voice(process)
            if reader.is_alive():
                reader.join(timeout=5)
            if awake:
                reachy_mini.stop_head_tracking()
                reachy_mini.disable_wobbling()
                reachy_mini.goto_target(
                    head=create_head_pose(), antennas=[0, 0], duration=1.0
                )


if __name__ == "__main__":
    app = ReachyMiniHaVoice()
    try:
        app.wrapped_run()
    except KeyboardInterrupt:
        app.stop()
