"""Only replay the SDK wake animation when the robot is actually asleep."""
from reachy_mini_ha_voice.startup import is_sleeping

SLEEP = [0.0, 0.525, -0.669, 0.607, -0.607, 0.669, -0.525]


class Mini:
    def __init__(self, joints):
        self.joints = joints

    def get_current_joint_positions(self):
        return self.joints, (0.0, 0.0)


def test_sleep_pose_is_detected():
    assert is_sleeping(Mini(SLEEP), SLEEP)


def test_awake_pose_is_not_mistaken_for_sleep():
    assert not is_sleeping(Mini([0.0] * 7), SLEEP)


def test_unknown_telemetry_falls_back_to_waking():
    class Broken:
        def get_current_joint_positions(self):
            raise RuntimeError("no telemetry")

    assert is_sleeping(Broken(), SLEEP)


def test_joint_count_mismatch_is_treated_as_unknown():
    assert is_sleeping(Mini([0.0] * 6), SLEEP)
