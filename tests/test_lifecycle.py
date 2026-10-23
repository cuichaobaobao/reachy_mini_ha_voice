"""Exercise the app lifecycle without connecting to a robot."""

import asyncio
import importlib
import sys
import threading
from types import ModuleType
from unittest.mock import Mock

import pytest


@pytest.fixture
def app_module(monkeypatch):
    sdk = ModuleType("reachy_mini")
    sdk.ReachyMiniApp = type("ReachyMiniApp", (), {})
    utils = ModuleType("reachy_mini.utils")
    utils.create_head_pose = lambda **kw: kw
    monkeypatch.setitem(sys.modules, "reachy_mini", sdk)
    monkeypatch.setitem(sys.modules, "reachy_mini.utils", utils)
    sys.modules.pop("reachy_mini_ha_voice.main", None)
    module = importlib.import_module("reachy_mini_ha_voice.main")
    yield module
    sys.modules.pop("reachy_mini_ha_voice.main", None)


def test_normal_stop_cleans_child_and_returns_neutral(
    app_module, monkeypatch, tmp_path
):
    monkeypatch.setenv("REACHY_HA_DATA_DIR", str(tmp_path))
    child = Mock()
    child.poll.return_value = None
    stop_child = Mock()
    monkeypatch.setattr(app_module, "start_voice", lambda *_: child)
    monkeypatch.setattr(app_module, "stop_voice", stop_child)

    async def reader(stop, queue):
        queue.put({"event": "tts_speaking"})
        while not stop.is_set():
            await asyncio.sleep(0.01)

    monkeypatch.setattr(app_module, "events", reader)
    stop = threading.Event()
    robot = Mock()
    robot.set_target.side_effect = lambda **_: stop.set()
    app_module.ReachyMiniHaVoice().run(robot, stop)
    stop_child.assert_called_once_with(child)
    robot.start_head_tracking.assert_not_called()
    assert robot.stop_head_tracking.call_count == 2
    robot.disable_wobbling.assert_called_once()
    assert robot.set_target.call_count == 1
    assert robot.goto_target.call_count == 2
    assert robot.goto_target.call_args.kwargs["antennas"] == [0, 0]
    assert not any(t.name == "ha-voice-events" for t in threading.enumerate())


def test_child_failure_is_visible_and_cleaned(app_module, monkeypatch, tmp_path):
    monkeypatch.setenv("REACHY_HA_DATA_DIR", str(tmp_path))
    child = Mock(returncode=2)
    child.poll.return_value = 2
    stop_child = Mock()
    monkeypatch.setattr(app_module, "start_voice", lambda *_: child)
    monkeypatch.setattr(app_module, "stop_voice", stop_child)

    async def reader(*_):
        return

    monkeypatch.setattr(app_module, "events", reader)
    robot = Mock()
    with pytest.raises(RuntimeError, match="exit code 2"):
        app_module.ReachyMiniHaVoice().run(robot, threading.Event())
    stop_child.assert_called_once_with(child)
    assert robot.goto_target.call_count == 2
