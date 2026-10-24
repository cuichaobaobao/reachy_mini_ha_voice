# Reachy Mini HA Voice implementation

Build a Wireless Python ReachyMiniApp with Home Assistant Assist voice and smooth conversation gestures. Use LVA's ESPHome discovery/wake/audio implementation, with its public peripheral events driving a separate single-owner robot control loop. Keep upstream HA/wake logic intact; document narrow audio/peripheral adaptations and retain models, sounds and licenses in the installed package. Persist only configuration/preferences in the app data directory.

Validation: automated event/motion/lifecycle tests, real loopback WebSocket, build artifacts, Linux dependency/import checks and official app checker. Physical audio and HA acceptance will be performed by the installer.

Publish GitHub first, then mirror the tested source to Hugging Face. Do not include development environments, caches or credentials.

## 0.2.0 audio-driven motion
User approved actual TTS PCM driving official HeadWobbler, frozen listening antennas with breathing suppressed and tracking retained; thinking unchanged. Implement a GStreamer URL player preserving LVA completion callbacks, music stays mpv. Validate real PCM/DSP/EOS/interruption in Linux CI; user performs hardware acceptance.

0.2.1: User requests head tracking off by default. Explicitly disable on startup unless config head_tracking is true; bundled microWakeWord models retained.

## 0.3.0 wake direction (approved)
Read daemon DOA with measured head pose before wake sound; cache recent speech only, ignore playback, convert relative angle into world yaw. Use 6 degree deadband, full angle clamped to conservative ±40 degree base yaw, smooth turn duration clamp(abs(delta)/75, .65, 1.25). Keep conversation heading separate from thinking/TTS offsets. After real playback finish and no continued listening, wait 5 seconds then return over 1.5 seconds. New wake cancels hold/return and targets new direction directly. Visual tracking stays off by default; acoustic heading takes priority when enabled. No robot connection during development; virtual daemon, lifecycle and Linux audio tests before GitHub/HF publication.

## 0.3.1 coordinated wake turn (approved correction)
Remove arbitrary ±40° cap. Full DOA-derived heading drives both world head yaw and body yaw via the same smoothed trajectory, bounded only by ±160° body range. Thinking and audio sway remain head-only offsets. Both axes return to zero after 5s hold over 1.5s. Test actual app output, not just heading arithmetic.

## 0.3.2 robot startup fix
User robot fails due to missing libmpv. Remove runtime dependency and switch music to GStreamer without speech motion. Test actual LVA boot and media controls in Linux with libmpv absent, then publish GitHub/HF. Do not connect to robot or install OS packages on it.

## 0.4.0 SDK audio adapter (approved)
Replace soundcard/PulseAudio input and direct pulsesink output with one SDK-owned audio backend in the LVA child; parent remains no_media and owns base motion. Preserve upstream wake/HA protocol logic. Use SDK synchronized wobbling and playback clock, bounded decode queues, shared playback mixing, clear_player on interruption and deterministic shutdown. Verify SDK1.12 interfaces against read-only robot source. Add no-Pulse Linux virtual-device integration and unit regressions; publish only after checks. Robot remains read-only.
