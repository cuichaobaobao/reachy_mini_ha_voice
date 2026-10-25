"""Official Reachy Mini app: HA Assist voice with conversation gestures."""

import asyncio
import json
import logging
import math
import os
import threading
import time
from pathlib import Path
from queue import Empty, Queue

from reachy_mini import ReachyMiniApp
from reachy_mini.utils import create_head_pose

from .heading import Heading
from .motion import (
    NEUTRAL_ANTENNAS,
    Motion,
    relative_to_heading,
    tick_delay,
    with_heading,
)
from .motion_link import MotionLink
from .runtime import events, start_voice, stop_voice
from .startup import wake_up_if_sleeping


class ReachyMiniHaVoice(ReachyMiniApp):
    request_media_backend = "local"
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
        logging.getLogger("reachy_mini_ha_voice").setLevel(logging.INFO)
        process = start_voice(data_dir, settings, reachy_mini)
        reader_stop = threading.Event()
        queue = Queue()
        reader = threading.Thread(
            target=lambda: asyncio.run(events(reader_stop, queue)),
            name="ha-voice-events",
        )
        heading = Heading()
        facing = 0.0

        def read_breathing_pose():
            _, antennas = reachy_mini.get_current_joint_positions()
            return relative_to_heading(reachy_mini.get_current_head_pose(), facing), antennas

        motion = Motion(read_breathing_pose)
        link = MotionLink(reachy_mini)
        awake = False
        try:
            reader.start()
            wake_up_if_sleeping(reachy_mini)
            awake = True
            reachy_mini.goto_target(
                head=create_head_pose(), antennas=list(NEUTRAL_ANTENNAS), body_yaw=0.0, duration=1.0
            )
            if settings.get("head_tracking", False) is True:
                reachy_mini.start_head_tracking(weight=1.0)
            else:
                reachy_mini.stop_head_tracking()
            tracking = settings.get("head_tracking", False) is True
            while not stop_event.is_set():
                if process.poll() is not None:
                    raise RuntimeError(
                        f"LVA stopped with exit code {process.returncode}; see app logs"
                    )
                now = time.monotonic()
                for _ in range(100):
                    try:
                        message = queue.get_nowait()
                        was_listening = motion.state == "listening"
                        motion.event(message, now)
                        if motion.state == "listening" and not was_listening:
                            try:
                                _, antennas = reachy_mini.get_current_joint_positions()
                                logging.getLogger(__name__).info(
                                    "Listening measured antennas: right %.2f°, left %.2f°",
                                    math.degrees(antennas[0]), math.degrees(antennas[1]))
                            except Exception as exc:  # noqa: BLE001 - diagnostic SDK reads cannot stop voice
                                logging.getLogger(__name__).warning("Listening telemetry unavailable: %s", exc)
                        heading.event(message, now)
                    except Empty:
                        break
                facing = heading.sample(now)
                heading.report_measured(reachy_mini, now)
                want_tracking = settings.get("head_tracking", False) is True and not heading.active
                if tracking != want_tracking:
                    if want_tracking:
                        reachy_mini.start_head_tracking(weight=1.0)
                    else:
                        reachy_mini.stop_head_tracking()
                    tracking = want_tracking
                head, antennas = motion.sample(now)
                if link.send(
                    head=with_heading(head, facing),
                    antennas=list(antennas),
                    body_yaw=math.radians(facing),
                ):
                    motion.command_sent(antennas)
                stop_event.wait(tick_delay(now, time.monotonic()))
        finally:
            reader_stop.set()
            link.close()
            try:
                stop_voice(process)
            finally:
                if reader.is_alive():
                    reader.join(timeout=5)
            if awake:
                try:
                    reachy_mini.stop_head_tracking()
                    reachy_mini.disable_wobbling()
                    reachy_mini.goto_target(
                        head=create_head_pose(), antennas=list(NEUTRAL_ANTENNAS), body_yaw=0.0, duration=1.0
                    )
                except ConnectionError:
                    logging.getLogger(__name__).warning("SDK unavailable at shutdown; neutral command skipped")


if __name__ == "__main__":
    app = ReachyMiniHaVoice()
    try:
        app.wrapped_run()
    except KeyboardInterrupt:
        app.stop()
