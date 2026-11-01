# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/): new behaviour raises the minor
version, fixes raise the patch version.

## [0.13.0] - 2026-11-01

### Added
- Face Tracking switch on the Home Assistant device page. It turns on the
  robot daemon's face tracking, is off at every start and is not saved. As
  before, tracking pauses during a wake turn and conversation (until the
  return finishes) and while a manual direction is set.

### Removed
- The `head_tracking` option in `config.json`; the switch replaces it and the
  option is ignored if present.

Wake, conversation, motion and audio are unchanged while the switch is off.

## [0.12.3] - 2026-11-01

No change to the app itself.

### Changed
- README credits list the projects whose code the app uses, and the media
  player note explains the behaviour directly.

## [0.12.2] - 2026-11-01

No change to the app itself.

### Changed
- README rewritten in both languages: shorter, organised as features,
  install, Home Assistant controls, settings, known limitations and credits,
  with test, release and license badges.

## [0.12.1] - 2026-11-01

No change to wake, conversation, motion or the Home Assistant protocol.

### Fixed
- Allow Reachy Mini SDK 1.13 and newer (`reachy-mini>=1.12.0`). The previous
  `<1.13` cap would downgrade the SDK in the robot's shared app environment
  after a system update. CI now tests both SDK 1.12.0 and the latest release.
- Allow websockets 13–15 instead of exactly 12, matching the SDK's range.
  The exact pin downgraded websockets in the shared app environment, which
  breaks apps that need a newer version (such as the official conversation
  app's realtime voice).
- Removing a file from the repository now also removes it from the Hugging
  Face Space.

### Changed
- The application's own WebSocket code uses the `websockets.asyncio` API
  (available since websockets 13). The vendored LVA is unchanged.
- CI runs on Ubuntu 24.04 with Node 24 actions (`checkout@v6`,
  `setup-python@v6`, `setup-uv@v7`).
- README is now in English with a Chinese version (`README.zh-CN.md`). The
  Space landing page is rewritten with an English/Chinese switch and no
  longer lists PulseAudio and libmpv requirements removed in 0.4.0.
- `TESTING.md` describes the current validation; the changelog is in English.

### Removed
- `plan.md`, outdated early development notes.

## [0.12.0] - 2026-10-29

### Added
- Manual direction on the Home Assistant device page: Body Turn (head and body
  together, ±160°), Head Turn (head only, ±65°), Head Tilt (±40°) and a Center
  button. The ranges are the official limits.

### Changed
- The single motion loop composes the manual direction under breathing,
  antennas, listening freeze and speech wobble. A wake turn starts from the
  manual body direction, temporarily straightens the head and returns to the
  manual direction afterwards. Head tracking does not move the head while a
  manual direction is set. The manual direction is not saved across restarts.
- Vendored LVA: `ServerState.robot_entities` holds app controls that the
  satellite appends after its own entities (existing entity keys unchanged),
  ESPHome button commands are routed to them, and `main()` accepts `controls`.

With all sliders at 0, behaviour is the same as 0.11.0.

## [0.11.0] - 2026-10-28

### Added
- Chinese wake word 「小派小派」 (`xiao_pai`), a microWakeWord v2 model trained
  by lichao. It can be selected on the Home Assistant device page next to the
  built-in wake words, or enabled together with one of them.

### Changed
- The model lives in the app's own `reachy_mini_ha_voice/wakewords/` and is
  added with `--wake-word-dir`, the way upstream documents custom wake words.
  `vendor/lva` stays identical to upstream; the default wake word is unchanged.

## [0.10.0] - 2026-10-27

### Changed
- Vendored Linux Voice Assistant synced to upstream `20f8a1f` (from `39a10e7`,
  37 commits): paused music stays paused after an announcement, unknown keys
  in `preferences.json` no longer prevent startup, continued conversations
  keep the pipeline of the wake word that started them, inactive wake models
  are unloaded, log timestamps include milliseconds.
- Lower idle CPU: the shared playback mixing loop waits while nothing plays
  instead of polling every 5 ms.

### Added
- Upstream's pipeline-ended sound (enabled by default): a short tone when a
  pipeline ends without a spoken reply.

All local adaptations are kept. Upstream's microphone reconnect (#491) targets
`soundcard` capture and exits the process; it is not used because the SDK owns
capture.

## [0.9.0] - 2026-10-26

### Fixed
- Wake turn angle correction. On the robot the microphone array under-reports
  side sources (45° reads about 20°, 90° about 54°). The raw relative angle is
  mapped piecewise linearly 0→0°, 20→45°, 54→90°, symmetric and capped at
  ±90°; the 3° deadband still applies to the raw reading.
- The wake direction uses speech samples only; without any, the turn is
  skipped instead of following non-speech readings.
- The DOA median is linear: 0 (left) and π (right) are opposite ends, not
  neighbours on a circle.

### Changed
- `Wake turn` logs both the raw and the corrected relative angle.

## [0.8.0] - 2026-10-26

### Changed
- The wake chime plays through the SDK's local file playback
  (`media.play_sound()`) on a dedicated thread instead of the PCM mixing loop.
  Completion is timed from the file's frame count and sample rate; cancelling,
  replacing or stopping never fires a stale listening callback.
- The 60 Hz motion loop runs on a dedicated `ha-motion` thread fed by the
  event queue. Startup and shutdown motions run outside it; shutdown stops the
  thread before cleaning up connections.

Turn, breathing, antenna and speech wobble behaviour is unchanged.

## [0.7.2] - 2026-10-25

### Fixed
- Startup wake-up matches the official conversation app: the sleep pose is
  detected with `SLEEP_HEAD_POSE` and `distance_between_poses`, and the motors
  are enabled before `wake_up()`. Starting the app while the robot slept used
  to play the sound without moving.

## [0.7.1] - 2026-10-25

### Fixed
- `wake_up()` runs only when the measured head pose is the sleep pose, so the
  wake animation and sound are not repeated when the robot is already awake.
  Without pose telemetry the app still wakes the robot once.

## [0.7.0] - 2026-10-24

### Changed
- Wake direction window widened from 0.4 s to 0.8 s to cover the whole wake
  word. With at least 3 speech samples only they are used; otherwise speech
  samples seed a ±30° cluster before taking the median.
- Wake turn deadband reduced from 6° to 3°.

## [0.6.5] - 2026-10-24

### Changed
- Wake direction uses the circular median of speech readings from the last
  0.4 s instead of the last single DOA sample, and logs its source.

## [0.6.4] - 2026-10-24

### Fixed
- Leaving listening blends from the last antenna command that was actually
  sent, so a failed send no longer causes an extra jump.

## [0.6.3] - 2026-10-24

### Changed
- When an antenna is within 8° of 0° as listening freezes it, it moves to
  ±10° on the same side over 0.2 s before locking, because holding at 0°
  makes the gearbox jitter. This is the only deviation from the official
  motion code.

## [0.6.2] - 2026-10-24

### Fixed
- Breathing start-up handles feedback errors like the official app.
- The listening freeze uses the last successfully sent antenna command.
- Non-network `set_target` errors are isolated and logged at most once per
  second; diagnostic read failures no longer stop the voice loop.

## [0.6.1] - 2026-10-24

### Fixed
- `BreathingMove` taken verbatim from the official conversation app (commit
  `c178d4a`). Listening freezes only the antennas; breathing already started
  continues, and leaving listening blends back over 0.4 s.

## [0.6.0] - 2026-10-24

### Changed
- Restored the official two-phase breathing and removed the custom bias,
  interpolation and thinking sway.

### Fixed
- A lost SDK motion connection no longer stops voice; after 5 s only the SDK
  WebSocket reconnects.
- Shutdown no longer blocks while Home Assistant is still connected.

## [0.5.2] - 2026-10-24

### Fixed
- The player no longer treats `appsink.eos=true` before start as the end of
  playback; playback completes only after a real GStreamer EOS and drained
  audio.

### Added
- Announcement receive, first-frame and end logs (no signed URLs or text).

## [0.5.1] - 2026-10-24

### Changed
- 60 Hz control loop with compute-time compensation; wake turns use the full
  measured angle with coordinated head and body.

## [0.5.0] - 2026-10-24

### Changed
- The app uses the official `ReachyMiniApp` local SDK instance and LVA shares
  `reachy_mini.media`; dashboard video keeps working.

## [0.4.0] - 2026-10-24

### Changed
- Recording and playback use the SDK GStreamer audio backend; `soundcard`,
  PulseAudio and libmpv are no longer needed. DOA comes from the SDK. Old
  `audio_input_device` and `audio_output_device` settings must be removed.

## [0.3.2] - 2026-10-23

### Removed
- libmpv startup dependency; music plays through GStreamer.

## [0.3.1] - 2026-10-23

### Changed
- Removed the ±40° turn cap; head and body turn together within the body's
  ±160° range.

## [0.3.0] - 2026-10-23

### Added
- Wake turn toward the speaker: 0.65–1.25 s turn, 5 s hold, 1.5 s return; a
  new wake cancels the hold or return.

## [0.2.1] - 2026-10-23

### Changed
- Head tracking is off by default; set `head_tracking` to `true` in
  `config.json` to enable it.

## [0.2.0] - 2026-10-23

### Added
- Decoded TTS audio drives the official `HeadWobbler`; music does not.

## [0.1.1] - 2026-10-23

### Changed
- Idle breathing uses the official parameters.

## [0.1.0] - 2026-10-23

### Added
- First installable version: official `ReachyMiniApp` entry point, bundled
  Linux Voice Assistant runtime, ESPHome discovery and local wake word.

[0.13.0]: https://github.com/cuichaobaobao/reachy_mini_ha_voice/compare/v0.12.3...v0.13.0
[0.12.3]: https://github.com/cuichaobaobao/reachy_mini_ha_voice/compare/v0.12.2...v0.12.3
[0.12.2]: https://github.com/cuichaobaobao/reachy_mini_ha_voice/compare/v0.12.1...v0.12.2
[0.12.1]: https://github.com/cuichaobaobao/reachy_mini_ha_voice/compare/v0.12.0...v0.12.1
[0.12.0]: https://github.com/cuichaobaobao/reachy_mini_ha_voice/compare/v0.11.0...v0.12.0
[0.11.0]: https://github.com/cuichaobaobao/reachy_mini_ha_voice/compare/v0.10.0...v0.11.0
[0.10.0]: https://github.com/cuichaobaobao/reachy_mini_ha_voice/compare/v0.9.0...v0.10.0
[0.9.0]: https://github.com/cuichaobaobao/reachy_mini_ha_voice/compare/v0.8.0...v0.9.0
[0.8.0]: https://github.com/cuichaobaobao/reachy_mini_ha_voice/compare/v0.7.2...v0.8.0
[0.7.2]: https://github.com/cuichaobaobao/reachy_mini_ha_voice/compare/v0.7.1...v0.7.2
[0.7.1]: https://github.com/cuichaobaobao/reachy_mini_ha_voice/compare/v0.7.0...v0.7.1
[0.7.0]: https://github.com/cuichaobaobao/reachy_mini_ha_voice/compare/v0.6.5...v0.7.0
[0.6.5]: https://github.com/cuichaobaobao/reachy_mini_ha_voice/compare/v0.6.4...v0.6.5
[0.6.4]: https://github.com/cuichaobaobao/reachy_mini_ha_voice/compare/v0.6.3...v0.6.4
[0.6.3]: https://github.com/cuichaobaobao/reachy_mini_ha_voice/compare/v0.6.2...v0.6.3
[0.6.2]: https://github.com/cuichaobaobao/reachy_mini_ha_voice/compare/v0.6.1...v0.6.2
[0.6.1]: https://github.com/cuichaobaobao/reachy_mini_ha_voice/compare/v0.6.0...v0.6.1
[0.6.0]: https://github.com/cuichaobaobao/reachy_mini_ha_voice/compare/v0.5.2...v0.6.0
[0.5.2]: https://github.com/cuichaobaobao/reachy_mini_ha_voice/compare/v0.5.1...v0.5.2
[0.5.1]: https://github.com/cuichaobaobao/reachy_mini_ha_voice/compare/v0.5.0...v0.5.1
[0.5.0]: https://github.com/cuichaobaobao/reachy_mini_ha_voice/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/cuichaobaobao/reachy_mini_ha_voice/compare/v0.3.2...v0.4.0
[0.3.2]: https://github.com/cuichaobaobao/reachy_mini_ha_voice/compare/v0.3.1...v0.3.2
[0.3.1]: https://github.com/cuichaobaobao/reachy_mini_ha_voice/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/cuichaobaobao/reachy_mini_ha_voice/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/cuichaobaobao/reachy_mini_ha_voice/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/cuichaobaobao/reachy_mini_ha_voice/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/cuichaobaobao/reachy_mini_ha_voice/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/cuichaobaobao/reachy_mini_ha_voice/releases/tag/v0.1.0
