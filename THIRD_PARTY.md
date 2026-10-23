# Third-party components

The Linux Voice Assistant runtime and its sounds/wakewords are bundled under `reachy_mini_ha_voice/vendor/lva` from OHF-Voice/linux-voice-assistant, commit `39a10e76dbe028587181fb54d8db7d99d2e3470b`, Apache-2.0. Its license is retained there. Model metadata retains individual author attribution. This runtime owns ESPHome discovery, wake words and microphone input. Local changes in __main__.py replace only the TTS player with ReachyTtsPlayer and close it during shutdown; music remains on mpv.

Movement architecture is informed by pollen-robotics/reachy_mini_conversation_app (Apache-2.0): a single command owner, bounded smooth state transitions, and quiet listening. Our motion module is a small independent implementation. Speech uses the installed Reachy Mini SDK HeadWobbler/SwayRollRT directly, fed from a synchronized GStreamer PCM appsink, and sends the same speech-offset protocol as the official SDK. The URL player is an application adapter, not a copy of the official full audio stack.

Idle breathing uses the official BreathingMove amplitudes and frequencies (5 mm at 0.1 Hz; opposing antennas 15 degrees at 0.5 Hz), with a 0.3 second idle delay and one second transition. The transition blends to zero antenna offset to avoid the upstream transition boundary jump; steady breathing follows the official equations.
