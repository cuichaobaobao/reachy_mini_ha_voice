"""Compare every frame to pinned upstream executable code, not copied expectations."""
import ast
import logging
from collections import deque
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from reachy_mini.utils import create_head_pose
from reachy_mini.utils.interpolation import linear_pose_interpolation

from reachy_mini_ha_voice.motion import (
    CONTROL_LOOP_HZ,
    NEUTRAL_ANTENNAS,
    Motion,
    relative_to_heading,
    tick_delay,
    with_heading,
)


def official_manager(read_pose):
    """Run original queue/breathing/listening methods without audio/network threads."""
    tree = ast.parse((Path(__file__).parent / 'fixtures/conversation_moves.py').read_text())
    methods = {'_handle_command', '_manage_move_queue', '_manage_breathing',
               '_get_primary_pose', '_update_primary_motion', '_calculate_blended_antennas'}
    nodes = [ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0)]
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == 'BreathingMove' or isinstance(node, ast.FunctionDef) and node.name == 'clone_full_body_pose':
            nodes.append(node)
        elif isinstance(node, ast.ClassDef) and node.name == 'MovementManager':
            node.bases = []
            node.body = [m for m in node.body if isinstance(m, ast.FunctionDef) and m.name in methods]
            nodes.append(node)
    namespace = {'np': np, 'create_head_pose': create_head_pose,
                 'linear_pose_interpolation': linear_pose_interpolation,
                 'Move': object, 'logger': logging.getLogger('official-oracle')}
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])), 'upstream-moves.py', 'exec'), namespace)  # noqa: S102 - pinned offline upstream oracle
    manager = namespace['MovementManager']()
    manager.time = 0.0
    manager._now = lambda: manager.time
    manager.state = SimpleNamespace(current_move=None, move_start_time=None, last_primary_pose=None,
                                    last_activity_time=0.0)
    manager.state.update_activity = lambda: setattr(manager.state, 'last_activity_time', manager.time)
    manager.move_queue = deque()
    manager._is_listening = manager._breathing_active = False
    manager._track_anchor = None
    manager.idle_inactivity_delay = .3
    manager._antenna_blend_duration = .4
    manager._antenna_unfreeze_blend = 1.0
    manager._last_listening_blend_time = 0.0
    pose = (create_head_pose(), NEUTRAL_ANTENNAS, 0.0)
    manager.state.last_primary_pose = pose
    manager._last_commanded_pose = pose
    manager._listening_antennas = NEUTRAL_ANTENNAS
    manager.current_robot = SimpleNamespace(
        get_current_head_pose=lambda: read_pose()[0],
        get_current_joint_positions=lambda: (None, read_pose()[1]),
    )
    return manager


@pytest.mark.parametrize('listening_windows', [[], [(2, 5)], [(0, 2)], [(0.3, 1)],
                                                [(19 / 60, 2)], [(2, 2.2), (2.3, 3), (5, 6)]])
@pytest.mark.parametrize('failed_sends', [False, True])
def test_frames_match_upstream_lifecycle(listening_windows, failed_sends):
    # Include rotation and x/y translation: old implementation discarded these.
    feedback = (create_head_pose(x=.002, y=-.003, z=.004, roll=7, pitch=-4, yaw=12), (-.3, .22))
    motion = Motion(lambda: feedback)
    official = official_manager(lambda: feedback)
    listening = False
    samples = []
    for frame in range(900):
        now = frame / 60
        official.time = now
        wanted = any(start <= now < end for start, end in listening_windows)
        if wanted != listening:
            official._handle_command('set_listening', wanted, now)
            motion.event({'event': 'listening' if wanted else 'thinking'}, now)
            listening = wanted
        official._update_primary_motion(now)
        head, antennas, body = official._get_primary_pose(now)
        antennas = official._calculate_blended_antennas(antennas)
        actual_head, actual_antennas = motion.sample(now)
        np.testing.assert_allclose(actual_head, head, atol=1e-12, rtol=0)
        np.testing.assert_allclose(actual_antennas, antennas, atol=1e-12, rtol=0)
        if not (failed_sends and (90 <= frame < 180 or 310 <= frame < 350)):
            official._last_commanded_pose = (head, antennas, body)
            motion.command_sent(actual_antennas)
        samples.append((actual_head[2, 3], actual_antennas))
    if listening_windows == [(2, 5)]:
        assert samples[150][0] != samples[210][0]  # Existing z breath continues.
        assert samples[150][1] == samples[210][1]  # Only antennas freeze.
    if listening_windows == [(0, 2)]:
        assert all(z == 0 and a == NEUTRAL_ANTENNAS for z, a in samples[:120])


def test_official_zero_centred_steady_waveform():
    motion = Motion()
    motion.sample(0)
    motion.sample(.3)  # Queue, exactly like upstream.
    motion.sample(.3 + 1 / 60)  # Start on following control frame.
    start = .3 + 1 / 60 + 1
    for phase in (0, .5, 1, 1.5, 2.5, 7.5):
        head, antennas = motion.sample(start + phase)
        np.testing.assert_allclose(antennas, np.deg2rad([15, -15]) * np.sin(np.pi * phase), atol=1e-12)
        assert head[2, 3] == pytest.approx(.005 * np.sin(.2 * np.pi * phase))


@pytest.mark.parametrize('error', [ConnectionError, RuntimeError, KeyError])
def test_feedback_failure_holds_then_retries_without_resetting_running_breath(error):
    feedback = (create_head_pose(z=.003), (-.23, .21))
    def read():
        if not ready[0]:
            raise error('no telemetry')
        return feedback
    ready = [False]
    motion = Motion(read)
    motion.sample(0)
    head, antennas = motion.sample(.5)
    np.testing.assert_array_equal(head, np.eye(4))
    assert antennas == NEUTRAL_ANTENNAS
    ready[0] = True
    motion.sample(.6)
    head, antennas = motion.sample(.7)
    np.testing.assert_allclose(head, feedback[0])
    np.testing.assert_allclose(antennas, feedback[1])
    ready[0] = False
    assert motion.sample(3.2)[0][2, 3] != 0  # No reread needed during active move.


def test_heading_composition_preserves_feedback_and_breathing():
    relative = create_head_pose(x=.003, y=.002, z=.004, roll=3, pitch=-6, yaw=8)
    for heading in (-160, -90, 0, 90, 160):
        world = with_heading(relative, heading)
        np.testing.assert_allclose(relative_to_heading(world, heading), relative, atol=1e-12)
        assert world[2, 3] == pytest.approx(relative[2, 3])


def test_official_sixty_hz_accounts_for_compute():
    assert CONTROL_LOOP_HZ == 60
    assert tick_delay(1, 1.005) == pytest.approx(1 / 60 - .005)
    assert tick_delay(1, 1.1) == 0


def test_thinking_speech_finish_do_not_restart_or_replace_breathing():
    baseline, actual = Motion(), Motion()
    for frame in range(600):
        now = frame / 60
        if frame in {120, 180, 240, 300}:
            actual.event({'event': {120: 'thinking', 180: 'tts_speaking',
                                    240: 'tts_finished', 300: 'idle'}[frame]}, now)
        expected_head, expected_antennas = baseline.sample(now)
        head, antennas = actual.sample(now)
        np.testing.assert_allclose(head, expected_head, atol=1e-12)
        np.testing.assert_allclose(antennas, expected_antennas, atol=1e-12)


def test_breathing_class_body_is_unchanged_upstream_code():
    import inspect

    from reachy_mini_ha_voice.official_breathing import BreathingMove
    original = ast.parse((Path(__file__).parent / 'fixtures/conversation_moves.py').read_text())
    upstream = next(n for n in original.body if isinstance(n, ast.ClassDef) and n.name == 'BreathingMove')
    local = ast.parse(inspect.getsource(BreathingMove)).body[0]
    # No parent Move needed in the adapter; every statement of the body is identical.
    assert [ast.dump(n) for n in local.body] == [ast.dump(n) for n in upstream.body]


@pytest.mark.parametrize('error', [KeyboardInterrupt, SystemExit])
def test_feedback_does_not_swallow_process_exit(error):
    def read():
        raise error()
    motion = Motion(read)
    motion.sample(0)
    with pytest.raises(error):
        motion.sample(.5)


def test_listening_freezes_last_successful_command_not_last_calculation():
    motion = Motion()
    motion.sample(0)
    motion.sample(.3)
    motion.sample(.4)
    _, sent = motion.sample(1.6)
    motion.command_sent(sent)
    _, unsent = motion.sample(1.9)
    assert unsent != sent
    motion.event({'event': 'listening'}, 2)
    assert motion.sample(2)[1] == sent
