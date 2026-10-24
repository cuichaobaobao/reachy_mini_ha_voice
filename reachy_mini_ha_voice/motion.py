"""Conversation breathing and listening freeze; one caller owns robot motion."""

import math

CONTROL_LOOP_HZ = 60.0  # Official conversation application's executable constant.
NEUTRAL_ANTENNAS = (-10.0, 10.0)  # Degrees; outward bias takes up gearbox backlash.


def tick_delay(started, finished):
    """Account for computation time; never catch up by issuing bursts of commands."""
    return max(0.0, 1.0 / CONTROL_LOOP_HZ - max(0.0, finished - started))


def smoothstep(t):
    t = min(1.0, max(0.0, t))
    return t * t * t * (10 + t * (-15 + 6 * t))


class Motion:
    def __init__(self):
        self.state = "idle"
        self.pose = [0.0, 0.0, 0.0, *NEUTRAL_ANTENNAS]
        self.connected = False
        self.z = 0.0  # metres
        self._idle_started = None
        self._idle_origin = None
        self._frozen_antennas = NEUTRAL_ANTENNAS
        self._unfreeze_elapsed = 0.4

    def event(self, message):
        if not isinstance(message, dict):
            return
        event = message.get("event")
        data = message.get("data") or {}
        if not isinstance(data, dict):
            return
        if event == "snapshot":
            self.connected = bool(data.get("ha_connected"))
            self.state = "idle"
        elif event == "zeroconf":
            self.connected = data.get("status") == "connected"
        elif event in ("wake_word_detected", "listening"):
            if self.state != "listening":
                self._frozen_antennas = tuple(self.pose[3:])
                self._unfreeze_elapsed = 0.0
                self._idle_started = None
                self._idle_origin = None
            self.state = "listening"
        elif event == "thinking":
            self.state = "thinking"
        elif event == "tts_speaking":
            self.state = "speaking"
        elif event in ("tts_finished", "idle", "pipeline_error", "disconnected"):
            self.state = "idle"
            if event == "disconnected":
                self.connected = False

    def sample(self, now, dt, allow_breathing=True):
        if self.state == "listening":
            return tuple(self.pose)  # Exact freeze, including z; no new antenna targets.
        dt = min(max(dt, 0.0), 0.05)
        breathing = (self.state == "idle" and allow_breathing) or self.state == "speaking"
        if breathing:
            if self._idle_started is None:
                self._idle_started = now
                self._idle_origin = (tuple(self.pose), self.z)
            elapsed = now - self._idle_started
            if elapsed < 0.3:
                return tuple(self.pose)
            phase = elapsed - 0.3
            blend = smoothstep(phase)  # One second, with continuous endpoint velocity.
            sway = 15.0 * math.sin(2 * math.pi * 0.5 * phase)
            # Retain the rest offset throughout the oscillation, avoiding the
            # upstream BreathingMove's 10° jump at the interpolation boundary.
            target = [0.0, 0.0, 0.0,
                      NEUTRAL_ANTENNAS[0] + sway, NEUTRAL_ANTENNAS[1] - sway]
            origin, origin_z = self._idle_origin
            self.pose = [a + blend * (b - a) for a, b in zip(origin, target)]
            self.z = (1 - blend) * origin_z + blend * 0.005 * math.sin(2 * math.pi * 0.1 * phase)
        else:
            self._idle_started = None
            self._idle_origin = None
            self.z += max(-0.01 * dt, min(0.01 * dt, -self.z))
            target = [0.0, 0.0, 0.0, *NEUTRAL_ANTENNAS]
            if self.state == "thinking":
                target = [3 * math.sin(now), -3, 4 * math.sin(now * 0.7), -15, 15]
            step = 25 * dt
            self.pose = [old + max(-step, min(step, new - old))
                         for old, new in zip(self.pose, target)]
            if self._unfreeze_elapsed < 0.4:
                self.pose[3:] = target[3:]  # Blend from the frozen pose, not recursively.
        if self._unfreeze_elapsed < 0.4:
            self._unfreeze_elapsed = min(0.4, self._unfreeze_elapsed + dt)
            blend = self._unfreeze_elapsed / 0.4
            self.pose[3:] = [old + blend * (new - old)
                            for old, new in zip(self._frozen_antennas, self.pose[3:])]
        return tuple(self.pose)
