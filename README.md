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

1. 机器人系统需有可用的 PulseAudio/PipeWire 音频服务及 `libmpv`。若缺少播放库，在机器人终端执行 `sudo apt-get update && sudo apt-get install libmpv2 libpulse0`（旧版 Debian 可使用 `libmpv1`）。应用不会自行提权安装系统包。
2. 在 Reachy Mini 官方 Dashboard 应用安装界面使用 Hugging Face Space `lichao622/reachy_mini_ha_voice` 安装，然后启动。若应用列表尚未更新，使用 Dashboard 支持的 Hugging Face 自定义应用来源安装；这是社区应用，不代表官方审核认证。
3. 确保机器人和 HA 在同一可通信局域网。在 HA「设置 → 设备与服务」接受发现的 ESPHome 设备，选择已配置好 STT/对话代理/TTS 的 Assist 流水线。无需在应用中填写 HA 地址或访问令牌。
4. 说 **Okay Nabu** 唤醒。监听时保持安静姿态，思考时轻微摆头，说话时点头和摆动天线，播放结束后平滑归位。

若自动发现不可用，可在 HA 的 ESPHome 集成中手动输入**机器人 IP，端口 6053**。请勿将该端口转发到公网。语音状态内部接口仅绑定 `127.0.0.1:6055`。

停止其他占用机器人语音/动作的应用后再运行本应用。音频默认使用机器人系统默认输入/输出设备；如果设备选择不正确，可通过下述配置明确指定。

## 配置

默认持久化目录为机器人用户的 `~/.local/share/reachy_mini_ha_voice/`，包含 `config.json`、LVA 偏好及自定义模型下载。可通过 `REACHY_HA_DATA_DIR` 指定其他目录。配置更改后重启应用。

可选 `config.json`（无需 HA token）：

```json
{
  "name": "Reachy Mini HA Voice",
  "wake_model": "okay_nabu",
  "audio_input_device": "ReSpeaker",
  "audio_output_device": "pulse/default",
  "network_interface": "wlan0"
}
```

只填需要覆盖的键；设备名称和网卡名称需符合你的机器人系统。唤醒词也可在 HA 设备页中配置。

## 工作原理与边界

- 保留 OHF 的 [Linux Voice Assistant](https://github.com/OHF-Voice/linux-voice-assistant) 语音运行时、ESPHome API、mDNS、本地唤醒模型及播放功能。
- 通过上游公开 peripheral WebSocket 事件监听 `listening`、`thinking`、`tts_speaking`、`tts_finished`，在同一个 30 Hz 控制循环中驱动机器人。
- 动作设计参考 [Reachy Mini 官方对话应用](https://github.com/pollen-robotics/reachy_mini_conversation_app)：单一控制入口、平滑转换、监听阶段静止降低电机噪声。
- 说话动作按 TTS 播放状态同步，不是逐字嘴型或音量驱动。首版不包含视觉追踪，也不需要 OpenAI API key。
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
