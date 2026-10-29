"""Worker shutdown must finish cleanup before SDK media is destroyed."""
import asyncio
import threading

from reachy_mini_ha_voice.runtime import VoiceWorker


def test_shared_robot_and_clean_cancellation():
    entered = threading.Event()
    cleaned = threading.Event()
    robot = object()

    async def runner(argv, robot, install_signals, controls):
        assert argv == ['--name', 'test']
        assert robot is expected
        assert not install_signals
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            await asyncio.sleep(.01)
            cleaned.set()

    expected = robot
    worker = VoiceWorker(['--name', 'test'], robot, runner)
    assert entered.wait(2)
    worker.stop()
    assert cleaned.is_set()
    assert worker.poll() == 0
    assert not worker._thread.is_alive()


def test_worker_startup_failure_propagates():
    async def runner(**kwargs):
        raise RuntimeError('capture unavailable')

    worker = VoiceWorker([], object(), runner)
    worker._thread.join(2)
    assert worker.poll() == 1
    worker.stop()


def test_immediate_stop_race():
    async def runner(**kwargs):
        await asyncio.Event().wait()

    worker = VoiceWorker([], object(), runner)
    worker.stop()
    assert worker.poll() == 0
