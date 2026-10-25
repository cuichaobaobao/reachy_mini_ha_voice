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
    player._wake = None
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


def test_wake_file_uses_sdk_and_completion_runs_on_owner_loop(player_module, monkeypatch, tmp_path):
    import asyncio
    import threading

    monkeypatch.setitem(sys.modules, 'soundfile', SimpleNamespace(
        info=lambda _: SimpleNamespace(frames=480, samplerate=16000)))

    async def run():
        owner = threading.get_ident()
        audio = SimpleNamespace(players=[], rate=16000, media=Mock(), backend=Mock(), flush=Mock())
        wake = tmp_path / 'wake.flac'
        player = player_module.ReachyTtsPlayer(audio, wake_sound=str(wake))
        callbacks = []
        player.set_volume(60)
        def played(path):
            assert threading.get_ident() != owner
            assert path == str(wake)
        audio.media.play_sound.side_effect = played
        try:
            for _ in range(3):
                done = asyncio.Event()
                def finished(done=done):
                    callbacks.append(threading.get_ident())
                    done.set()
                player.play(str(wake), finished)
                assert player.is_playing and not player.is_speech
                assert len(player.take(320, 0)) == 0  # Never enters PCM mixer.
                await asyncio.wait_for(done.wait(), 1)
                assert not player.is_playing
            assert callbacks == [owner] * 3
            assert audio.media.play_sound.call_count == 3
            audio.backend._playbin.set_property.assert_called_with('volume', .6)
            audio.flush.assert_not_called()
            # Only the configured chime uses direct playback; TTS stays decoded.
            player._wake_path = None
            player._next = Mock()
            player.play('https://ha.example/tts.mp3')
            assert player._urls == ['https://ha.example/tts.mp3']
            player._next.assert_called_once()
        finally:
            player.close()
        assert not any(t.name == 'ha-wake-sound' for t in threading.enumerate())
    asyncio.run(run())


def test_wake_cancel_and_replacement_cannot_start_obsolete_listening(player_module, monkeypatch, tmp_path):
    import asyncio
    import threading

    monkeypatch.setitem(sys.modules, 'soundfile', SimpleNamespace(
        info=lambda _: SimpleNamespace(frames=1600, samplerate=16000)))

    async def run():
        audio = SimpleNamespace(players=[], rate=16000, media=Mock(), backend=Mock(), flush=Mock())
        wake = str(tmp_path / 'wake.flac')
        player = player_module.ReachyTtsPlayer(audio, wake_sound=wake)
        calls = []
        try:
            player.play(wake, lambda: calls.append('cancelled'))
            await asyncio.sleep(.02)
            player.stop()
            await asyncio.sleep(.12)
            assert calls == []
            audio.backend._playbin.set_state.assert_called_with(player_module.Gst.State.NULL)
            player.play(wake, lambda: calls.append('replaced'))
            await asyncio.sleep(.02)
            player.play(wake, lambda: calls.append('current'))
            await asyncio.sleep(.2)
            assert calls == ['current']
            # Even a completion already queued on the owner loop is invalidated.
            player.play(wake, lambda: calls.append('closed'))
            previous = player._wake
            player.close()
            player._wake_finished(previous, None)
            assert calls == ['current']
            assert not any(t.name == 'ha-wake-sound' for t in threading.enumerate())
        finally:
            player.close()
    asyncio.run(run())
