"""Actual PCM playback + official DSP; virtual speaker, no robot connection."""
import asyncio
import tempfile
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import wave
from pathlib import Path

import numpy as np
from reachy_mini_ha_voice.tts_player import ReachyTtsPlayer


async def main():
    offsets = []
    player = ReachyTtsPlayer(offset_callback=offsets.append)
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
                player.play(f"http://127.0.0.1:{server.server_port}/speech.wav", done.set)
                await asyncio.wait_for(done.wait(), 10)
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
            music = ReachyTtsPlayer(wobble=False, offset_callback=music_offsets.append)
            try:
                music_done = asyncio.Event()
                music.play([str(path), str(path)], music_done.set)
                music.set_volume(60)
                music.duck(.5)
                assert abs(music._pipeline.get_property('volume') - .3) < 1e-3
                await asyncio.sleep(.2)
                music.pause()
                await asyncio.sleep(.2)
                assert music.is_playing
                music.unduck()
                # PulseAudio round-trips volume through its finite-resolution scale.
                volume = music._pipeline.get_property('volume')
                assert abs(volume - .6) < 1e-3, volume
                music.resume()
                await asyncio.wait_for(music_done.wait(), 10)
                assert not music.is_playing
                assert music._robot is None and not music_offsets
                calls = []
                music.play(str(path), lambda: calls.append('stopped'))
                music.stop()
                assert calls == ['stopped']
            finally:
                music.close()
            assert not music._thread.is_alive()
            print('GStreamer music: playlist, pause/resume, volume, duck, stop; no robot/offsets')
            print('Real TTS PCM -> official HeadWobbler: nonzero motion, EOS, replacement, stop passed')
    finally:
        player.close()


asyncio.run(main())
