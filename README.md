---
title: Reachy Mini HA Voice
emoji: 🏠
colorFrom: blue
colorTo: green
sdk: static
app_file: index.html
pinned: false
short_description: Home Assistant Assist voice with expressive robot gestures
tags:
  - reachy_mini
  - reachy_mini_python_app
license: apache-2.0
---

# Reachy Mini HA Voice

**English** | [简体中文](README.zh-CN.md)

Turns Reachy Mini Wireless into a Home Assistant Assist voice satellite: local
wake word, ESPHome auto-discovery, spoken conversations, and smooth head and
antenna motion while listening, thinking and speaking.

## Install and connect

The app uses the official `ReachyMiniApp` entry point and runs on the Wireless
robot's Linux system, not on the Hugging Face web server. Python 3.11 or newer
is required.

1. It uses the robot's existing Reachy Mini SDK (1.12 or newer) audio setup.
   Recording and playback go through the SDK's local GStreamer/ALSA backend;
   PulseAudio and libmpv are not needed, and the app does not install system
   packages or change audio settings.
2. Install and start the Hugging Face Space `lichao622/reachy_mini_ha_voice`
   from the app store in Reachy Mini Control. This is a community app, not
   reviewed by Pollen Robotics.
3. Keep the robot and Home Assistant on the same LAN. In Home Assistant, accept
   the discovered ESPHome device under *Settings → Devices & services* and pick
   an Assist pipeline with STT, a conversation agent and TTS. No Home Assistant
   address or token is entered in the app.
4. Say the wake word (**Okay Nabu** by default) to start talking. On the Home
   Assistant device page you can switch to the Chinese wake word
   **小派小派** (*xiao pai xiao pai*) or enable both.

If discovery does not work, add the ESPHome device manually with the
**robot's IP and port 6053**. Do not forward this port to the internet; the
internal voice event interface only listens on `127.0.0.1:6055`.

You can also install through the daemon API (replace `ROBOT_IP`):

```sh
curl -X POST http://ROBOT_IP:8000/api/apps/install \
  -H 'Content-Type: application/json' \
  -d '{"name":"reachy_mini_ha_voice","source_kind":"hf_space","url":"https://huggingface.co/spaces/lichao622/reachy_mini_ha_voice"}'
```

Stop other apps that use the robot's audio or motion first. If startup fails,
check the full app log; the app verifies that the SDK delivers microphone
audio before announcing itself to Home Assistant.

## Wake and motion

- **Startup**: like the official conversation app, the robot runs the official
  wake-up motion once, only if it is actually in the sleep pose (motors are
  enabled first). An already awake robot does not nod or play the sound again.
- **Idle**: after 0.3 s the official `BreathingMove` starts, easing to neutral
  over 1 s, then the head moves 5 mm at 0.1 Hz and the antennas ±15° in
  opposition at 0.5 Hz, sent at 60 Hz.
- **Wake turn**: before the chime, the app takes the median direction of the
  speech samples heard during the wake word (no speech samples, no turn) and
  combines it with the measured head pose. Deviations under 3° are ignored;
  side angles are corrected with a measured curve (reading 20° → 45°,
  54° → 90°, capped at ±90°). Head and body turn together along one smooth
  path within the body's ±160° range, taking 0.65–1.25 s.
- **Listening**: only the antennas freeze (at the last command sent; near 0°
  they move to ±10° on the same side over 0.2 s). Breathing already running
  continues; leaving listening blends back over 0.4 s.
- **Thinking / speaking**: breathing continues; while speaking, the actual TTS
  audio drives the official `HeadWobbler`, applied to the head only.
- **End**: when playback finishes without a follow-up, the robot holds its
  direction for 5 s, then head and body return together over 1.5 s. A new wake
  during that time cancels the return and turns to the new speaker. Without
  updates for 120 s while listening or thinking, the hold is released.

The direction comes from the DOA of the shared SDK media instance and the head
pose from the SDK telemetry cache, sampled at about 20 Hz; no extra recording
device is opened. Visual head tracking is off by default; when enabled, it
pauses during the turn hold and return.

## Manual direction

While the app runs, the Home Assistant device page has three sliders and a
button. The app's own motion loop applies them; while an app runs, it is the
robot's only motion controller, so pose commands sent directly from outside
are overwritten.

| Control | Range | Effect |
|---|---|---|
| Body Turn | ±160° | Head and body turn together (negative is left) |
| Head Turn | ±65° | Head only, body stays (negative is left) |
| Head Tilt | ±40° | Look up or down (positive is up) |
| Center | — | Reset all three sliders to the standby pose |

- The ranges are the official limits: body ±160°, head within ±65° of the
  body, head pitch ±40°. Moves ease in over about 0.6–1.5 s.
- Breathing, antennas, the listening freeze and speech wobble still apply on
  top of the manual direction. At the limits, the SDK clips what goes beyond.
- On wake, the body turns to the speaker from the manual direction and the
  head straightens over 0.6 s; afterwards it returns to the manual direction
  rather than straight ahead. With everything at 0, behaviour is unchanged.
- While a manual direction is set, visual tracking does not move the head. The
  manual direction is not saved; after a restart the robot faces forward.
- When the app is not running, these controls show as unavailable.

## Configuration

Data is stored in `~/.local/share/reachy_mini_ha_voice/` of the robot user:
`config.json`, LVA preferences and downloaded custom models. Set
`REACHY_HA_DATA_DIR` to use another directory. Restart the app after changing
the configuration.

Optional `config.json` (no Home Assistant token needed):

```json
{
  "name": "Reachy Mini HA Voice",
  "head_tracking": false,
  "wake_model": "okay_nabu",
  "network_interface": "wlan0"
}
```

`head_tracking` defaults to `false` and is enabled only when set to `true`.
Only include the keys you want to override; the device and network interface
names must match your robot. Wake words can also be chosen on the Home
Assistant device page.

Since 0.4.0 audio devices are managed by the SDK; remove `audio_input_device`
and `audio_output_device` from older configurations.

## Known limitations

- **DOA covers half a plane**: the linear microphone array reports 0–π
  (0 = left, π/2 = front or back, π = right) and **cannot tell front from
  back**. Sources behind the robot fold to the front, so the turn may go to
  the mirrored direction.
- **Side angles are compressed**: the array under-reports side sources
  (45° reads about 20°, 90° about 54°). Since 0.9.0 a measured curve corrects
  this, but it comes from one robot placed against a wall; other placements or
  reflections may still be off.
- **Noisy readings**: often only a few `speech=True` samples arrive during the
  wake word and single readings jump. The speech-sample median dampens this
  and no speech samples means no turn, but it is not always accurate.
- **First Home Assistant setup**: the wizard may report "unable to connect to
  Home Assistant" during its connection test because of a concurrent
  announcement, usually unrelated to audio. Retry once the test sound ends, or
  add the ESPHome device manually.
- **Chinese wake word**: upstream models are English only. The bundled
  「小派小派」 (`xiao_pai`) microWakeWord model is self-trained; its detection
  and false-wake rates depend on that training and should be checked in use.
  Sensitivity can be adjusted in Home Assistant.
- **Media player state**: like upstream LVA, conversation replies and
  announcements play directly and do not set the media player to *playing*;
  the Assist satellite entity shows the conversation state.
- **Antenna jitter at 0°**: 0° is an unstable mechanical balance point; the
  software avoids holding there but cannot remove gear backlash on every unit.
- Real audio quality, wake rate, turn accuracy and the full Home Assistant
  path still need acceptance on the robot; see `TESTING.md`.

## How it works

- The OHF [Linux Voice Assistant](https://github.com/OHF-Voice/linux-voice-assistant)
  (LVA) runtime, ESPHome API, mDNS and local wake models are kept. LVA and
  motion run on separate threads of one app process: LVA's public peripheral
  WebSocket events go through a reader thread into a queue, and a dedicated
  `ha-motion` thread sends the base pose and antenna targets at 60 Hz.
- The wake chime uses the SDK's local file playback on a dedicated thread; its
  completion is timed from the file length, and cancelling never fires a stale
  callback. Other sounds and TTS do not use this path.
- Motion follows the [official conversation app](https://github.com/pollen-robotics/reachy_mini_conversation_app):
  one motion owner, smooth transitions, and listening freezes only the antennas
  while breathing continues.
- TTS plays the audio URL from Home Assistant, decodes it to PCM, outputs it
  through the shared SDK audio backend and feeds it, on the SDK playback
  clock, to the official `HeadWobbler/SwayRollRT`, applied to the head through
  `SetSpeechOffsetsCmd`. Music also uses GStreamer but does not move the head.
  No OpenAI API key is needed.
- The audio adapter is implemented by this app to keep URL playback and
  completion callbacks; it reuses the official audio analysis and wobble
  algorithm. The playback drain clock uses SDK internals, so CI tests both the
  oldest supported SDK (1.12.0) and the latest release.
- Conversation text is handled by LVA and Home Assistant; the app does not
  store conversations. macOS is for development only; voice requires Linux.

## Development

```sh
python -m pip install -e '.[test]'
python -m pytest -q
ruff check reachy_mini_ha_voice tests
python -m build
reachy-mini-app-assistant check .
```

Running `python -m reachy_mini_ha_voice.main` locally connects to the robot and
starts voice; do not run it alongside the same app started from the dashboard.

GitHub is the source of truth. To release, raise the version in
`pyproject.toml`, add a `CHANGELOG.md` section and push to `main`. When CI
passes and the version has no `vX.Y.Z` tag yet, CI syncs the Hugging Face Space
(repository secret `HF_TOKEN`, write access to that Space only), then creates
the tag and a GitHub release from the changelog section. Pushes without a
version change only run the tests. Upstream versions and licenses are in
`THIRD_PARTY.md`, validation in `TESTING.md`.

## Changelog

See [CHANGELOG.md](CHANGELOG.md).
