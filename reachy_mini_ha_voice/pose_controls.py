"""Home Assistant controls for the manual direction, served by the LVA device."""

# pylint: disable=no-name-in-module
from aioesphomeapi.api_pb2 import (  # type: ignore[attr-defined]
    ButtonCommandRequest,
    ListEntitiesButtonResponse,
    ListEntitiesNumberResponse,
    ListEntitiesRequest,
    NumberCommandRequest,
    NumberStateResponse,
    SubscribeHomeAssistantStatesRequest,
)
from aioesphomeapi.model import NumberMode

from .manual_pose import LIMITS

SLIDERS = (
    ("body", "Body Turn", "body_turn", "mdi:rotate-360"),
    ("head", "Head Turn", "head_turn", "mdi:arrow-left-right"),
    ("pitch", "Head Tilt", "head_tilt", "mdi:arrow-up-down"),
)


class DirectionNumber:
    """One slider: negative is left or down, positive is right or up."""

    def __init__(self, target, name, label, object_id, icon):
        self.server = None
        self.key = 0
        self.target = target
        self.axis = name
        self.name = label
        self.object_id = object_id
        self.icon = icon

    def state(self):
        return NumberStateResponse(key=self.key, state=self.target.get(self.axis))

    def handle_message(self, msg):
        if isinstance(msg, NumberCommandRequest) and msg.key == self.key:
            self.target.set(self.axis, msg.state)
            yield self.state()
        elif isinstance(msg, ListEntitiesRequest):
            limit = LIMITS[self.axis]
            yield ListEntitiesNumberResponse(
                object_id=self.object_id,
                key=self.key,
                name=self.name,
                icon=self.icon,
                min_value=-limit,
                max_value=limit,
                step=1.0,
                unit_of_measurement="°",
                mode=NumberMode.SLIDER,
            )
        elif isinstance(msg, SubscribeHomeAssistantStatesRequest):
            yield self.state()


class CenterButton:
    """Return body and head to the standby pose and reset the sliders."""

    def __init__(self, target, sliders):
        self.server = None
        self.key = 0
        self.target = target
        self.sliders = sliders
        self.name = "Center"
        self.object_id = "center_pose"

    def handle_message(self, msg):
        if isinstance(msg, ButtonCommandRequest) and msg.key == self.key:
            self.target.center()
            for slider in self.sliders:
                yield slider.state()
        elif isinstance(msg, ListEntitiesRequest):
            yield ListEntitiesButtonResponse(
                object_id=self.object_id,
                key=self.key,
                name=self.name,
                icon="mdi:crosshairs",
            )


def direction_controls(target):
    sliders = [DirectionNumber(target, *spec) for spec in SLIDERS]
    return [*sliders, CenterButton(target, sliders)]
