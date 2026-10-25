"""Only replay the SDK wake animation when the robot is actually asleep."""
import numpy as np

from reachy_mini_ha_voice.startup import is_sleeping

SLEEP_POSE = np.array([
    [0.911, 0.004, 0.413, -0.021],
    [-0.004, 1.0, -0.001, 0.001],
    [-0.413, -0.001, 0.911, -0.044],
    [0.0, 0.0, 0.0, 1.0],
])


class Mini:
    def __init__(self, pose):
        self.pose = pose

    def get_current_head_pose(self):
        return self.pose


def test_sleep_pose_is_detected():
    assert is_sleeping(Mini(SLEEP_POSE), SLEEP_POSE)


def test_awake_pose_is_not_mistaken_for_sleep():
    assert not is_sleeping(Mini(np.eye(4)), SLEEP_POSE)


def test_unknown_telemetry_falls_back_to_waking():
    class Broken:
        def get_current_head_pose(self):
            raise RuntimeError("no telemetry")

    assert is_sleeping(Broken(), SLEEP_POSE)


def test_wrong_shape_is_treated_as_unknown():
    assert is_sleeping(Mini(np.eye(3)), SLEEP_POSE)
