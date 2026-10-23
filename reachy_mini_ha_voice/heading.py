"""Single-loop acoustic heading; no timer threads or competing motor commands."""

import logging
import math

_LOG = logging.getLogger(__name__)


class Heading:
    LIMIT = 40.0  # Conservative base yaw; leave room for speech/thinking offsets.

    def __init__(self):
        self.yaw = 0.0
        self.active = False
        self._trajectory = None
        self._return_at = None
        self._watchdog = None
        self._ending = False

    def _turn(self, target, now, duration):
        self._trajectory = (self.yaw, target, now, duration)

    def sample(self, now):
        if self._watchdog is not None and now >= self._watchdog:
            self._watchdog = None
            self._ending = True
            self._return_at = now  # Lost terminal event: do not stay turned forever.
        if self._return_at is not None and now >= self._return_at:
            self._return_at = None
            self._turn(0.0, now, 1.5)
        if self._trajectory is not None:
            start, target, began, duration = self._trajectory
            t = min(1.0, max(0.0, (now - began) / duration))
            blend = t * t * (3 - 2 * t)
            self.yaw = start + (target - start) * blend
            if t == 1:
                self._trajectory = None
                if target == 0 and self._ending and self._return_at is None:
                    self.active = False
        return self.yaw

    def event(self, message, now):
        if not isinstance(message, dict):
            return
        event = message.get("event")
        if event in ("wake_word_detected", "listening", "thinking", "tts_speaking"):
            self.sample(now)
            self._return_at = None
            if self._ending:
                self._trajectory = None
            self._ending = False
            # Long TTS must never return before actual playback completion.
            self._watchdog = None if event == "tts_speaking" else now + 120.0
            self.active = True
            if event == "wake_word_detected":
                self._trajectory = None  # Also stop a return when direction is missing.
                data = message.get("data") or {}
                reading = data.get("direction") if isinstance(data, dict) else None
                try:
                    angle = float(reading["angle"])
                    measured_yaw = math.degrees(float(reading["head_yaw"]))
                    age = now - float(reading["sampled_at"])
                    if not all(map(math.isfinite, (angle, measured_yaw, age))):
                        return
                    if not 0 <= age <= 1.0 or not 0 <= angle <= math.pi:
                        return
                    relative = 90.0 - math.degrees(angle)
                    if abs(relative) < 6.0:
                        return
                    target = max(-self.LIMIT, min(self.LIMIT, measured_yaw + relative))
                    duration = max(0.65, min(1.25, abs(target - self.yaw) / 75.0))
                    _LOG.info("Wake turn: relative %.1f°, target %.1f°, duration %.2fs",
                              relative, target, duration)
                    self._turn(target, now, duration)
                except (KeyError, TypeError, ValueError):
                    return
        elif event in ("tts_finished", "idle", "pipeline_error", "disconnected", "snapshot"):
            self._watchdog = None
            if self.active and not self._ending:
                self._ending = True
                self._return_at = now + 5.0
