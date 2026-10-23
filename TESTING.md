# Validation

2026-10-23: local Python 3.12 on macOS.

- 10 automated tests passed: stage transitions and interruption, bounded motion/slew, quiet listening, malformed events, bundled model/audio assets, process termination escalation, real loopback WebSocket messages/shutdown, application normal/error lifecycle.
- Idle breathing regression checks official 5 mm / 0.1 Hz head movement and 15 degree / 0.5 Hz opposing antenna movement, plus freeze on wake and restart continuity.
- Ruff passed.
- Wheel and source distribution built successfully; bundled upstream source, models and sounds included.
- Tests use a robot mock and synthetic LVA events. They do not establish physical motion quality, microphone capture, wake-word detection accuracy or a real HA Assist conversation.
- Full Linux dependencies, upstream imports and official application installation checker are validated in GitHub Actions. See the latest workflow result for the tested commit.
- No robot or HA instance was contacted. User will install and perform hardware acceptance: HA discovery, Okay Nabu wake, listening → thinking → audible answer with motion, interruption, app restart/stop.

The macOS full SDK dependency download timed out; core tests use an isolated lightweight environment. This is not a successful full SDK installation test.

0.2.0 adds scripts/smoke_tts.py: real GStreamer virtual-speaker playback feeds the installed official HeadWobbler; asserts nonzero speech offsets, EOS reset, replacement callback isolation and interruption cancellation. This does not measure physical audio/motor latency.
