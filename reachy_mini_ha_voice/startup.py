"""Startup wake behaviour, aligned with the official conversation app.

The daemon wakes the robot before launching a startup app, so the app must not
replay the SDK wake animation (head nod + ``wake_up.wav``) when the robot is
already awake. Mirror ``reachy_mini_conversation_app.app_lifecycle``: wake only
from the sleep pose, enable the motors first, and never wake when the pose
cannot be read.
"""

import logging

from reachy_mini.reachy_mini import SLEEP_HEAD_POSE
from reachy_mini.utils.interpolation import distance_between_poses

_LOG = logging.getLogger(__name__)

SLEEP_TRANSLATION_TOLERANCE_M = 0.05
SLEEP_ROTATION_TOLERANCE_RAD = 0.35


def _is_sleep_head_pose(head_pose) -> bool:
    """Return True when ``head_pose`` matches the SDK sleep pose."""
    try:
        import numpy as np

        pose = np.asarray(head_pose, dtype=float)
    except (TypeError, ValueError):
        return False
    if pose.shape != (4, 4):
        return False
    translation, rotation, _ = distance_between_poses(pose, SLEEP_HEAD_POSE)
    return (
        translation <= SLEEP_TRANSLATION_TOLERANCE_M
        and rotation <= SLEEP_ROTATION_TOLERANCE_RAD
    )


def wake_up_if_sleeping(mini, logger: logging.Logger = _LOG) -> bool:
    """Run the SDK wake movement only when the robot rests at the sleep pose."""
    try:
        head_pose = mini.get_current_head_pose()
    except Exception as e:  # noqa: BLE001 - any telemetry failure means "leave it alone"
        logger.warning("Could not read robot pose before startup wake-up check: %s", e)
        return False

    if not _is_sleep_head_pose(head_pose):
        return False

    logger.info("Robot is in sleep pose; running wake-up movement")
    try:
        mini.enable_motors()
        mini.wake_up()
    except Exception as e:  # noqa: BLE001 - waking is best-effort, the app still runs
        logger.error("Failed to run wake-up movement: %s", e)
        return False
    return True
