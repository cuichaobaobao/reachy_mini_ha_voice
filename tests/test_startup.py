"""Startup wake must mirror the official conversation app."""
import numpy as np

from reachy_mini_ha_voice import startup

SLEEP_POSE = np.array([
    [0.911, 0.004, 0.413, -0.021],
    [-0.004, 1.0, -0.001, 0.001],
    [-0.413, -0.001, 0.911, -0.044],
    [0.0, 0.0, 0.0, 1.0],
])


class Mini:
    def __init__(self, pose=None, error=None):
        self.calls = []
        self.pose = pose
        self.error = error

    def get_current_head_pose(self):
        if self.error:
            raise self.error
        return self.pose

    def enable_motors(self):
        self.calls.append("enable_motors")

    def wake_up(self):
        self.calls.append("wake_up")


def test_sleep_pose_enables_motors_then_wakes(monkeypatch):
    monkeypatch.setattr(startup, "SLEEP_HEAD_POSE", SLEEP_POSE)
    mini = Mini(SLEEP_POSE.copy())
    assert startup.wake_up_if_sleeping(mini) is True
    assert mini.calls == ["enable_motors", "wake_up"]


def test_awake_pose_is_left_alone(monkeypatch):
    monkeypatch.setattr(startup, "SLEEP_HEAD_POSE", SLEEP_POSE)
    mini = Mini(np.eye(4))
    assert startup.wake_up_if_sleeping(mini) is False
    assert mini.calls == []


def test_pose_read_failure_does_not_wake(monkeypatch):
    monkeypatch.setattr(startup, "SLEEP_HEAD_POSE", SLEEP_POSE)
    mini = Mini(error=RuntimeError("no telemetry"))
    assert startup.wake_up_if_sleeping(mini) is False
    assert mini.calls == []


def test_wake_failure_is_reported(monkeypatch):
    monkeypatch.setattr(startup, "SLEEP_HEAD_POSE", SLEEP_POSE)
    mini = Mini(SLEEP_POSE.copy())

    def fail():
        raise RuntimeError("motor")

    mini.wake_up = fail
    assert startup.wake_up_if_sleeping(mini) is False
    assert mini.calls == ["enable_motors"]


def test_similar_position_but_wrong_rotation_is_awake(monkeypatch):
    monkeypatch.setattr(startup, "SLEEP_HEAD_POSE", SLEEP_POSE)
    pose = SLEEP_POSE.copy()
    pose[:3, :3] = np.eye(3)
    assert startup.wake_up_if_sleeping(Mini(pose)) is False
