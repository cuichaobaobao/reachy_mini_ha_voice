"""Actual PCM playback + official DSP; virtual speaker, no robot connection."""
import asyncio
import tempfile
import threading
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import wave
from pathlib import Path

import numpy as np
from reachy_mini_ha_voice.tts_player import ReachyTtsPlayer
from reachy_mini_ha_voice.sdk_audio import SdkAudio
from types import SimpleNamespace
from virtual_audio import install
from reachy_mini.media.media_manager import MediaBackend, MediaManager


async def main():
    # Real GStreamer reproduction: NULL appsink reports eos before any URL
    # has started. Older player.take() closed this pipeline on its first poll.
    from gi.repository import Gst
    from unittest.mock import Mock
    cold_audio = SimpleNamespace(players=[], rate=16000, flush=Mock())
    cold = ReachyTtsPlayer(cold_audio)
    cold._pipeline = Gst.Pipeline.new("cold-regression")
    cold._sink = Gst.ElementFactory.make("appsink")
    cold._pipeline.add(cold._sink)
    completed = []
    cold._callback = lambda: completed.append(True)
    assert cold._sink.get_property("eos") is True
    for _ in range(10):
        assert len(cold.take(320, 0)) == 0
        assert cold.is_playing, "Cold decoder incorrectly treated as completed"
        assert not completed
        await asyncio.sleep(.01)
    cold.close()
    print("Real NULL-state appsink EOS cannot cancel cold playback: passed")
    offsets = []
    install()
    MediaManager._init_camera = lambda *args: None
    media = MediaManager(backend=MediaBackend.LOCAL)
    audio = SdkAudio(robot=SimpleNamespace(media=media), offset_callback=offsets.append)
    player = ReachyTtsPlayer(audio)
    captured = await asyncio.to_thread(audio.record, 320)
    assert captured.shape == (320, 1)
    try:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "speech.wav"
            t = np.arange(32000) / 16000
            pcm = (0.4 * np.sin(2 * np.pi * 180 * t)
                   * (0.5 + 0.5 * np.sin(2 * np.pi * 4 * t)))
            with wave.open(str(path), "wb") as f:
                f.setnchannels(1)
                f.setsampwidth(2)
                f.setframerate(16000)
                f.writeframes((pcm * 32767).astype('<i2').tobytes())
            done = asyncio.Event()
            server = ThreadingHTTPServer(
                ("127.0.0.1", 0), partial(SimpleHTTPRequestHandler, directory=directory)
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                started = time.monotonic()
                player.play(f"http://127.0.0.1:{server.server_port}/speech.wav", done.set)
                await asyncio.wait_for(done.wait(), 10)
                assert time.monotonic() - started >= 1.8, "EOS fired before audible PCM drained"
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)
            assert any(any(abs(x) > 1e-8 for x in item) for item in offsets), offsets
            assert offsets[-1] == (0,) * 6
            assert not player.is_playing
            done.clear()
            player.play(str(path), done.set)
            await asyncio.sleep(0.3)
            player.pause()
            await asyncio.sleep(0.15)
            paused_count = len(offsets)
            await asyncio.sleep(0.2)
            assert len(offsets) == paused_count, 'Offsets continued while paused'
            player.resume()
            await asyncio.wait_for(done.wait(), 10)
            calls = []
            player.play(str(path), lambda: calls.append('obsolete'))
            await asyncio.sleep(0.3)
            player.play(str(path), lambda: calls.append('current'))
            await asyncio.sleep(0.3)
            player.stop()
            count = len(offsets)
            await asyncio.sleep(0.3)
            assert calls == ['current'], calls
            assert offsets[-1] == (0,) * 6
            assert len(offsets) == count, 'Offsets continued after interruption'
            music_offsets = []
            music = ReachyTtsPlayer(audio, wobble=False)
            music_offsets.extend(offsets)
            try:
                music_done = asyncio.Event()
                music.play([str(path), str(path)], music_done.set)
                music.set_volume(60)
                music.duck(.5)
                assert abs(music.gain - .3) < 1e-3
                await asyncio.sleep(.2)
                music.pause()
                await asyncio.sleep(.2)
                assert music.is_playing
                music.unduck()
                # PulseAudio round-trips volume through its finite-resolution scale.
                volume = music.gain
                assert abs(volume - .6) < 1e-3, volume
                music.resume()
                await asyncio.wait_for(music_done.wait(), 10)
                assert not music.is_playing
                assert offsets == music_offsets
                calls = []
                music.play(str(path), lambda: calls.append('stopped'))
                music.stop()
                assert calls == ['stopped']
                speech_done, music_done = asyncio.Event(), asyncio.Event()
                before = len(offsets)
                player.play(str(path), speech_done.set)
                music.play(str(path), music_done.set)
                await asyncio.wait_for(asyncio.gather(speech_done.wait(), music_done.wait()), 10)
                assert any(any(abs(x) > 1e-8 for x in item) for item in offsets[before:])
                assert (await asyncio.to_thread(audio.record, 320)).shape == (320, 1)
            finally:
                music.close()
            assert not audio.task.done()
            assert (await asyncio.to_thread(audio.record, 320)).shape == (320, 1)
            print('GStreamer music: playlist, pause/resume, volume, duck, stop; no robot/offsets')
            print('Real TTS PCM -> official HeadWobbler: nonzero motion, EOS, replacement, stop passed')
    finally:
        player.close()
        await audio.close()
        assert not audio.backend._thread_bus_calls.is_alive()
        media.close()


asyncio.run(main())
