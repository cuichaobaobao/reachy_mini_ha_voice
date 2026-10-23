# Reachy Mini HA Voice implementation

Build a Wireless Python ReachyMiniApp with Home Assistant Assist voice and smooth conversation gestures. Use LVA's ESPHome discovery/wake/audio implementation, with its public peripheral events driving a separate single-owner robot control loop. Keep vendored upstream source unmodified and retain models, sounds and licenses in the installed package. Persist only configuration/preferences in the app data directory.

Validation: automated event/motion/lifecycle tests, real loopback WebSocket, build artifacts, Linux dependency/import checks and official app checker. Physical audio and HA acceptance will be performed by the installer.

Publish GitHub first, then mirror the tested source to Hugging Face. Do not include development environments, caches or credentials.
