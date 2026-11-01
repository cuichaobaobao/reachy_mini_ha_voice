# Validation

How each release is checked. Release-by-release details are in
[CHANGELOG.md](CHANGELOG.md).

## Automated (GitHub Actions, every push)

Runs on Ubuntu 24.04 with Python 3.12, once with the oldest supported SDK
(`reachy-mini==1.12.0`) and once with the latest release. A release is
published only when both pass.

- **Unit and regression tests** (`pytest`): conversation state transitions and
  interruption, wake direction sampling and correction, wake turn timing,
  hold and return, manual direction limits and hand-off, listening antenna
  freeze, failed motor sends, the app lifecycle and shutdown order, wake word
  discovery (including `xiao_pai`) and real loopback WebSocket events.
- **Official motion comparison**: `BreathingMove` and the motion manager
  methods from the official conversation app (pinned in `tests/fixtures`) are
  run frame by frame against this app's motion over several 60 Hz timelines.
- **Lint, build and app check**: `ruff`, `python -m build` and
  `reachy-mini-app-assistant check`.
- **Smoke tests on real software** (`scripts/`): the real SDK GStreamer audio
  pipeline with virtual endpoints and no PulseAudio or libmpv; a real LVA
  runtime with an ESPHome client (handshake, entity list, manual direction
  controls, announcements fetched over HTTP, a 3-minute connected run, clean
  shutdown); TTS playback driving the official `HeadWobbler`; the wake chime
  path; the vendored wake handler capturing direction before the chime; and
  SDK motion reconnects.

These use a mocked robot and synthetic events. They do not measure physical
motion, microphone capture, wake word accuracy or a real Home Assistant
conversation.

## Local

The full `pytest` suite also runs on a development machine; the smoke tests
and the app check need the Linux CI environment.

```sh
python -m pip install -e '.[test]'
python -m pytest -q
ruff check reachy_mini_ha_voice tests
```

## On the robot (manual acceptance)

After installing a release from the app store:

- Home Assistant discovers the device and the Assist pipeline answers.
- The wake word works (Okay Nabu, and 小派小派 if enabled) without frequent
  false wakes.
- The robot turns toward the speaker, holds, and returns; breathing, the
  listening antenna freeze and speech head wobble look right.
- Manual direction sliders and Center move the robot as expected.
- Stopping and restarting the app is clean.

Logs: `sudo journalctl -u reachy-mini-daemon` on the robot (look for
`Wake turn` lines for direction).
