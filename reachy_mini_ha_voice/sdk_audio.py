"""Single SDK audio owner, shared by the LVA recorder and media players."""

import asyncio
import threading
import time
from contextlib import contextmanager

import numpy as np
from websockets.exceptions import ConnectionClosed


class SdkAudio:
    name = "Reachy Mini SDK microphone"

    def __init__(self, backend=None, offset_callback=None, robot=None):
        from reachy_mini.motion.head_wobbler import HeadWobbler

        self._owns_robot = robot is None and backend is None
        if self._owns_robot:
            from reachy_mini import ReachyMini
            robot = ReachyMini(media_backend="local", connection_mode="localhost_only")
        self._robot = robot
        self.media = robot.media if robot is not None else backend
        self.backend = self.media.audio if robot is not None else backend
        if self.backend is None:
            raise RuntimeError("SDK local audio unavailable; check daemon media status")
        self.rate = self.media.get_output_audio_samplerate()
        if self.media.get_input_audio_samplerate() != 16000:
            raise RuntimeError("Reachy SDK microphone must supply 16000 Hz audio")
        self.closed = threading.Event()
        self._capture_failed = threading.Event()
        self.players = []
        self._offset_callback = offset_callback
        self.wobbler = HeadWobbler(self._offsets, sample_rate=self.rate)
        self._speech = False
        self._input = np.empty((0, 1), dtype=np.float32)
        self.media.start_recording()
        self.media.start_playing()
        # Prime the SDK live mixer appsrc so its shared capture pipeline can
        # complete preroll before the first HA response arrives.
        self.media.push_audio_sample(np.zeros(
            (self.rate // 50, self.media.get_output_channels()), dtype=np.float32
        ))
        self.task = asyncio.create_task(self._render())

    def _offsets(self, offsets):
        if self._offset_callback is not None:
            self._offset_callback(offsets)
        elif self._robot is not None:
            from reachy_mini.io.protocol import SetSpeechOffsetsCmd
            try:
                self._robot.client.send_command(SetSpeechOffsetsCmd(offsets=list(offsets)))
            except (ConnectionError, OSError, ConnectionClosed):
                # Same best-effort policy as SDK enable_wobbling: cosmetic
                # motion must not kill playback or prevent audio cleanup.
                pass

    @contextmanager
    def recorder(self, samplerate, channels, blocksize):
        if samplerate != 16000 or channels != 1:
            raise ValueError("SDK adapter exposes processed microphone channel 0 as 16 kHz mono")
        yield self

    def record(self, frames):
        deadline = time.monotonic() + 5
        while len(self._input) < frames:
            if self.closed.is_set():
                raise EOFError("SDK audio closed")
            sample = self.media.get_audio_sample()
            if sample is None or not np.size(sample):
                if time.monotonic() > deadline:
                    raise RuntimeError("No microphone audio received from Reachy SDK for 5 seconds")
                self.closed.wait(.005)
                continue
            # SDK/XMOS channel 0 is the processed microphone; never mix channel 1
            # into it or advertise an unverified second-channel AEC reference to HA.
            sample = np.nan_to_num(np.asarray(sample, dtype=np.float32), nan=0.0, posinf=1.0, neginf=-1.0)
            sample = sample.reshape(-1, 1) if sample.ndim == 1 else sample[:, :1]
            self._input = np.concatenate((self._input, sample))
        result, self._input = self._input[:frames], self._input[frames:]
        return result

    def fail_capture(self):
        self._capture_failed.set()

    def clock(self):
        # SDK 1.12 exposes no public playback-drained API. Keep its timing
        # dependency here: AudioBase stamps _appsrc_pts in pipeline running time.
        source = self.backend._appsrc
        running = source.get_current_running_time()
        latency = self.backend._pipeline.get_latency()
        if latency >= 2**63:
            latency = 0
        return running, latency

    def flush(self):
        self.backend.clear_player()
        if self._speech:
            self.wobbler.reset()
            self._speech = False

    async def _render(self):
        frames = self.rate // 50
        try:
            while not self.closed.is_set():
                if self._capture_failed.is_set():
                    raise RuntimeError("SDK microphone capture failed; see preceding traceback")
                now, latency = self.clock()
                # At most one 20 ms chunk ahead of the SDK playback clock.
                if self.backend._appsrc_pts > now + 20_000_000:
                    await asyncio.sleep(.005)
                    continue
                mixed = np.zeros(frames, dtype=np.float32)
                speech = np.zeros(frames, dtype=np.float32)
                count = 0
                for player in tuple(self.players):
                    pcm = player.take(frames, now)
                    if len(pcm):
                        pcm = pcm * player.gain
                        mixed[:len(pcm)] += pcm
                        if player.wobble:
                            speech[:len(pcm)] += pcm
                        count = max(count, len(pcm))
                speaking = any(p.is_speech for p in self.players)
                if speaking != self._speech:
                    (self.wobbler.start if speaking else self.wobbler.stop)()
                    self._speech = speaking
                if count:
                    stereo = np.repeat(np.clip(mixed[:count], -1, 1)[:, None],
                                       self.media.get_output_channels(), axis=1)
                    self.media.push_audio_sample(stereo)
                    end = self.backend._appsrc_pts + latency
                    running, _ = self.clock()
                    start_ns = time.monotonic_ns() + end - running - count * 1_000_000_000 // self.rate
                    if speaking:
                        self.wobbler.feed(speech[:count], start_ns)
                    for player in self.players:
                        if player._contributed:
                            player._audible_until = end
                await asyncio.sleep(.005)
        except asyncio.CancelledError:
            raise
        except Exception:
            self.closed.set()
            raise

    async def close(self):
        self.closed.set()
        self.task.cancel()
        try:
            await self.task
        except asyncio.CancelledError:
            pass
        finally:
            for player in tuple(self.players):
                player.close()
            self.wobbler.stop()
            self.media.stop_recording()
            self.media.stop_playing()
            if self._robot is None:
                self.backend.cleanup()
            # SDK 1.12 cleanup() releases USB; its destructor owns the GLib loop.
            # Close the audio loop deterministically; never release daemon media.
            self.backend._loop.quit()
            self.backend._thread_bus_calls.join(timeout=3)
            if self._owns_robot:
                self._robot.__exit__(None, None, None)
