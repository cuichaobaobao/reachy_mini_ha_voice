# Third-party components

The Linux Voice Assistant runtime and its sounds/wakewords are bundled under `reachy_mini_ha_voice/vendor/lva` from OHF-Voice/linux-voice-assistant, commit `39a10e76dbe028587181fb54d8db7d99d2e3470b`, Apache-2.0. Its license is retained there. Model metadata retains individual author attribution. This runtime owns ESPHome discovery, wake words and microphone input. Local changes in __main__.py adapt TTS playback and own a daemon direction-cache reader; satellite.py attaches a cached direction to the wake event before chime playback. Music also uses the GStreamer adapter with wobbling disabled. entity.py/models.py refer to the adapted player; audio capture uses the SDK adapter. Unused mpv implementation files were removed; upstream license and attribution remain.

BreathingMove is copied from pollen-robotics/reachy_mini_conversation_app (Apache-2.0), commit `c178d4aa375f2a3968b1340932870b4c54af83c9`, `src/reachy_mini_conversation_app/moves.py`, into `official_breathing.py`. Its class body is unchanged; only the unused abstract Move base/import context is omitted. The source attribution is retained in the module; this repository includes Apache-2.0 LICENSE. The pinned complete upstream moves.py and license under tests/fixtures serve as an offline executable comparison oracle, not installed application code.

The app adapts the official queue/start and listening freeze/blend logic for a breathing-only primary move. Actual SDK feedback supplies the transition origin; acoustic heading is removed/reapplied as a separate application feature. Official random idle tools, dance/emotion queues and full tracking handoff are not copied. Speech still uses installed SDK HeadWobbler directly, with application PCM/timestamp feeding; this is not the complete official audio stack.

The direction reader and single-loop heading controller are independently implemented.

0.4.0: The adapter uses SDK GStreamerAudio for capture, ALSA routing, and output; only decoding/mixing and LVA lifecycle adaptation are application code. SDK1.12 internal appsrc timestamps are isolated in sdk_audio.py because the SDK has no public playback-drained API.

0.5.0: LVA runs in a cancellable worker sharing the official application SDK media manager. No no_media clients or separate production audio backend. Parser arguments are injected without changing global argv; logging formatter changes stay local. HA/wake protocol unchanged.

Historical 0.5.1 (superseded by0.6.0/0.6.1): official conversation moves.py uses60Hz,0.1Hz/5mm breathing,0.5Hz/15° antenna sway and.4s unfreeze; SDK troubleshooting/PR952 recommends±10° rest bias. This app retains that bias during sway and uses a smooth interpolation envelope to avoid upstream's rest-to-zero boundary jump. Thinking gestures and acoustic heading remain application-specific.

0.6.3 listening freeze deviation: official conversation moves.py freezes antennas at the last commanded sway value, which can sit at 0 degrees where the gearbox is unstable and shakes. Following the SDK troubleshooting guide and PR #952, a freeze inside 8 degrees of vertical is eased (0.2 s, same direction) onto the +/-10 degree resting bias. The BreathingMove waveform, 0.4 s unfreeze blend, 60 Hz loop, acoustic heading and speech wobble are unchanged; this is the only deliberate motion deviation.

0.6.4 consistency fix: leaving listening (including mid-adjustment) now starts the 0.4 s unfreeze blend from the last successfully sent antenna target, not from a computed frame that may never have reached the robot. No change to the deadzone rule, waveform, heading or audio.

0.6.5 wake direction filter: the raw DOA stream jumps by tens of degrees between samples and wraps at 0/pi, so the wake snapshot is now the circular median of the last 0.4 s of speech-flagged samples of that utterance, falling back to all recent samples only when the hardware VAD never flagged it. The turn formula, deadband, limits, hold/return timing, motion waveform, audio and HA protocol are unchanged.
