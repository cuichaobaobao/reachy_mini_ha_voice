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

让 Reachy Mini Wireless 成为 Home Assistant Assist 语音卫星：本地唤醒、ESPHome 自动发现、语音对话，以及思考和说话时的平滑头部/天线动作。

## 安装与连接

本应用使用官方 `ReachyMiniApp` 入口，运行在 Wireless 的 Linux 系统上，不在 Hugging Face 网页服务器上运行。Python 需要 3.11 或更高版本。

1. 使用机器人现有的 Reachy Mini SDK 1.12 音频环境。**0.4.0 起录音、播放统一使用 SDK 的本地 GStreamer 音频后端**，Wireless 使用现有 ALSA 配置，不要求 PulseAudio 或 libmpv；应用不会安装系统包或改写音频配置。
2. 在 Reachy Mini 官方 Dashboard 应用安装界面使用 Hugging Face Space `lichao622/reachy_mini_ha_voice` 安装，然后启动。若应用列表尚未更新，使用 Dashboard 支持的 Hugging Face 自定义应用来源安装；这是社区应用，不代表官方审核认证。
3. 确保机器人和 HA 在同一可通信局域网。在 HA「设置 → 设备与服务」接受发现的 ESPHome 设备，选择已配置好 STT/对话代理/TTS 的 Assist 流水线。无需在应用中填写 HA 地址或访问令牌。
4. 说 **Okay Nabu** 唤醒。监听时保持安静姿态，思考时轻微摆头，说话时由实际 TTS 音频驱动头部摆动，播放结束后平滑转入空闲呼吸。空闲 0.3 秒后用 1 秒过渡，随后头部上下 ±5 mm（0.1 Hz，每分钟 6 次），天线反向摆动 ±15°（0.5 Hz），参数采用官方对话应用的 BreathingMove；监听时冻结天线并抑制呼吸，头部追踪默认关闭（可配置开启，需机器人系统支持）。

### 唤醒转向与回正（0.3.1）

唤醒时从 daemon 缓存锁定最近的人声方向（提示音播放前），结合当时实际头部姿态换算目标方向。偏差小于 6°不转；其余使用完整角度，头部和身体沿同一平滑轨迹协同转向，仅在身体 ±160°边界内限制目标；这不是让头部相对身体扭转 ±160°。转向时长为实际目标角差 ÷ 75°/秒，限制在 0.65～1.25 秒。

对话期间保持该朝向，思考和官方音频驱动动作叠加其上。回复实际播放结束、且未继续聆听时，等待 5 秒，再用 1.5 秒让头部与身体一起平滑回正，随后恢复空闲呼吸。等待或回正途中再次唤醒会取消旧任务，并从当前位置转向新声源；方向缺失或过期则保持当前位置继续对话。连续聆听会取消回正倒计时，错误/断线会安排回正；聆听或思考阶段 120 秒没有更新的异常对话也会解除朝向保持。

方向从已接管音频的 SDK 实例读取，头部姿态通过本机 daemon 的 `/api/state/full` 读取，不另开录音设备。需 ReSpeaker 返回有效方向数据；不可用时跳过转向，语音照常工作。视觉追踪默认关闭；即使显式开启，也会在声源朝向保持和回正期间暂停，避免抢占头部。

此功能尚需真机校准左右方向、侧头后的角度换算与电机声影响。DOA 不能保证区分前后声源；唤醒转向由头部与身体共同完成；说话时身体保持基础朝向，仅头部叠加思考/语音摆动。

若自动发现不可用，可在 HA 的 ESPHome 集成中手动输入**机器人 IP，端口 6053**。请勿将该端口转发到公网。语音状态内部接口仅绑定 `127.0.0.1:6055`。

也可以使用官方 daemon 安装 API（将 `ROBOT_IP` 替换为你的机器人地址）：

```sh
curl -X POST http://ROBOT_IP:8000/api/apps/install \
  -H 'Content-Type: application/json' \
  -d '{"name":"reachy_mini_ha_voice","source_kind":"hf_space","url":"https://huggingface.co/spaces/lichao622/reachy_mini_ha_voice"}'
```

若启动失败，请查看完整应用日志。应用会在发布 HA 自动发现前检查 SDK 是否能收到麦克风数据。不要为了此应用额外启用 PulseAudio。

停止其他占用机器人语音/动作的应用后再运行本应用。音频默认使用机器人系统默认输入/输出设备；如果设备选择不正确，可通过下述配置明确指定。

## 配置

默认持久化目录为机器人用户的 `~/.local/share/reachy_mini_ha_voice/`，包含 `config.json`、LVA 偏好及自定义模型下载。可通过 `REACHY_HA_DATA_DIR` 指定其他目录。配置更改后重启应用。

可选 `config.json`（无需 HA token）：

```json
{
  "name": "Reachy Mini HA Voice",
  "head_tracking": false,
  "wake_model": "okay_nabu",
  "network_interface": "wlan0"
}
```

`head_tracking` 默认为 `false`，仅显式设为 `true` 才启用头部追踪。

只填需要覆盖的键；设备名称和网卡名称需符合你的机器人系统。唤醒词也可在 HA 设备页中配置。

## 工作原理与边界

- 保留 OHF 的 [Linux Voice Assistant](https://github.com/OHF-Voice/linux-voice-assistant) 语音运行时、ESPHome API、mDNS、本地唤醒模型及播放功能。
- 通过上游公开 peripheral WebSocket 事件监听 `listening`、`thinking`、`tts_speaking`、`tts_finished`，在同一个 30 Hz 控制循环中驱动机器人。
- 动作设计参考 [Reachy Mini 官方对话应用](https://github.com/pollen-robotics/reachy_mini_conversation_app)：单一控制入口、平滑转换、监听阶段冻结天线并抑制呼吸。
- TTS 使用 GStreamer 播放 HA 返回的音频 URL；解码 PCM 经共享 SDK 音频后端播放，按 SDK 播放时钟将 TTS PCM 交给官方 `HeadWobbler/SwayRollRT`，通过官方 `SetSpeechOffsetsCmd` 由 daemon 叠加到头部姿态。播放结束或打断清零偏移。音乐也使用 GStreamer，但不驱动头部动作。无需 OpenAI API key。
- 为保留 LVA 的 URL 播放和完成回调，音频适配层由本应用实现；复用官方音频分析与定时摆动算法，但并非复制整个官方对话应用。需 SDK 和机器人 daemon 支持 1.12.0 的头部追踪、语音偏移协议。说话时暂不采用官方“锁定人脸后暂停追踪”的策略。
- 原始对话文本由 LVA/HA 处理；本应用不保存对话记录。
- macOS 仅用于开发测试，实际语音运行要求 Linux。真机音频效果、唤醒率与 HA 端到端接入须安装后验证，见 `TESTING.md`。

## 开发与验证

```sh
python -m pip install -e '.[test]'
python -m pytest -q
ruff check reachy_mini_ha_voice tests
python -m build
reachy-mini-app-assistant check .
```

本地直接运行：`python -m reachy_mini_ha_voice.main`。这会连接机器人并启动语音，不应与官方 Dashboard 中已启动的同一应用同时运行。

源码以 GitHub 为主，完成检查后同步到 Hugging Face。上游源码和资源版本、许可见 `THIRD_PARTY.md`。

0.4.0 音频适配：设备选择由 SDK 管理，旧配置中的 `audio_input_device`、`audio_output_device` 必须移除。TTS 与媒体音频混合后送入 SDK，只有 TTS 音频驱动头部。停止/替换/暂停会清空共享输出队列，录音管线继续工作。播放完成按 SDK 时钟及管线延迟判断，不以下载或解码结束代替。

### 0.5.0：保留视频服务
应用通过官方 `ReachyMiniApp` 创建一个 `local` SDK 实例。LVA 在可取消的工作线程中共用 `reachy_mini.media`，录音和播放不再另建后端或 `no_media` 客户端。旧版 `no_media` 会让 daemon 释放媒体设备，影响 Dashboard/WebRTC 视频；新版不再请求释放。HA 协议、唤醒词和动作逻辑不变。

SDK 1.12 没有公开的播放排空时钟接口，精确播放结束及 TTS 动作同步仍在适配层使用该版本内部时间戳，因此继续限制 SDK <1.13。虚拟设备测试不能代替真机视频、音频延迟和 HA 全链路验收。
