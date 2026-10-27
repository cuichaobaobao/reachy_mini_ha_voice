"""Hardware-independent checks for the SDK/LVA microphone contract."""
import threading
from unittest.mock import Mock

import numpy as np
import pytest

from reachy_mini_ha_voice.sdk_audio import SdkAudio


def recorder(samples):
    audio = SdkAudio.__new__(SdkAudio)
    audio.backend = Mock()
    audio.media = audio.backend
    audio.backend.get_audio_sample.side_effect = samples
    audio.closed = threading.Event()
    audio._input = np.empty((0, 1), dtype=np.float32)
    return audio


def test_variable_sdk_chunks_keep_mic_channel_and_exact_frames():
    samples = np.column_stack((np.arange(700, dtype=np.float32), np.full(700, -999)))
    audio = recorder([samples[:83], samples[83:400], samples[400:]])
    first = audio.record(320)
    second = audio.record(320)
    assert first.shape == second.shape == (320, 1)
    np.testing.assert_array_equal(np.concatenate((first, second))[:, 0], np.arange(640))
    np.testing.assert_array_equal(audio._input[:, 0], np.arange(640, 700))


def test_mono_capture_and_shutdown_unblocks_reader():
    audio = recorder([np.ones(320, dtype=np.float32)])
    assert audio.record(320).shape == (320, 1)
    audio.closed.set()
    with pytest.raises(EOFError):
        audio.record(320)


def test_unsupported_channel_contract_fails_explicitly():
    audio = recorder([])
    with pytest.raises(ValueError), audio.recorder(samplerate=16000, channels=2, blocksize=320):
        pass


def test_wobbler_connection_loss_is_cosmetic_not_audio_failure(monkeypatch):
    import sys
    from types import ModuleType
    protocol = ModuleType('reachy_mini.io.protocol')
    protocol.SetSpeechOffsetsCmd = lambda **kwargs: kwargs
    monkeypatch.setitem(sys.modules, 'reachy_mini.io.protocol', protocol)
    audio = SdkAudio.__new__(SdkAudio)
    audio._offset_callback = None
    audio._robot = Mock()
    audio._robot.client.send_command.side_effect = ConnectionError('lost heartbeat')
    audio._offsets([0] * 6)  # Must also allow wobbler.stop() during cleanup.


def test_render_loop_idles_until_a_player_starts():
    import asyncio
    from types import SimpleNamespace

    async def scenario():
        audio = SdkAudio.__new__(SdkAudio)
        audio.closed = threading.Event()
        audio._capture_failed = threading.Event()
        audio._activity = asyncio.Event()
        audio._speech = False
        audio.players = []
        audio.rate = 16000
        audio.wobbler = Mock()
        audio.backend = SimpleNamespace(_appsrc_pts=0)
        audio.media = Mock()
        audio.media.get_output_channels.return_value = 2
        ticks = []
        audio.clock = lambda: (ticks.append(1), (10_000_000_000, 0))[1]
        task = asyncio.create_task(audio._render())
        await asyncio.sleep(0.1)
        assert not ticks  # No 5 ms polling while nothing plays.
        player = SimpleNamespace(rendering=True, is_speech=False, wobble=False, gain=1.0,
                                 _contributed=False, _audible_until=0,
                                 take=lambda frames, now: np.empty(0, dtype=np.float32))
        audio.players.append(player)
        audio.wake()
        await asyncio.sleep(0.05)
        assert ticks  # Woken immediately, not after the idle timeout.
        player.rendering = False
        await asyncio.sleep(0.05)
        idle_ticks = len(ticks)
        await asyncio.sleep(0.1)
        assert len(ticks) == idle_ticks
        audio.closed.set()
        await asyncio.wait_for(task, 1)

    asyncio.run(scenario())
