"""Run the production worker with real SDK media and virtual physical endpoints."""
import signal
import sys
import threading
from types import SimpleNamespace
from unittest.mock import Mock

from virtual_audio import install

install()
from reachy_mini.media.media_manager import MediaBackend, MediaManager
from reachy_mini_ha_voice.runtime import VoiceWorker

# Only physical camera/capture/speaker endpoints are substituted.
MediaManager._init_camera = lambda *args: None
media = MediaManager(backend=MediaBackend.LOCAL)
robot = SimpleNamespace(media=media, client=Mock(),
                        get_current_head_pose=lambda: [[1, 0, 0, 0], [0, 1, 0, 0],
                                                       [0, 0, 1, 0], [0, 0, 0, 1]])
stop = threading.Event()
signal.signal(signal.SIGTERM, lambda *_: stop.set())
worker = VoiceWorker(sys.argv[1:], robot)
try:
    while not stop.wait(.05):
        if worker.poll() is not None:
            raise RuntimeError(f"Voice worker exited early: {worker.returncode}")
finally:
    worker.stop()
    media.close()
assert worker.returncode == 0
assert not worker._thread.is_alive()
