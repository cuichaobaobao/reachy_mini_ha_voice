"""Single-loop acoustic heading; no timer threads or competing motor commands."""

import logging
import math
from itertools import pairwise

_LOG = logging.getLogger(__name__)


# The microphone array under-reports off-axis sources: measured on the robot, a
# speaker at 45 degrees reads about 20 degrees and one at 90 degrees about 54.
# Piecewise-linear (raw, corrected) knots in degrees; symmetric, capped at 90.
DOA_CORRECTION = ((0.0, 0.0), (20.0, 45.0), (54.0, 90.0))


def corrected_relative(raw):
    """Map a raw DOA-relative angle (degrees) onto the speaker's actual bearing."""
    magnitude = abs(raw)
    for (x0, y0), (x1, y1) in pairwise(DOA_CORRECTION):
        if magnitude <= x1:
            value = y0 + (magnitude - x0) * (y1 - y0) / (x1 - x0)
            break
    else:
        value = DOA_CORRECTION[-1][1]
    return math.copysign(value, raw)


class Heading:
    BODY_YAW_LIMIT = 160.0  # SDK/body mechanical range; not a neck rotation limit.

    def __init__(self):
        self.yaw = 0.0
        self.active = False
        self._trajectory = None
        self._return_at = None
        self._watchdog = None
        self._ending = False
        self._report = None

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
                self._report = None
                self._trajectory = None  # Also stop a return when direction is missing.
                data = message.get("data") or {}
                reading = data.get("direction") if isinstance(data, dict) else None
                try:
                    angle = float(reading["angle"])
                    measured_yaw = math.degrees(float(reading["head_yaw"]))
                    age = now - float(reading["sampled_at"])
                    if not all(map(math.isfinite, (angle, measured_yaw, age))):
                        _LOG.info("Wake turn skipped: invalid direction values")
                        return
                    if not 0 <= age <= 1.0 or not 0 <= angle <= math.pi:
                        _LOG.info("Wake turn skipped: sample age %.3fs, DOA %.3f rad", age, angle)
                        return
                    raw = 90.0 - math.degrees(angle)
                    # Deadband on the raw reading so front-facing noise is not amplified.
                    if abs(raw) < 3.0:
                        _LOG.info("Wake turn skipped: relative %.1f° inside 3° deadband", raw)
                        return
                    relative = corrected_relative(raw)
                    target = max(-self.BODY_YAW_LIMIT, min(self.BODY_YAW_LIMIT, measured_yaw + relative))
                    duration = max(0.65, min(1.25, abs(target - self.yaw) / 75.0))
                    _LOG.info("Wake turn: DOA %.1f°, raw relative %.1f°, corrected %.1f°, "
                              "measured head %.1f°, head/body target %.1f°, sample age %.3fs, "
                              "duration %.2fs, direction=%s(%s samples, spread %.1f°)",
                              math.degrees(angle), raw, relative, measured_yaw, target, age,
                              duration, reading.get("source", "instant"),
                              reading.get("samples", 1), reading.get("spread", 0.0))
                    self._turn(target, now, duration)
                    self._report = (now + duration + 0.3, target)
                except (KeyError, TypeError, ValueError):
                    _LOG.info("Wake turn skipped: no fresh speech direction available")
                    return
        elif event in ("tts_finished", "idle", "pipeline_error", "disconnected", "snapshot"):
            self._watchdog = None
            if self.active and not self._ending:
                self._ending = True
                self._return_at = now + 5.0

    def report_measured(self, robot, now):
        """One cached telemetry sample after a turn; this never commands motors."""
        if self._report is None or now < self._report[0]:
            return
        _, target = self._report
        self._report = None
        try:
            pose = robot.get_current_head_pose()
            joints, _ = robot.get_current_joint_positions()
            head = math.degrees(math.atan2(pose[1][0], pose[0][0]))
            body = math.degrees(joints[0])
            _LOG.info("Wake turn measured: target %.1f°, head %.1f°, body %.1f°", target, head, body)
        except Exception as exc:  # noqa: BLE001 - diagnostic SDK reads cannot stop voice
            _LOG.info("Wake turn measured: telemetry unavailable: %s", exc)
