"""Startup helpers.

The daemon already wakes the robot before launching a startup app, so the app
must not replay the SDK wake animation (head nod + ``wake_up.wav``) when the
robot is already awake. Only wake when the head joints sit at the SDK sleep
pose, which is how a robot that was started manually from sleep is detected.
"""

import logging
from collections.abc import Sequence

_LOG = logging.getLogger(__name__)

SLEEP_JOINT_TOLERANCE = 0.3


def is_sleeping(mini, sleep_joints: Sequence[float] | None = None) -> bool:
    """Return True when the head joints are at the SDK sleep pose.

    ``mini`` only needs ``get_current_joint_positions()``. Unknown or missing
    telemetry falls back to True so a failed read keeps the previous behavior
    (wake once) instead of leaving a sleeping robot limp.
    """
    try:
        if sleep_joints is None:
            from reachy_mini.reachy_mini import SLEEP_HEAD_JOINT_POSITIONS

            sleep_joints = SLEEP_HEAD_JOINT_POSITIONS
        joints, _ = mini.get_current_joint_positions()
        if len(joints) != len(sleep_joints):
            return True
        distance = sum((float(a) - float(b)) ** 2 for a, b in zip(joints, sleep_joints)) ** 0.5
        return distance < SLEEP_JOINT_TOLERANCE
    except Exception:  # noqa: BLE001 - any telemetry failure must keep the old wake behavior
        _LOG.info("Sleep pose unavailable; waking once to be safe")
        return True
