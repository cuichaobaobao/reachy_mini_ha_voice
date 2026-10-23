# Third-party components

The unmodified Linux Voice Assistant runtime and its sounds/wakewords are bundled under `reachy_mini_ha_voice/vendor/lva` from OHF-Voice/linux-voice-assistant, commit `39a10e76dbe028587181fb54d8db7d99d2e3470b`, Apache-2.0. Its license is retained there. Model metadata retains individual author attribution. This runtime owns ESPHome discovery, wake words, microphone and playback.

Movement architecture is informed by pollen-robotics/reachy_mini_conversation_app (Apache-2.0): a single command owner, bounded smooth state transitions, and quiet listening. Our motion module is a small independent implementation. Speech gestures track TTS playback state; they are not phoneme or amplitude synchronized.
