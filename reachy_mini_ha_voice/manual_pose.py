"""Manual head/body direction set from Home Assistant.

Home Assistant writes the goal from the LVA thread; the single motion loop
reads it and composes it under breathing, wake turns and speech wobble, so no
second motor owner ever exists. Goals use the slider convention (negative is
left or down, positive is right or up) and the official limits: body yaw
±160°, head yaw within ±65° of the body, head pitch ±40°.
"""

import math
import threading

LIMITS = {"body": 160.0, "head": 65.0, "pitch": 40.0}
NAMES = tuple(LIMITS)


def smoothstep(t):
    return t * t * (3 - 2 * t)


class ManualTarget:
    """Thread-safe goal shared by the Home Assistant controls and the motion loop."""

    def __init__(self):
        self._lock = threading.Lock()
        self._values = dict.fromkeys(NAMES, 0.0)

    def set(self, name, value):
        value = float(value)
        with self._lock:
            if math.isfinite(value):
                limit = LIMITS[name]
                self._values[name] = max(-limit, min(limit, value))
            return self._values[name]

    def center(self):
        with self._lock:
            self._values = dict.fromkeys(NAMES, 0.0)

    def get(self, name):
        with self._lock:
            return self._values[name]

    def snapshot(self):
        with self._lock:
            return dict(self._values)


class ManualPose:
    """Ease toward the goal; head offsets step aside while a conversation turn runs."""

    RELEASE = 0.6  # Seconds to straighten the head for a wake turn, or restore it after.

    def __init__(self, target):
        self.target = target
        self._current = dict.fromkeys(NAMES, 0.0)
        self._goal = dict(self._current)
        self._move = None
        self._weight = 1.0
        self._sampled = None

    def sample(self, now, engaged):
        """Return SDK angles in degrees: body yaw, head yaw offset, head pitch.

        SDK signs are positive yaw to the left and positive pitch down.
        """
        goal = self.target.snapshot()
        if goal != self._goal:
            self._goal = goal
            distance = max(abs(goal[name] - self._current[name]) for name in NAMES)
            self._move = (dict(self._current), goal, now, max(0.6, min(1.5, distance / 90.0)))
        if self._move is not None:
            start, end, began, duration = self._move
            blend = smoothstep(min(1.0, max(0.0, (now - began) / duration)))
            self._current = {name: start[name] + (end[name] - start[name]) * blend for name in NAMES}
            if blend == 1.0:
                self._move = None
        step = 0.0 if self._sampled is None else max(0.0, now - self._sampled) / self.RELEASE
        self._sampled = now
        self._weight = max(0.0, self._weight - step) if engaged else min(1.0, self._weight + step)
        hold = smoothstep(self._weight)
        return -self._current["body"], -self._current["head"] * hold, -self._current["pitch"] * hold

    @property
    def rest(self):
        """Body yaw (SDK degrees) a finished wake turn returns to."""
        return -self._goal["body"]

    @property
    def centered(self):
        return not any(self._goal.values()) and not any(self._current.values())
