"""Actual PCM playback + official DSP; virtual speaker, no robot connection."""
import asyncio
import tempfile
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
            player.play(str(path), done.set)
            await asyncio.wait_for(done.wait(), 10)
            assert any(any(abs(x) > 1e-8 for x in item) for item in offsets), offsets
            assert offsets[-1] == (0,) * 6
            assert not player.is_playing
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
            print('Real TTS PCM -> official HeadWobbler: nonzero motion, EOS, replacement, stop passed')
    finally:
        player.close()


asyncio.run(main())
