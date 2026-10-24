from types import SimpleNamespace
from unittest.mock import Mock

from reachy_mini_ha_voice.motion_link import MotionLink


def test_transient_motion_failure_does_not_escape_or_recreate_media():
    robot = Mock()
    robot.set_target.side_effect = [ConnectionError('heartbeat'), None]
    factory = Mock()
    link = MotionLink(robot, factory=factory)
    assert not link.send(head='pose')
    assert link.send(head='pose')
    factory.assert_not_called()
    robot.media.close.assert_not_called()
    link.close()


def test_persistent_outage_reconnects_only_sdk_client():
    now = [0.]
    old, new = Mock(host='localhost', port=8000), Mock()
    robot = SimpleNamespace(client=old, set_target=Mock(side_effect=ConnectionError('closed')))
    factory = Mock(return_value=new)
    link = MotionLink(robot, factory=factory, clock=lambda: now[0])
    assert not link.send()
    now[0] = 6
    assert not link.send()
    link._thread.join(2)
    assert robot.client is new
    old.disconnect.assert_called_once()
    new.wait_for_connection.assert_called_once_with(timeout=3)
    link.close()
