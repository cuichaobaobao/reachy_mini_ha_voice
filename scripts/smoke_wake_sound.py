"""Actual SDK file playback with a captured virtual speaker; no robot/HA access."""
import asyncio
import threading
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import soundfile as sf
from gi.repository import Gst
from reachy_mini.media.media_manager import MediaBackend, MediaManager

from reachy_mini_ha_voice.sdk_audio import SdkAudio
from reachy_mini_ha_voice.tts_player import ReachyTtsPlayer
from virtual_audio import VirtualAudio, install


async def main():
    Gst.init(None)
    outputs = []

    def speaker(self):
        sink = Gst.ElementFactory.make('fakesink')
        sink.set_property('sync', True)
        sink.set_property('async', False)
        sink.set_property('signal-handoffs', True)
        chunks = []
        outputs.append(chunks)

        def capture(_, buffer, pad):
            caps = pad.get_current_caps().get_structure(0)
            chunks.append((caps.get_string('format'), caps.get_value('rate'),
                           caps.get_value('channels'), buffer.extract_dup(0, buffer.get_size())))
        sink.connect('handoff', capture)
        return sink

    VirtualAudio._build_audiosink_element = speaker
    install()
    MediaManager._init_camera = lambda *args: None
    media = MediaManager(backend=MediaBackend.LOCAL)
    offsets = []
    audio = SdkAudio(robot=SimpleNamespace(media=media), offset_callback=offsets.append)
    path = Path(__file__).resolve().parents[1] / 'reachy_mini_ha_voice/vendor/lva/sounds/wake_word_triggered.flac'
    expected, rate = sf.read(path, dtype='float32')
    player = ReachyTtsPlayer(audio, wake_sound=str(path))
    try:
        for _ in range(3):
            done = asyncio.Event()
            player.play(str(path), done.set)
            await asyncio.wait_for(done.wait(), 5)
            # Duration-based callbacks are not speaker acknowledgements. Allow
            # the actual SDK pipeline to drain before inspecting its output.
            await asyncio.sleep(.2)
            chunks = outputs[-1]
            assert chunks, 'SDK file player produced no output'
            fmt, actual_rate, channels, _ = chunks[0]
            assert actual_rate == rate, (actual_rate, rate)
            dtype, scale = {'F32LE': ('<f4', 1), 'S16LE': ('<i2', 32768),
                            'S32LE': ('<i4', 2147483648)}[fmt]
            actual = np.frombuffer(b''.join(c[3] for c in chunks), dtype=dtype)
            actual = actual.reshape(-1, channels)[:, 0].astype(np.float64) / scale
            assert len(actual) == len(expected), (len(actual), len(expected))
            np.testing.assert_allclose(actual, expected, atol=2 / 32768)
            assert not player.is_playing
            assert (await asyncio.to_thread(audio.record, 320)).shape == (320, 1)
        assert not offsets, 'Wake sound entered the TTS motion path'
        calls = []
        player.play(str(path), lambda: calls.append('obsolete'))
        await asyncio.sleep(.1)
        player.stop()
        await asyncio.sleep(.1)
        assert calls == []
        player.play(str(path), lambda: calls.append('closed'))
        await asyncio.sleep(.1)
        player.close()
        await asyncio.sleep(.1)
        assert calls == []
        assert not any(t.name == 'ha-wake-sound' for t in threading.enumerate())
        print('SDK wake chime: 3 complete waveforms including onset; cancellation, microphone and cleanup passed')
    finally:
        player.close()
        await audio.close()
        media.close()


asyncio.run(main())
