"""LVA TTS playback with the SDK's clock-driven HeadWobbler.

Music uses this player with wobbling disabled. A local daemon client sends only speech offsets;
the app remains the sole owner of the base head pose and antenna targets.
"""

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
from gi.repository import GLib, Gst
from reachy_mini.motion.head_wobbler import HeadWobbler

_LOG = logging.getLogger(__name__)


class _PlaybackLoop:
    """One owner for GLib's default context used by SDK HeadWobbler timers."""
    _lock = threading.Lock()
    _users = 0
    _loop = None
    _thread = None

    @classmethod
    def acquire(cls):
        with cls._lock:
            if cls._users == 0:
                cls._loop = GLib.MainLoop()
                cls._thread = threading.Thread(target=cls._loop.run, daemon=True)
                cls._thread.start()
            cls._users += 1
            return cls._thread

    @classmethod
    def release(cls):
        with cls._lock:
            cls._users -= 1
            if cls._users == 0:
                cls._loop.quit()
                cls._thread.join(timeout=3)


def on_owner(method):
    """LVA also calls players from its microphone thread."""
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        if threading.get_ident() != self._owner:
            self._async_loop.call_soon_threadsafe(lambda: method(self, *args, **kwargs))
            return None
        return method(self, *args, **kwargs)
    return wrapped


class ReachyTtsPlayer:
    def __init__(self, device=None, offset_callback=None, wobble=True):
        self._owner = threading.get_ident()
        Gst.init(None)
        self._async_loop = asyncio.get_running_loop()
        self._thread = _PlaybackLoop.acquire()
        self._closed = False
        self._wobble = wobble
        self._device = device
        self._robot = None
        self._offset_callback = offset_callback
        self._pipeline = None
        self._wobbler = None
        self._callback = None
        self._urls = []
        self._volume = 1.0
        self._duck = 1.0
        self._generation = 0

    def _offsets(self, offsets):
        if self._offset_callback is not None:
            self._offset_callback(offsets)
        else:
            from reachy_mini.io.protocol import SetSpeechOffsetsCmd
            self._robot.client.send_command(SetSpeechOffsetsCmd(offsets=list(offsets)))

    @on_owner
    def play(self, url, done_callback=None, stop_first=False):
        self._clear()
        self._urls = [url] if isinstance(url, str) else list(url)
        self._callback = done_callback
        if self._wobble and self._robot is None and self._offset_callback is None:
            from reachy_mini import ReachyMini
            self._robot = ReachyMini(
                media_backend="no_media", connection_mode="localhost_only"
            )
        self._next()

    def _next(self):
        if not self._urls:
            callback, self._callback = self._callback, None
            if callback:
                callback()
            return
        url = self._urls.pop(0)
        if not urlparse(url).scheme:
            url = Path(url).resolve().as_uri()
        # Both branches use the same pipeline clock. appsink sync=True releases
        # PCM at playback time, as in the SDK's GStreamer audio sink tee.
        if self._wobble:
            description = (
                'audioconvert ! audioresample ! audio/x-raw,format=F32LE,rate=16000,channels=1 '
                '! tee name=t t. ! queue ! audioconvert ! audioresample '
                '! pulsesink name=speaker t. ! queue ! appsink name=motion '
                'emit-signals=true sync=true max-buffers=8 drop=false'
            )
        else:
            # Preserve music channels/rate and never connect a robot or emit offsets.
            description = 'audioconvert ! audioresample ! pulsesink name=speaker'
        sink = Gst.parse_bin_from_description(description, True)
        if self._device:
            sink.get_by_name("speaker").set_property(
                "device", None if self._device == "pulse/default" else self._device.removeprefix("pulse/")
            )
        pipeline = Gst.ElementFactory.make("playbin")
        pipeline.set_property("uri", url)
        pipeline.set_property("audio-sink", sink)
        pipeline.set_property("video-sink", Gst.ElementFactory.make("fakesink"))
        pipeline.set_property("volume", self._volume * self._duck)
        wobbler = None
        if self._wobble:
            wobbler = HeadWobbler(self._offsets, sample_rate=16000)
            wobbler.start()
            sink.get_by_name("motion").connect("new-sample", self._sample, wobbler)
        bus = pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self._message, self._generation)
        self._pipeline, self._wobbler = pipeline, wobbler
        if pipeline.set_state(Gst.State.PLAYING) == Gst.StateChangeReturn.FAILURE:
            self._finish(self._generation, "Unable to start TTS audio sink")

    @staticmethod
    def _sample(sink, wobbler):
        sample = sink.emit("pull-sample")
        if sample is None:
            return Gst.FlowReturn.EOS
        buffer = sample.get_buffer()
        ok, mapped = buffer.map(Gst.MapFlags.READ)
        if ok:
            try:
                # The synchronized appsink has already waited for buffer PTS.
                wobbler.feed(np.frombuffer(mapped.data, dtype="<f4").copy(),
                             time.monotonic_ns())
            finally:
                buffer.unmap(mapped)
        return Gst.FlowReturn.OK

    def _message(self, bus, message, generation):
        if message.type == Gst.MessageType.EOS:
            self._async_loop.call_soon_threadsafe(self._finish, generation, None)
        elif message.type == Gst.MessageType.ERROR:
            error, _ = message.parse_error()
            self._async_loop.call_soon_threadsafe(self._finish, generation, str(error))

    def _finish(self, generation, error):
        if generation != self._generation:
            return
        self._clear()
        if error:
            _LOG.error("TTS playback failed: %s", error)
            self._urls = []
        self._next()

    def _clear(self):
        self._generation += 1
        if self._pipeline is not None:
            self._pipeline.set_state(Gst.State.NULL)
            self._pipeline.get_bus().remove_signal_watch()
            self._pipeline = None
        if self._wobbler is not None:
            self._wobbler.stop()
            self._wobbler = None

    @on_owner
    def stop(self):
        self._clear()
        self._urls = []
        callback, self._callback = self._callback, None
        if callback:
            callback()

    @on_owner
    def pause(self):
        if self._pipeline is not None:
            self._pipeline.set_state(Gst.State.PAUSED)
            if self._wobbler is not None:
                self._wobbler.stop()

    @on_owner
    def resume(self):
        if self._pipeline is not None:
            if self._wobbler is not None:
                self._wobbler.start()
            self._pipeline.set_state(Gst.State.PLAYING)

    @property
    def is_playing(self):
        return self._pipeline is not None

    @on_owner
    def set_volume(self, volume):
        self._volume = max(0.0, min(1.0, volume / 100))
        self._apply_volume()

    @on_owner
    def duck(self, factor=0.5):
        self._duck = max(0.0, min(1.0, factor))
        self._apply_volume()

    @on_owner
    def unduck(self):
        self._duck = 1.0
        self._apply_volume()

    def _apply_volume(self):
        if self._pipeline is not None:
            self._pipeline.set_property("volume", self._volume * self._duck)

    @on_owner
    def close(self):
        if self._closed:
            return
        self._closed = True
        self.stop()
        _PlaybackLoop.release()
        if self._robot is not None:
            self._robot.__exit__(None, None, None)
