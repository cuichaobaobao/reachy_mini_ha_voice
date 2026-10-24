"""Recent direction captured before LVA plays its wake chime.

Uses the active SDK audio owner's DOA when supplied, otherwise the daemon. No network request
runs on the wake-word/audio thread. A missing/old reading never delays Assist.
"""

import json
import logging
import math
import threading
import time
from urllib.request import ProxyHandler, build_opener

_LOG = logging.getLogger(__name__)
URL = (
    "http://127.0.0.1:8000/api/state/full?with_doa=true"
    "&with_control_mode=false&with_body_yaw=false&with_antenna_positions=false"
)


class DirectionReader:
    def __init__(self, playing=lambda: False, url=URL, clock=time.monotonic, doa=None, pose=None):
        self.playing = playing
        self.doa = doa
        self.pose = pose
        self.url = url.replace("with_doa=true", "with_doa=false") if doa else url
        self.clock = clock
        self._reading = None
        self._last_error = "no sample yet"
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None
        self._opener = build_opener(ProxyHandler({}))  # Local daemon never uses a proxy.

    def start(self):
        self._thread = threading.Thread(target=self._run, name="wake-direction", daemon=True)
        self._thread.start()

    def update(self, payload, sampled_at):
        try:
            doa, pose = payload["doa"], payload["head_pose"]
            angle, yaw = float(doa["angle"]), float(pose["yaw"])
            if (not all(map(math.isfinite, (angle, yaw, sampled_at))) or
                    not 0 <= angle <= math.pi):
                return
            reading = {"angle": angle, "head_yaw": yaw, "sampled_at": sampled_at, "speech_detected": bool(doa["speech_detected"])}
            with self._lock:
                self._reading = reading
                self._last_error = None
        except (KeyError, TypeError, ValueError):
            return

    def snapshot(self):
        if self.playing():
            _LOG.info("Wake direction skipped: playback active")
            return {}
        with self._lock:
            reading = self._reading
        if reading is None:
            _LOG.info("Wake direction skipped: %s", self._last_error)
            return {}
        age = self.clock() - reading["sampled_at"]
        if not 0 <= age <= 0.6:
            _LOG.info("Wake direction skipped: latest sample age %.3fs; last error=%s", age, self._last_error)
            return {}
        # Called only after wake-word recognition. A second XMOS VAD gate can
        # reject the final syllable's direction after the speaker has stopped.
        _LOG.info("Wake direction snapshot: DOA %.1f°, speech=%s, age %.3fs",
                  math.degrees(reading["angle"]), reading["speech_detected"], age)
        return {"direction": dict(reading)}

    def _run(self):
        warned = False
        while not self._stop.is_set():
            if self.playing():
                with self._lock:
                    self._reading = None
            else:
                try:
                    started = self.clock()
                    if self.pose is not None:
                        matrix = self.pose()  # SDK telemetry cache; no HTTP round trip.
                        payload = {"head_pose": {"yaw": math.atan2(matrix[1][0], matrix[0][0])}}
                    else:
                        with self._opener.open(self.url, timeout=0.3) as response:
                            payload = json.loads(response.read(65536))
                    if self.doa is not None:
                        direction = self.doa()
                        payload["doa"] = (
                            {"angle": direction[0], "speech_detected": direction[1]}
                            if direction is not None else None
                        )
                    # Reject a request overlapping audio playback.
                    if not self.playing():
                        self.update(payload, started)
                except (OSError, ValueError, TypeError, IndexError, AssertionError) as error:
                    self._last_error = f"{type(error).__name__}: {error}"
                    if not warned:
                        _LOG.warning("Wake direction unavailable; turning skipped until readings recover")
                        warned = True
            self._stop.wait(0.05 if self.pose is not None else 0.1)

    def close(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1)
