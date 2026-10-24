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
