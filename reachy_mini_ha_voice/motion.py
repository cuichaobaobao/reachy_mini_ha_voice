"""Small, smooth conversation gestures; one caller owns robot motion."""

import math


class Motion:
    def __init__(self):
        self.state = "idle"
        self.pose = [0.0] * 5  # roll, pitch, yaw, right antenna, left antenna (degrees)
        self.connected = False
        self.z = 0.0  # metres
        self._idle_started = None
        self._idle_origin = None

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
            self.state = "listening"
        elif event == "thinking":
            self.state = "thinking"
        elif event == "tts_speaking":
            self.state = "speaking"
        elif event in ("tts_finished", "idle", "pipeline_error", "disconnected"):
            self.state = "idle"
            if event == "disconnected":
                self.connected = False

    def sample(self, now, dt):
        if self.state == "idle":
            if self._idle_started is None:
                self._idle_started = now
                self._idle_origin = (tuple(self.pose), self.z)
            elapsed = now - self._idle_started
            if elapsed < 0.3:
                return tuple(self.pose)
            phase = max(0.0, elapsed - 1.3)
            # Official BreathingMove amplitudes/frequencies. Blend from the
            # previous pose for one second, avoiding its antenna phase jump.
            blend = min(1.0, elapsed - 0.3)
            sway = 15 * math.sin(2 * math.pi * 0.5 * phase)
            target = [0.0, 0.0, 0.0, sway, -sway]
            origin, origin_z = self._idle_origin
            self.pose = [a + blend * (b - a) for a, b in zip(origin, target)]
            self.z = (1 - blend) * origin_z + blend * 0.005 * math.sin(
                2 * math.pi * 0.1 * phase
            )
            return tuple(self.pose)
        self._idle_started = None
        self._idle_origin = None
        if self.state == "listening":
            return tuple(self.pose)  # No motor noise during recognition.
        self.z += max(
            -0.01 * min(max(dt, 0), 0.05), min(0.01 * min(max(dt, 0), 0.05), -self.z)
        )
        target = [0.0] * 5
        if self.state == "speaking":
            target = [
                2 * math.sin(now * 3.1),
                4 * math.sin(now * 5.3),
                5 * math.sin(now * 1.7),
                12 * math.sin(now * 2.7),
                -12 * math.sin(now * 2.7),
            ]
        elif self.state == "thinking":
            target = [3 * math.sin(now), -3, 4 * math.sin(now * 0.7), -15, 15]
        # Limit velocity even after a delayed tick; continuously blend transitions.
        step = 25 * min(max(dt, 0), 0.05)
        self.pose = [
            old + max(-step, min(step, new - old))
            for old, new in zip(self.pose, target)
        ]
        return tuple(self.pose)
