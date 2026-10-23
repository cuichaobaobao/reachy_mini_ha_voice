# Reachy Mini HA Voice implementation

Build a Wireless Python ReachyMiniApp with Home Assistant Assist voice and smooth conversation gestures. Use LVA's ESPHome discovery/wake/audio implementation, with its public peripheral events driving a separate single-owner robot control loop. Keep vendored upstream source unmodified and retain models, sounds and licenses in the installed package. Persist only configuration/preferences in the app data directory.

Validation: automated event/motion/lifecycle tests, real loopback WebSocket, build artifacts, Linux dependency/import checks and official app checker. Physical audio and HA acceptance will be performed by the installer.

Publish GitHub first, then mirror the tested source to Hugging Face. Do not include development environments, caches or credentials.

## 0.2.0 audio-driven motion
User approved actual TTS PCM driving official HeadWobbler, frozen listening antennas with breathing suppressed and tracking retained; thinking unchanged. Implement a GStreamer URL player preserving LVA completion callbacks, music stays mpv. Validate real PCM/DSP/EOS/interruption in Linux CI; user performs hardware acceptance.

0.2.1: User requests head tracking off by default. Explicitly disable on startup unless config head_tracking is true; bundled microWakeWord models retained.

## 0.3.0 wake direction (approved)
Read daemon DOA with measured head pose before wake sound; cache recent speech only, ignore playback, convert relative angle into world yaw. Use 6 degree deadband, full angle clamped to conservative ±40 degree base yaw, smooth turn duration clamp(abs(delta)/75, .65, 1.25). Keep conversation heading separate from thinking/TTS offsets. After real playback finish and no continued listening, wait 5 seconds then return over 1.5 seconds. New wake cancels hold/return and targets new direction directly. Visual tracking stays off by default; acoustic heading takes priority when enabled. No robot connection during development; virtual daemon, lifecycle and Linux audio tests before GitHub/HF publication.
