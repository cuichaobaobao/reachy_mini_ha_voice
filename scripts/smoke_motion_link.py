"""Real SDK 1.12 WebSocket heartbeat loss and socket reconnection; no robot."""
import threading
import time
from types import SimpleNamespace

import numpy as np
from websockets.sync.server import serve
from websockets.exceptions import ConnectionClosed
from reachy_mini.io.ws_client import WSClient
from reachy_mini.io.protocol import HeadPoseMsg, JointPositionsMsg, SetSpeechOffsetsCmd
from reachy_mini_ha_voice.motion_link import MotionLink

silent = threading.Event()
sockets = []
commands = []
head = HeadPoseMsg(head_pose=np.eye(4).tolist()).model_dump_json()
joints = JointPositionsMsg(head_joint_positions=[0.] * 7, antennas_joint_positions=[0., 0.]).model_dump_json()


def handler(ws):
    sockets.append(ws)
    try:
        while True:
            if not silent.is_set():
                ws.send(head)
                ws.send(joints)
            try:
                commands.append(ws.recv(timeout=.02))
            except TimeoutError:
                pass
    except ConnectionClosed:
        pass


with serve(handler, '127.0.0.1', 0) as server:
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    client = WSClient(host='127.0.0.1', port=server.socket.getsockname()[1])
    client.wait_for_connection()
    robot = SimpleNamespace(client=client)
    robot.set_target = lambda **kw: robot.client.send_command(SetSpeechOffsetsCmd(offsets=[0.] * 6))
    link = MotionLink(robot)

    def drive(seconds):
        end = time.monotonic() + seconds
        outcomes = []
        while time.monotonic() < end:
            outcomes.append(link.send())
            time.sleep(1 / 60)
        return outcomes

    try:
        assert all(drive(.2))
        silent.set()
        assert not all(drive(3)), 'Expected real SDK heartbeat timeout'
        silent.clear()
        assert any(drive(3)), 'SDK did not recover from transient telemetry pause'
        assert len(sockets) == 1, 'Transient heartbeat failure should not replace the connection'
        sockets[0].close(code=1011, reason='injected transport failure')
        before = len(commands)
        drive(9)
        assert len(sockets) >= 2 and robot.client is not client
        assert len(commands) > before and link.send()
        print('Real SDK heartbeat loss recovered without exit; closed socket reconnected; commands resumed')
    finally:
        link.close()
        robot.client.disconnect()
        server.shutdown()
        thread.join(2)
