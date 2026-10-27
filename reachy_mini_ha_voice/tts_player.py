"""Bounded GStreamer decoding; the shared SDK audio owner performs playback."""

import asyncio
import logging
import threading
import time
from functools import wraps
from pathlib import Path
from urllib.parse import urlparse

import gi
import numpy as np

gi.require_version("Gst", "1.0")
from gi.repository import Gst

from .wake_sound import WakeSound

_LOG = logging.getLogger(__name__)


def on_owner(method):
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        if threading.get_ident() != self._owner:
            self._async_loop.call_soon_threadsafe(lambda: method(self, *args, **kwargs))
            return None
        return method(self, *args, **kwargs)
    return wrapped


class ReachyTtsPlayer:
    def __init__(self, audio, wobble=True, wake_sound=None):
        self.audio = audio
        self.wobble = wobble
        self._wake_path = Path(wake_sound).resolve() if wake_sound else None
        self._wake = None
        self._owner = threading.get_ident()
        self._async_loop = asyncio.get_running_loop()
        self._pipeline = None
        self._sink = None
        self._callback = None
        self._urls = []
        self._pending = np.empty(0, dtype=np.float32)
        self._volume = self._duck = 1.0
        self._audible_until = 0
        self._contributed = False
        self.paused = False
        self._closed = False
        self._decoder_eos = False
        self._first_pcm = False
        self._started_at = 0.0
        self._item = 0
        audio.players.append(self)

    @property
    def gain(self):
        return self._volume * self._duck

    @property
    def is_playing(self):
        return self._pipeline is not None or self._wake is not None

    @property
    def rendering(self):
        """True while the shared render loop must pull decoded audio from this player."""
        return self._pipeline is not None and not self.paused

    @property
    def is_paused(self):
        # Same meaning as upstream LVA players: loaded but paused.
        return self.paused and self.is_playing

    @property
    def is_speech(self):
        return self.wobble and self.is_playing and self._wake is None and not self.paused

    @on_owner
    def play(self, url, done_callback=None, stop_first=False):
        self._clear(flush=True)
        self._urls = [url] if isinstance(url, str) else list(url)
        self._callback = done_callback
        self.paused = False
        self._next()

    def _next(self):
        if not self._urls:
            callback, self._callback = self._callback, None
            if callback:
                callback()
            return
        url = self._urls.pop(0)
        if self._wake_path is not None and not urlparse(url).scheme and Path(url).resolve() == self._wake_path:
            playback = WakeSound(
                self.audio, str(self._wake_path), self.gain,
                lambda error: self._async_loop.call_soon_threadsafe(self._wake_finished, playback, error),
            )
            self._wake = playback
            playback.start()
            return
        if not urlparse(url).scheme:
            url = Path(url).resolve().as_uri()
        self._decoder_eos = False
        self._first_pcm = False
        self._started_at = time.monotonic()
        self._item += 1
        parsed = urlparse(url)
        # Never log signed URLs, query tokens, credentials or announcement text.
        _LOG.info("Audio item %d starting: scheme=%s host=%s", self._item, parsed.scheme, parsed.hostname)
        sink = Gst.parse_bin_from_description(
            f'audioconvert ! audioresample ! audio/x-raw,format=F32LE,rate={self.audio.rate},channels=1 '
            '! appsink name=decoded sync=false max-buffers=4 drop=false', True
        )
        self._sink = sink.get_by_name("decoded")
        self._pipeline = Gst.ElementFactory.make("playbin")
        self._pipeline.set_property("uri", url)
        self._pipeline.set_property("audio-sink", sink)
        self._pipeline.set_property("video-sink", Gst.ElementFactory.make("fakesink"))
        if self._pipeline.set_state(Gst.State.PLAYING) == Gst.StateChangeReturn.FAILURE:
            self._failed("Cannot start audio decoder")
            return
        self.audio.wake()

    def _wake_finished(self, playback, error):
        # Cancellation/replacement may already have invalidated this callback.
        if self._wake is not playback:
            return
        self._wake = None
        if error is not None:
            _LOG.error("Wake sound playback failed: %s", error)
        self._next()

    def _failed(self, reason):
        _LOG.error("Audio playback failed: %s", reason)
        self._clear(flush=True)
        self._urls = []
        self._next()

    def take(self, frames, now):
        self._contributed = False
        if self._pipeline is None or self.paused:
            return np.empty(0, dtype=np.float32)
        bus = self._pipeline.get_bus()
        while message := bus.pop_filtered(Gst.MessageType.ERROR | Gst.MessageType.EOS):
            if message.type == Gst.MessageType.ERROR:
                self._failed(str(message.parse_error()[0]))
                return np.empty(0, dtype=np.float32)
            self._decoder_eos = True
        while len(self._pending) < frames:
            sample = self._sink.emit("try-pull-sample", 0)
            if sample is None:
                break
            buffer = sample.get_buffer()
            ok, mapped = buffer.map(Gst.MapFlags.READ)
            if ok:
                try:
                    self._pending = np.concatenate((self._pending, np.frombuffer(mapped.data, dtype='<f4')))
                finally:
                    buffer.unmap(mapped)
        result, self._pending = self._pending[:frames], self._pending[frames:]
        self._contributed = bool(len(result))
        if len(result) and not self._first_pcm:
            self._first_pcm = True
            _LOG.info("Audio item %d first PCM after %.3fs", self._item, time.monotonic() - self._started_at)
        # appsink.eos also returns True in NULL/READY, before playback starts.
        # Only an actual bus EOS proves decoding ended; never cancel cold startup.
        # Decoder EOS means data decoded, not sound finished. Wait for the SDK
        # clock to reach the final submitted sample plus pipeline latency.
        if not len(result) and self._decoder_eos and now >= self._audible_until:
            _LOG.info("Audio item %d finished after %.3fs", self._item, time.monotonic() - self._started_at)
            self._clear(flush=False)
            self._next()
        return result

    def _clear(self, flush):
        if self._wake is not None:
            playback, self._wake = self._wake, None
            playback.stop()
        if self._pipeline is not None:
            self._pipeline.set_state(Gst.State.NULL)
            if flush:
                self.audio.flush()
        self._pipeline = self._sink = None
        self._pending = np.empty(0, dtype=np.float32)
        self._audible_until = 0

    @on_owner
    def stop(self):
        was_wake = self._wake is not None
        self._clear(flush=True)
        self._urls = []
        callback, self._callback = self._callback, None
        if callback and not was_wake:
            callback()

    @on_owner
    def pause(self):
        if self.is_playing and not self.paused:
            self.paused = True
            self.audio.flush()

    @on_owner
    def resume(self):
        self.paused = False
        self.audio.wake()

    @on_owner
    def set_volume(self, volume):
        self._volume = max(0.0, min(1.0, volume / 100))
        if self._wake is not None:
            self._wake.set_gain(self.gain)

    @on_owner
    def duck(self, factor=0.5):
        self._duck = max(0.0, min(1.0, factor))
        if self._wake is not None:
            self._wake.set_gain(self.gain)

    @on_owner
    def unduck(self):
        self._duck = 1.0
        if self._wake is not None:
            self._wake.set_gain(self.gain)

    @on_owner
    def close(self):
        if self._closed:
            return
        self._closed = True
        self.stop()
        self.audio.players.remove(self)
