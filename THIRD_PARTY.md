# Third-party components

The Linux Voice Assistant runtime and its sounds/wakewords are bundled under `reachy_mini_ha_voice/vendor/lva` from OHF-Voice/linux-voice-assistant, commit `39a10e76dbe028587181fb54d8db7d99d2e3470b`, Apache-2.0. Its license is retained there. Model metadata retains individual author attribution. This runtime owns ESPHome discovery, wake words and microphone input. Local changes in __main__.py adapt TTS playback and own a daemon direction-cache reader; satellite.py attaches a cached direction to the wake event before chime playback. Music also uses the GStreamer adapter with wobbling disabled. entity.py/models.py refer to the adapted player; audio capture uses the SDK adapter. Unused mpv implementation files were removed; upstream license and attribution remain.

Movement architecture is informed by pollen-robotics/reachy_mini_conversation_app (Apache-2.0): a single command owner, bounded smooth state transitions, and quiet listening. Our motion module is a small independent implementation. Speech uses the installed Reachy Mini SDK HeadWobbler/SwayRollRT directly, fed with decoded TTS PCM scheduled against the SDK playback clock, and sends the same speech-offset protocol as the official SDK. The URL player is an application adapter, not a copy of the official full audio stack.

Idle breathing uses the official BreathingMove amplitudes and frequencies (5 mm at 0.1 Hz; opposing antennas 15 degrees at 0.5 Hz), with a 0.3 second idle delay and one second transition. The transition blends to zero antenna offset to avoid the upstream transition boundary jump; steady breathing follows the official equations.

Wake-facing behavior was studied in ha-china/Reachy_Mini_For_Home_Assistant and the referenced reachy_mini_home_assistant_custom Space. Our direction reader and single-loop heading controller are independently implemented; no source from those projects is bundled.

0.4.0 SDK audio ownership was informed by the ha-china reference implementation. No source was copied. The adapter uses SDK GStreamerAudio for capture, ALSA routing, and output; only decoding/mixing and LVA lifecycle adaptation are application code. SDK1.12 internal appsrc timestamps are isolated in sdk_audio.py because the SDK has no public playback-drained API.

0.5.0: LVA runs in a cancellable worker sharing the official application SDK media manager. No no_media clients or separate production audio backend. Parser arguments are injected without changing global argv; logging formatter changes stay local. HA/wake protocol unchanged.
