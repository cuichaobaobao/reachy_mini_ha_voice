"""Startup helpers.

The daemon already wakes the robot before launching a startup app, so the app
must not replay the SDK wake animation (head nod + ``wake_up.wav``) when the
robot is already awake. Only wake when the measured head pose matches the SDK
sleep pose, which is how a manually started app finds a sleeping robot.
"""

import logging
from collections.abc import Sequence

_LOG = logging.getLogger(__name__)

# Sleep pose tolerance: the head may sag a few mm, but not stand at init.
POSE_TRANSLATION_TOLERANCE = 0.03
POSE_ROTATION_TOLERANCE = 0.4


def is_sleeping(mini, sleep_pose: Sequence[Sequence[float]] | None = None) -> bool:
    """Return True when the measured head pose is the SDK sleep pose.

    ``mini`` only needs ``get_current_head_pose()``. Unknown or missing
    telemetry falls back to True so a failed read keeps the previous behavior
    (wake once) instead of leaving a sleeping robot limp.
    """
    try:
        if sleep_pose is None:
            from reachy_mini.reachy_mini import SLEEP_HEAD_POSE

            sleep_pose = SLEEP_HEAD_POSE
        import numpy as np

        pose = np.asarray(mini.get_current_head_pose(), dtype=float)
        reference = np.asarray(sleep_pose, dtype=float)
        if pose.shape != (4, 4) or reference.shape != (4, 4):
            return True
        translation = float(np.linalg.norm(pose[:3, 3] - reference[:3, 3]))
        rotation = float(np.linalg.norm(pose[:3, :3] - reference[:3, :3]))
        return (
            translation < POSE_TRANSLATION_TOLERANCE
            and rotation < POSE_ROTATION_TOLERANCE
        )
    except Exception:  # noqa: BLE001 - any telemetry failure must keep the old wake behavior
        _LOG.info("Sleep pose unavailable; waking once to be safe")
        return True
