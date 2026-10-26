"""Recent direction captured before LVA plays its wake chime.

Uses the active SDK audio owner's DOA when supplied, otherwise the daemon. No network request
runs on the wake-word/audio thread. A missing/old reading never delays Assist.

The array's raw angle is noisy (single-sample jumps of tens of degrees), so a wake
snapshot is the median of the last SPEECH_WINDOW seconds of speech samples. DOA is a
linear 0..pi scale (0 = left, pi = right), so the two ends are opposite, not adjacent.
Without any speech-flagged sample the reading is dominated by room noise and is dropped.
"""
import json
import logging
import math
import statistics
import threading
import time
from collections import deque
from urllib.request import ProxyHandler, build_opener

_LOG = logging.getLogger(__name__)
URL = (
    "http://127.0.0.1:8000/api/state/full?with_doa=true"
    "&with_control_mode=false&with_body_yaw=false&with_antenna_positions=false"
)
SPEECH_WINDOW = 0.8
MIN_SPEECH_SAMPLES = 3
SEED_CLUSTER = math.radians(30.0)
SAMPLE_LIMIT = 64


def _unwrap(values, period):
    ref = values[0]
    return [ref + ((value - ref + period / 2) % period) - period / 2 for value in values]


def circular_median(values, period):
    """Median on a circle, used for the 2*pi-periodic head yaw."""
    unwrapped = _unwrap(values, period)
    if max(unwrapped) - min(unwrapped) < 1e-12:
        return values[0]
    return statistics.median(unwrapped) % period


def _spread_degrees(angles):
    return math.degrees(max(angles) - min(angles))


class DirectionReader:
    def __init__(self, playing=lambda: False, url=URL, clock=time.monotonic, doa=None, pose=None):
        self.playing = playing
        self.doa = doa
        self.pose = pose
        self.url = url.replace("with_doa=true", "with_doa=false") if doa else url
        self.clock = clock
        self._samples = deque(maxlen=SAMPLE_LIMIT)
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
                self._samples.append(reading)
                self._last_error = None
        except (KeyError, TypeError, ValueError):
            return

    def snapshot(self):
        if self.playing():
            _LOG.info("Wake direction skipped: playback active")
            return {}
        now = self.clock()
        with self._lock:
            recent = [s for s in self._samples if 0 <= now - s["sampled_at"] <= SPEECH_WINDOW]
        if not recent:
            _LOG.info("Wake direction skipped: %s", self._last_error)
            return {}
        speech = [s for s in recent if s["speech_detected"]]
        if len(speech) >= MIN_SPEECH_SAMPLES:
            pool, source = speech, "speech"
        elif speech:
            # One or two voice-flagged frames are too few on their own: keep
            # them as the seed and add nearby frames of the same utterance.
            seed = statistics.median(s["angle"] for s in speech)
            pool = [s for s in recent if abs(s["angle"] - seed) <= SEED_CLUSTER]
            pool = pool or speech
            source = "mixed"
        else:
            _LOG.info("Wake direction skipped: no speech-flagged samples in %d recent readings",
                      len(recent))
            return {}
        angle = statistics.median(s["angle"] for s in pool)
        yaw = circular_median([s["head_yaw"] for s in pool], 2 * math.pi)
        if yaw > math.pi:
            yaw -= 2 * math.pi
        elif yaw < -math.pi:
            yaw += 2 * math.pi
        newest = max(pool, key=lambda s: s["sampled_at"])
        spread = _spread_degrees([s["angle"] for s in pool])
        direction = {
            "angle": angle,
            "head_yaw": yaw,
            "sampled_at": newest["sampled_at"],
            "speech_detected": newest["speech_detected"],
            "source": source,
            "samples": len(pool),
            "spread": spread,
        }
        _LOG.info("Wake direction snapshot: DOA %.1f°, source=%s(%d, spread %.1f°), "
                  "speech=%s, age %.3fs",
                  math.degrees(angle), source, len(pool), spread,
                  direction["speech_detected"], now - newest["sampled_at"])
        return {"direction": direction}

    def _run(self):
        warned = False
        while not self._stop.is_set():
            if self.playing():
                with self._lock:
                    self._samples.clear()
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
