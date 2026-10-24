# Validation

2026-10-23: local Python 3.12 on macOS.

- 28 automated tests passed: stage transitions and interruption, bounded motion/slew, quiet listening, malformed events, bundled model/audio assets, process termination escalation, real loopback WebSocket messages/shutdown, application normal/error lifecycle.
- Idle breathing regression checks official 5 mm / 0.1 Hz head movement and 15 degree / 0.5 Hz opposing antenna movement, plus freeze on wake and restart continuity.
- Ruff passed.
- Wheel and source distribution built successfully; bundled upstream source, models and sounds included.
- Tests use a robot mock and synthetic LVA events. They do not establish physical motion quality, microphone capture, wake-word detection accuracy or a real HA Assist conversation.
- Full Linux dependencies, upstream imports and official application installation checker are validated in GitHub Actions. See the latest workflow result for the tested commit.
- No robot or HA instance was contacted. User will install and perform hardware acceptance: HA discovery, Okay Nabu wake, listening → thinking → audible answer with motion, interruption, app restart/stop.

The macOS full SDK dependency download timed out; core tests use an isolated lightweight environment. This is not a successful full SDK installation test.

0.2.0 adds scripts/smoke_tts.py: real GStreamer virtual-speaker playback feeds the installed official HeadWobbler; asserts nonzero speech offsets, EOS reset, replacement callback isolation and interruption cancellation. This does not measure physical audio/motor latency.

0.3.0 adds virtual daemon HTTP sampling and playback suppression, stale/invalid direction rejection, measured-yaw coordinate conversion, turn timing/deadband/clamping, hold and return timing, repeated-wake cancellation during hold/return, continued listening, duplicate idle events, error/watchdog recovery, and breathing restoration. Linux smoke_direction.py invokes the actual vendored LVA wake handler to verify direction precedes chime in both listening modes. Physical DOA calibration and acoustic interference remain user hardware acceptance items.

0.3.1 removes the arbitrary ±40° base cap. Regression checks cover full 90° turns, measured world headings up to the ±160° body boundary, and actual application-loop commands containing coordinated head/body targets through wake, speaking, 5-second hold and 1.5-second recenter. Motor dynamics and physical DOA accuracy are not hardware-tested.

0.3.2: Robot report exposed missing libmpv hidden by CI provisioning. CI now removes libmpv/mpv and asserts find_library("mpv") is None before real LVA startup. GStreamer music smoke covers playlist completion, pause/resume, volume/duck, stop and absence of robot connection/speech offsets. TTS playback and official DSP regressions still run. This does not certify the full robot OS image or its GStreamer plugins.

0.4.0: previous PulseAudio CI masked the stock Wireless ALSA environment. New Linux smoke uses SDK GStreamerAudio with a clocked GStreamer test source and synchronized fake speaker, without starting PulseAudio. Real LVA boots with its motor/daemon connection stubbed. ALSA null capture failed to produce frames and stalled SDK shutdown in CI; it is not treated as a passing hardware test. Playback/motion tests use real decoding, SDK output clock and HeadWobbler; physical microphone, speaker latency and HA acceptance remain unverified. Read-only robot inspection confirmed SDK1.12.0, Debian13.2 aarch64, ALSA configuration and the soundcard PulseAudio assertion.

0.6.1: pinned upstream moves.py commit c178d4aa375f2a3968b1340932870b4c54af83c9 is the offline oracle. Tests execute its original BreathingMove and six MovementManager methods without hardware threads. Six60Hz timelines (900frames each) compare head matrices and antenna commands at1e-12 absolute tolerance: ordinary idle, listening before breathing, during breathing, at queue/start boundaries and rapid listen/unlisten. Additional tests compare the exact class AST, feedback pose/transport failure, zero-centred waveform, no reset on thinking/speech/finish, acoustic frame transforms and application-level head/body turn/hold/return. Old tests that asserted whole-frame freezing/restart were replaced because they encoded the incorrect behaviour. Local runner uses installed SDK maths with its hardware-importing package entrypoint bypassed; full SDK imports remain Linux CI's responsibility. No robot/HA writes or real motor/audio playback were performed for this release.
