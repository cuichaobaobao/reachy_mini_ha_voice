"""Manual direction: goal limits, easing, SDK signs and wake-turn hand-off."""

import pytest
from aioesphomeapi.api_pb2 import (
    ButtonCommandRequest,
    ListEntitiesButtonResponse,
    ListEntitiesNumberResponse,
    ListEntitiesRequest,
    NumberCommandRequest,
    NumberStateResponse,
    SubscribeHomeAssistantStatesRequest,
)

from reachy_mini_ha_voice.heading import Heading
from reachy_mini_ha_voice.manual_pose import ManualPose, ManualTarget
from reachy_mini_ha_voice.pose_controls import direction_controls


def test_goal_uses_official_limits_and_ignores_non_finite_values():
    target = ManualTarget()
    assert target.set("body", 200) == 160
    assert target.set("head", -90) == -65
    assert target.set("pitch", 50) == 40
    assert target.set("pitch", float("nan")) == 40
    target.center()
    assert target.snapshot() == {"body": 0.0, "head": 0.0, "pitch": 0.0}


def test_pose_eases_to_goal_with_sdk_signs():
    target = ManualTarget()
    pose = ManualPose(target)
    target.set("body", -30)  # Slider left.
    target.set("head", 20)  # Slider right.
    target.set("pitch", 10)  # Slider up.
    assert pose.sample(0.0, engaged=False) == (0.0, 0.0, 0.0)
    assert pose.rest == 30.0
    assert not pose.centered
    body, head, pitch = pose.sample(0.3, engaged=False)
    assert 0 < body < 30 and -20 < head < 0 and -10 < pitch < 0
    assert pose.sample(5.0, engaged=False) == pytest.approx((30.0, -20.0, -10.0))
    target.center()
    pose.sample(5.0, engaged=False)
    assert pose.sample(10.0, engaged=False) == pytest.approx((0.0, 0.0, 0.0))
    assert pose.centered


def test_head_offsets_step_aside_during_a_conversation_turn():
    target = ManualTarget()
    pose = ManualPose(target)
    target.set("head", -40)
    target.set("pitch", -20)
    pose.sample(0.0, engaged=False)
    assert pose.sample(5.0, engaged=False) == pytest.approx((0.0, 40.0, 20.0))
    assert pose.sample(5.0 + ManualPose.RELEASE, engaged=True) == pytest.approx((0.0, 0.0, 0.0))
    assert pose.sample(5.0 + 1.5 * ManualPose.RELEASE, engaged=False)[1] == pytest.approx(20.0)  # Halfway back.
    assert pose.sample(9.0, engaged=False) == pytest.approx((0.0, 40.0, 20.0))


def test_heading_follows_manual_body_and_returns_to_it():
    heading = Heading()
    heading.follow(30.0, 12.0)
    assert heading.sample(0.0) == 12.0
    heading.follow(30.0, 30.0)
    heading.event({"event": "wake_word_detected"}, 1.0)  # No direction: stays put.
    heading.event({"event": "tts_finished"}, 2.0)
    heading.follow(30.0, 0.0)  # Manual pose is ignored while the turn owns the heading.
    assert heading.sample(3.0) == 30.0
    heading.follow(-10.0, 0.0)  # Manual direction changed before the return.
    heading.sample(7.0)
    assert heading.active
    assert heading.sample(8.5) == pytest.approx(-10.0)
    assert not heading.active


def test_heading_return_replans_when_manual_body_changes():
    heading = Heading()
    heading.event({"event": "wake_word_detected"}, 0.0)
    heading.event({"event": "idle"}, 0.0)
    heading.sample(5.0)  # Return to 0 starts.
    heading.follow(45.0, 0.0)
    heading.sample(5.5)  # Re-planned toward the new rest.
    assert heading.sample(7.0) == pytest.approx(45.0)
    assert not heading.active


def test_home_assistant_controls_report_and_set_the_goal():
    target = ManualTarget()
    controls = direction_controls(target)
    for key, entity in enumerate(controls):
        entity.key = key
    body, head, pitch, center = controls
    listed = [msg for entity in controls for msg in entity.handle_message(ListEntitiesRequest())]
    assert [type(msg) for msg in listed] == [ListEntitiesNumberResponse] * 3 + [ListEntitiesButtonResponse]
    assert [(msg.object_id, msg.min_value, msg.max_value) for msg in listed[:3]] == [
        ("body_turn", -160, 160), ("head_turn", -65, 65), ("head_tilt", -40, 40)]
    (state,) = head.handle_message(NumberCommandRequest(key=1, state=99))
    assert state == NumberStateResponse(key=1, state=65)
    assert list(body.handle_message(NumberCommandRequest(key=1, state=5))) == []
    pitch.handle_message(NumberCommandRequest(key=2, state=-15)).__next__()
    assert list(pitch.handle_message(SubscribeHomeAssistantStatesRequest())) == [
        NumberStateResponse(key=2, state=-15)]
    states = list(center.handle_message(ButtonCommandRequest(key=3)))
    assert states == [NumberStateResponse(key=k, state=0) for k in range(3)]
    assert target.snapshot() == {"body": 0.0, "head": 0.0, "pitch": 0.0}
