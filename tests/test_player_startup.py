"""Regression: a not-yet-started appsink must not cancel the first HA URL."""
import importlib
import sys
from enum import IntFlag
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest


@pytest.fixture
def player_module(monkeypatch):
    class MessageType(IntFlag):
        ERROR = 1
        EOS = 2

    gi = ModuleType('gi')
    gi.require_version = Mock()
    repository = ModuleType('gi.repository')
    repository.Gst = SimpleNamespace(MessageType=MessageType, State=SimpleNamespace(NULL=0))
    monkeypatch.setitem(sys.modules, 'gi', gi)
    monkeypatch.setitem(sys.modules, 'gi.repository', repository)
    name = 'reachy_mini_ha_voice.tts_player'
    sys.modules.pop(name, None)
    module = importlib.import_module(name)
    yield module
    sys.modules.pop(name, None)


def test_unstarted_sink_is_not_eof_and_real_eos_waits_for_speaker(player_module):
    module = player_module
    player = module.ReachyTtsPlayer.__new__(module.ReachyTtsPlayer)
    player._pipeline = Mock()
    bus = player._pipeline.get_bus.return_value
    bus.pop_filtered.return_value = None
    player._sink = Mock()
    player._sink.emit.return_value = None
    player._sink.get_property.return_value = True  # Real appsink in NULL/READY.
    player._pending = np.empty(0, dtype=np.float32)
    player._decoder_eos = False
    player._first_pcm = False
    player._item = 1
    player._started_at = 0
    player._audible_until = 0
    player.paused = False
    player._next = Mock()
    player._clear = Mock()
    for now in (0, 100, 1_000_000_000):
        assert not len(player.take(320, now))
        player._clear.assert_not_called()
        player._next.assert_not_called()
    # Actual EOS is necessary, and it still cannot preempt submitted PCM.
    player._audible_until = 2_000_000_000
    bus.pop_filtered.side_effect = [SimpleNamespace(type=module.Gst.MessageType.EOS), None, None]
    player.take(320, 1_000_000_000)
    player._next.assert_not_called()
    player.take(320, 2_000_000_000)
    player._clear.assert_called_once_with(flush=False)
    player._next.assert_called_once()
