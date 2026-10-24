"""CI substitutes only physical endpoints; SDK mixer/clock/capture remain real.

ALSA's null capture device does not behave as a clocked microphone on the
GitHub runner. Use a live GStreamer test source and synchronized fake speaker.
This is not validation of the robot's ALSA driver or physical audio latency.
"""
from reachy_mini.media import audio_gstreamer
from gi.repository import Gst


class VirtualAudio(audio_gstreamer.GStreamerAudio):
    def _init_pipeline_record(self, pipeline):
        capture = Gst.parse_bin_from_description(
            'audiotestsrc is-live=true samplesperbuffer=320 wave=sine freq=180 volume=0.1 '
            '! audio/x-raw,format=F32LE,rate=16000,channels=2 '
            '! appsink name=capture sync=false max-buffers=8 drop=true', False
        )
        self._appsink_audio = capture.get_by_name('capture')
        pipeline.add(capture)

    def _build_audiosink_element(self):
        sink = Gst.ElementFactory.make('fakesink')
        sink.set_property('sync', True)
        sink.set_property('async', False)
        return sink


def install():
    audio_gstreamer.GStreamerAudio = VirtualAudio
