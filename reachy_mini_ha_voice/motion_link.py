"""Keep transient SDK transport failures out of the voice/audio lifecycle.

SDK 1.12 has no reconnect operation. Re-create only its WSClient after a
sustained outage; never recreate/release shared media or restart the LVA worker.
"""
import logging
import threading
import time

from websockets.exceptions import ConnectionClosed

_LOG = logging.getLogger(__name__)


class MotionLink:
    def __init__(self, robot, factory=None, clock=time.monotonic):
        self.robot, self.factory, self.clock = robot, factory, clock
        self._failed_at = None
        self._next_retry = 0.0
        self._stop = threading.Event()
        self._thread = None

    def send(self, **target):
        try:
            self.robot.set_target(**target)
        except (ConnectionError, OSError, ConnectionClosed) as error:
            now = self.clock()
            if self._failed_at is None:
                self._failed_at = now
                client = self.robot.client
                ws = getattr(client, '_ws', None)
                receiver = getattr(client, '_recv_thread', None)
                _LOG.warning("SDK motion unavailable: %s; receiver_alive=%s, close_code=%s, close_reason=%s. Voice stays running.",
                             error, receiver.is_alive() if receiver else None,
                             getattr(ws, 'close_code', None), getattr(ws, 'close_reason', None))
            if (now - self._failed_at >= 5 and now >= self._next_retry
                    and (self._thread is None or not self._thread.is_alive())):
                self._next_retry = now + 5
                self._thread = threading.Thread(target=self._reconnect, name='sdk-motion-reconnect', daemon=True)
                self._thread.start()
            return False
        if self._failed_at is not None:
            _LOG.info("SDK motion recovered after %.2fs; voice worker remained running", self.clock() - self._failed_at)
            self._failed_at = None
        return True

    def _reconnect(self):
        old = self.robot.client
        candidate = None
        try:
            factory = self.factory
            if factory is None:
                from reachy_mini.io.ws_client import WSClient
                factory = WSClient
            candidate = factory(host=old.host, port=old.port)
            candidate.wait_for_connection(timeout=3)
            if self._stop.is_set():
                return
            self.robot.client = candidate
            candidate = None
            old.disconnect()
            _LOG.info("SDK motion WebSocket reconnected; shared media unchanged")
        except (ConnectionError, OSError, TimeoutError, ConnectionClosed) as error:
            _LOG.warning("SDK motion reconnect failed: %s; will retry", error)
        finally:
            if candidate is not None:
                candidate.disconnect()

    def close(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1)
