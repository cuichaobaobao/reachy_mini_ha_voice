"""Official breathing/listening lifecycle, with acoustic heading kept separate.

Uses the upstream BreathingMove without changing its waveform. The only primary
move here is breathing: the conversation app's tool/dance queue is not included.
All poses are matrices in metres and all antenna angles are radians.
"""
import logging
import math

import numpy as np
from reachy_mini.utils import create_head_pose

from .official_breathing import BreathingMove

CONTROL_LOOP_HZ = 60.0
NEUTRAL_ANTENNAS = (-0.1745, 0.1745)
# Holding the antennas vertical is an unstable gearbox equilibrium and shakes.
# Listening is the only static hold, so a near-vertical freeze moves onto the
# SDK's own +/-10 degree resting bias (PR #952) instead of sitting at 0 degrees.
FREEZE_DEADZONE = math.radians(8.0)
FREEZE_BIAS = 0.1745
FREEZE_ADJUST_SECONDS = 0.2
_FREEZE_DEFAULT_SIGNS = (-1.0, 1.0)
_LOG = logging.getLogger(__name__)


def tick_delay(started, finished):
    return max(0.0, 1.0 / CONTROL_LOOP_HZ - max(0.0, finished - started))


def deadzone_safe_antennas(antennas):
    """Move a near-vertical pair onto the same-side +/-10 degree resting bias."""
    safe = []
    for value, default_sign in zip(antennas, _FREEZE_DEFAULT_SIGNS):
        if abs(value) < FREEZE_DEADZONE:
            safe.append(math.copysign(FREEZE_BIAS, value if value else default_sign))
        else:
            safe.append(value)
    return tuple(safe)


def relative_to_heading(head, heading):
    """Remove only the application's acoustic yaw from a measured world pose."""
    return create_head_pose(yaw=-heading) @ head


def with_heading(head, heading):
    """Keep head and body facing together without replacing breathing/tilt."""
    return create_head_pose(yaw=heading) @ head


class Motion:
    def __init__(self, read_pose=None):
        self.state = "idle"
        self.connected = False
        self.head = create_head_pose()
        self.antennas = NEUTRAL_ANTENNAS
        self._read_pose = read_pose
        self._move = self._queued_move = None
        self._move_started = None
        self._last_activity = None
        self._last_commanded_antennas = self.antennas
        self._frozen_antennas = self.antennas
        self._freeze_from = self._freeze_to = None
        self._freeze_started = None
        self._blend = 1.0
        self._last_blend_time = None
        self._now = 0.0

    def event(self, message, now=None):
        if not isinstance(message, dict):
            return
        event, data = message.get("event"), message.get("data") or {}
        if not isinstance(data, dict):
            return
        previous = self.state
        if event == "snapshot":
            self.connected = bool(data.get("ha_connected"))
            self.state = "idle"
        elif event == "zeroconf":
            self.connected = data.get("status") == "connected"
        elif event in ("wake_word_detected", "listening"):
            self.state = "listening"
        elif event == "thinking":
            self.state = "thinking"
        elif event == "tts_speaking":
            self.state = "speaking"
        elif event in ("tts_finished", "idle", "pipeline_error", "disconnected"):
            self.state = "idle"
            if event == "disconnected":
                self.connected = False
        if (previous == "listening") != (self.state == "listening"):
            now = self._now if now is None else now
            self._last_activity = self._last_blend_time = now
            self._blend = 0.0
            self._freeze_from = self._freeze_to = None
            self._freeze_started = None
            if self.state == "listening":
                raw = tuple(self._last_commanded_antennas)
                safe = deadzone_safe_antennas(raw)
                self._frozen_antennas = raw
                if safe != raw:
                    self._freeze_from, self._freeze_to = raw, safe
                    self._freeze_started = now
                    _LOG.info("Listening antenna freeze: right %.2f°, left %.2f° "
                              "(vertical deadzone, moving to right %.2f°, left %.2f°)",
                              math.degrees(raw[0]), math.degrees(raw[1]),
                              math.degrees(safe[0]), math.degrees(safe[1]))
                else:
                    _LOG.info("Listening antenna freeze: right %.2f°, left %.2f°",
                              math.degrees(raw[0]), math.degrees(raw[1]))
            else:
                # Leaving mid-adjustment must start the unfreeze from what was sent.
                self._frozen_antennas = tuple(self.antennas)
            # Upstream does not cancel/reset an already queued/running breath.

    def command_sent(self, antennas):
        """Remember only targets for which SDK set_target returned successfully.

        This is not a hardware acknowledgement, matching the official manager.
        """
        self._last_commanded_antennas = tuple(antennas)

    def _frozen_target(self, now):
        """Hold the frozen pair, easing a near-vertical freeze onto the bias."""
        if self._freeze_from is None:
            return tuple(self._frozen_antennas)
        elapsed = 0.0 if self._freeze_started is None else max(0.0, now - self._freeze_started)
        t = min(1.0, elapsed / FREEZE_ADJUST_SECONDS)
        blend = t * t * (3 - 2 * t)
        value = tuple(a + (b - a) * blend for a, b in zip(self._freeze_from, self._freeze_to))
        if t >= 1.0:
            self._frozen_antennas = tuple(self._freeze_to)
            self._freeze_from = self._freeze_to = None
            self._freeze_started = None
            return tuple(self._frozen_antennas)
        return value

    def sample(self, now):
        self._now = now
        if self._last_activity is None:
            self._last_activity = now
        # Official order: start previously queued move, then schedule idle move.
        if self._queued_move is not None:
            self._move, self._queued_move = self._queued_move, None
            self._move_started = now
        if self._move is None and self.state != "listening" and now - self._last_activity >= 0.3:
            try:
                head, antennas = (self._read_pose() if self._read_pose else (self.head, self.antennas))
                head = np.asarray(head, dtype=float)
                antennas = np.asarray(antennas, dtype=float)
                if head.shape != (4, 4) or antennas.shape != (2,) or not (
                    np.isfinite(head).all() and np.isfinite(antennas).all()
                ):
                    raise ValueError("Invalid feedback pose")
                self._queued_move = BreathingMove(head.copy(), tuple(antennas), 1.0)
                self._last_activity = now
            except Exception as exc:  # noqa: BLE001 - match upstream motion fault isolation
                # Like upstream: keep the last target and retry when feedback returns.
                _LOG.warning("Cannot start breathing from feedback: %s", exc)
        target_antennas = self.antennas
        if self._move is not None:
            self.head, target_antennas, _ = self._move.evaluate(now - self._move_started)
        # Same antenna freeze/blend as MovementManager._calculate_blended_antennas.
        dt = 0.0 if self._last_blend_time is None else max(0.0, now - self._last_blend_time)
        self._last_blend_time = now
        if self.state == "listening":
            self.antennas = self._frozen_target(now)
            self._blend = 0.0
        else:
            self._blend = min(1.0, self._blend + dt / 0.4)
            self.antennas = tuple(a * (1 - self._blend) + b * self._blend
                                  for a, b in zip(self._frozen_antennas, target_antennas))
            if self._blend >= 1.0:
                self._frozen_antennas = tuple(target_antennas)
        return self.head.copy(), self.antennas
