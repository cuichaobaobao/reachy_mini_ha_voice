"""Verify the actual vendored wake handler captures direction before any chime."""
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from reachy_mini_ha_voice.direction import DirectionReader

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'reachy_mini_ha_voice/vendor/lva'))
from linux_voice_assistant.satellite import VoiceSatelliteProtocol

for listen_during_sound in (False, True):
    order = []
    reader = DirectionReader()
    reader.update({'doa': {'angle': 1.0, 'speech_detected': True},
                   'head_pose': {'yaw': .2}}, time.monotonic())
    state = SimpleNamespace(muted=False, wake_direction_reader=reader,
                            tts_player=Mock(), listen_during_wake_sound=listen_during_sound,
                            wakeup_sound='wake.flac')
    state.tts_player.play.side_effect = lambda *a, **kw: order.append('chime')
    protocol = VoiceSatelliteProtocol.__new__(VoiceSatelliteProtocol)
    protocol.state = state
    protocol._pipeline_active = False
    protocol.duck = Mock()
    protocol._start_audio_streaming = Mock()

    def emit(event, data):
        assert data['direction']['angle'] == 1.0
        assert data['direction']['head_yaw'] == .2
        order.append('direction')

    protocol._emit = emit
    protocol.wakeup(SimpleNamespace(wake_word='Okay Nabu'))
    assert order == ['direction', 'chime'], order
    protocol.wakeup(SimpleNamespace(wake_word='Okay Nabu'))
    assert order == ['direction', 'chime'], 'Active conversation must ignore duplicate wakes'
print('Actual LVA wake handler: direction captured before chime in both listening modes')
