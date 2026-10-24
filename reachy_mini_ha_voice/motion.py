"""Official conversation breathing and listening antenna freeze, in degrees.

Port of BreathingMove.evaluate and the 0.4-second listening blend in upstream
moves.py. Acoustic heading is composed separately by the app, never here.
"""
import logging
import math

CONTROL_LOOP_HZ = 60.0
NEUTRAL_ANTENNAS = tuple(map(math.degrees, (-0.1745, 0.1745)))
_LOG = logging.getLogger(__name__)


def tick_delay(started, finished):
    return max(0.0, 1.0 / CONTROL_LOOP_HZ - max(0.0, finished - started))


class Motion:
    def __init__(self):
        self.state = "idle"
        self.pose = [0.0, 0.0, 0.0, *NEUTRAL_ANTENNAS]
        self.connected = False
        self.z = 0.0
        self._idle_started = None
        self._idle_origin = None
        self._frozen_antennas = NEUTRAL_ANTENNAS
        self._unfreeze_elapsed = 0.4

    def event(self, message):
        if not isinstance(message, dict):
            return
        event, data = message.get("event"), message.get("data") or {}
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
                self._idle_started = self._idle_origin = None
                _LOG.info("Listening antenna freeze: right %.2f°, left %.2f°", *self._frozen_antennas)
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
            return tuple(self.pose)
        self._unfreeze_elapsed = min(0.4, self._unfreeze_elapsed + max(0.0, dt))
        target = list(self.pose)
        if allow_breathing:
            if self._idle_started is None:
                self._idle_started = now
                self._idle_origin = (tuple(self.pose), self.z)
            elapsed = now - self._idle_started - 0.3
            origin, origin_z = self._idle_origin
            if elapsed >= 0:
                if elapsed < 1.0:
                    # Official first phase: linear interpolation to neutral.
                    target = [(1 - elapsed) * a + elapsed * b
                              for a, b in zip(origin, (0, 0, 0, *NEUTRAL_ANTENNAS))]
                    self.z = (1 - elapsed) * origin_z
                else:
                    phase = elapsed - 1.0
                    sway = 15.0 * math.sin(2 * math.pi * 0.5 * phase)
                    target = [0.0, 0.0, 0.0, sway, -sway]
                    self.z = .005 * math.sin(2 * math.pi * .1 * phase)
        else:
            self._idle_started = self._idle_origin = None
        blend = self._unfreeze_elapsed / .4
        target[3:] = [(1 - blend) * a + blend * b
                      for a, b in zip(self._frozen_antennas, target[3:])]
        self.pose = target
        return tuple(self.pose)
