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

[![Tests](https://github.com/cuichaobaobao/reachy_mini_ha_voice/actions/workflows/test.yml/badge.svg)](https://github.com/cuichaobaobao/reachy_mini_ha_voice/actions/workflows/test.yml)
[![Release](https://img.shields.io/github/v/release/cuichaobaobao/reachy_mini_ha_voice)](https://github.com/cuichaobaobao/reachy_mini_ha_voice/releases)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)

**English** | [简体中文](README.zh-CN.md)

A Home Assistant voice assistant for Reachy Mini Wireless. Say the wake word,
talk to Home Assistant, and the robot turns toward you and moves while it
listens and answers.

## Features

- Local wake word on the robot (**Okay Nabu** by default, or the Chinese
  **小派小派**); speech goes to your Home Assistant Assist pipeline.
- Appears in Home Assistant as an ESPHome device, discovered automatically.
- Turns head and body toward whoever said the wake word.
- Breathing, listening and talking motions based on the official
  conversation app.
- Sliders in Home Assistant to point the head and body.
- No cloud service or API key of its own.

## Install

1. In Reachy Mini Control, install **Reachy Mini HA Voice** from the app store
   and start it.
2. In Home Assistant, go to *Settings → Devices & services* and add the
   discovered ESPHome device. Choose an Assist pipeline with speech-to-text
   and text-to-speech.
3. Say “Okay Nabu”.

If the device is not discovered, add it in the ESPHome integration with the
robot's IP and port `6053`. Keep the robot and Home Assistant on the same
network and do not expose this port to the internet.

Requires Reachy Mini Wireless with SDK 1.12 or newer.

## Home Assistant controls

The device page in Home Assistant has:

- **Wake word** choice (up to two at once) and **sensitivity**.
- **Volume** (Media Player), **Mute** (stops listening), thinking sound and
  microphone settings.
- **Manual direction**, used while the app runs:

| Control | Range | What it does |
|---|---|---|
| Body Turn | ±160° | Head and body turn together (negative is left) |
| Head Turn | ±65° | Only the head turns (negative is left) |
| Head Tilt | ±40° | Look up or down (positive is up) |
| Center | — | Back to the standby pose |

When someone wakes the robot, it turns to them and then goes back to the
manual direction. The manual direction resets to straight ahead when the app
restarts.

- **Face Tracking** switch: the head follows the face in front of the camera.
  It pauses during a conversation and while a manual direction is set, and is
  off every time the app starts. Face detection runs in the robot's daemon,
  only while tracking is active.

## Settings

Optional file: `~/.local/share/reachy_mini_ha_voice/config.json` on the robot.
Restart the app after editing it.

```json
{
  "name": "Reachy Mini HA Voice",
  "wake_model": "okay_nabu",
  "network_interface": "wlan0"
}
```

| Key | Meaning |
|---|---|
| `name` | Device name shown in Home Assistant |
| `wake_model` | Default wake word |
| `network_interface` | Network interface to announce on |

## Known limitations

- The microphone array cannot tell front from back, so a voice from behind
  may turn the robot to the mirrored side.
- Side directions are corrected with measurements from one robot; other rooms
  may be less accurate.
- 小派小派 is a self-trained model; check how well it wakes in your home and
  adjust the sensitivity.
- During conversations the media player stays *idle*: replies are played
  directly, not through the media player. The Assist satellite entity shows
  the conversation state.

## How it works

The app bundles OHF's [Linux Voice Assistant](https://github.com/OHF-Voice/linux-voice-assistant)
for the Home Assistant side (ESPHome API, discovery, wake words). Audio goes
through the Reachy Mini SDK, and one motion loop drives the robot using the
motion code of the official [conversation app](https://github.com/pollen-robotics/reachy_mini_conversation_app).

## Development

```sh
python -m pip install -e '.[test]'
python -m pytest -q
ruff check reachy_mini_ha_voice tests
reachy-mini-app-assistant check .
```

To release, raise the version in `pyproject.toml`, add a section to
[CHANGELOG.md](CHANGELOG.md) and push to `main`. When the tests pass, CI
publishes the Hugging Face Space and the GitHub release. Details on testing
are in [TESTING.md](TESTING.md).

## Credits and license

- [Linux Voice Assistant](https://github.com/OHF-Voice/linux-voice-assistant) by the Open Home Foundation
- [Reachy Mini conversation app](https://github.com/pollen-robotics/reachy_mini_conversation_app) by Pollen Robotics

This is a community app, not made by Pollen Robotics. Licensed under
Apache-2.0; bundled third-party code is listed in [THIRD_PARTY.md](THIRD_PARTY.md).
