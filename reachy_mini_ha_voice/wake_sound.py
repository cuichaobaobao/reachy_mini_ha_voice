"""Local wake chime: SDK file playback on a worker, timed by file duration.

SDK 1.12 has no public stop-file or file-volume method. Keep the playbin
compatibility access here; never stop the shared recording/PCM pipeline.
"""

import logging
import threading

_LOG = logging.getLogger(__name__)


class WakeSound:
    def __init__(self, audio, path, gain, finished):
        self.audio, self.path = audio, path
        self.gain, self.finished = gain, finished
        self.cancelled = threading.Event()
        self._player = None
        self._thread = threading.Thread(target=self._run, name="ha-wake-sound")

    def start(self):
        self._thread.start()

    def _run(self):
        error = None
        try:
            import soundfile as sf

            info = sf.info(self.path)
            duration = info.frames / info.samplerate
            if duration <= 0:
                raise ValueError("Wake sound has no audio frames")
            if self.cancelled.is_set():
                return
            self.audio.media.play_sound(self.path)
            self._player = self.audio.backend._playbin
            if self._player is None:
                raise RuntimeError("SDK did not create the wake sound player")
            self.set_gain(self.gain)
            _LOG.info("Wake sound: SDK file playback, duration %.3fs", duration)
            # Completion uses elapsed file duration, not a hardware playback
            # acknowledgement. A stop signal interrupts the wait immediately.
            self.cancelled.wait(duration)
        except Exception as exc:  # noqa: BLE001 - report playback worker failure to owner.
            error = exc
        finally:
            if self.cancelled.is_set():
                self._stop_player()
            else:
                self.finished(error)

    def set_gain(self, gain):
        self.gain = gain
        if self._player is not None:
            self._player.set_property("volume", gain)

    def _stop_player(self):
        if self._player is not None:
            from gi.repository import Gst

            self._player.set_state(Gst.State.NULL)

    def stop(self):
        self.cancelled.set()
        self._thread.join()
        self._stop_player()
