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

让 Reachy Mini Wireless 成为 Home Assistant Assist 语音卫星：本地唤醒、ESPHome 自动发现、语音对话，以及聆听、思考和说话时的平滑头部/天线动作。

## 安装与连接

本应用使用官方 `ReachyMiniApp` 入口，运行在 Wireless 的 Linux 系统上，不在 Hugging Face 网页服务器上运行。Python 需要 3.11 或更高版本。

1. 使用机器人现有的 Reachy Mini SDK 1.12 音频环境。录音、播放统一使用 SDK 的本地 GStreamer/ALSA 后端，不要求 PulseAudio 或 libmpv；应用不会安装系统包或改写音频配置。
2. 在 Reachy Mini 官方 Dashboard 应用安装界面使用 Hugging Face Space `lichao622/reachy_mini_ha_voice` 安装并启动。若列表未更新，使用 Dashboard 支持的 Hugging Face 自定义应用来源；这是社区应用，不代表官方审核认证。
3. 确保机器人和 HA 在同一局域网。在 HA「设置 → 设备与服务」接受发现的 ESPHome 设备，并选择已配置 STT/对话代理/TTS 的 Assist 流水线。无需在应用中填 HA 地址或令牌。
4. 说唤醒词（默认 **Okay Nabu**）开始对话。

自动发现不可用时，可在 HA 的 ESPHome 集成中手动输入**机器人 IP，端口 6053**。请勿将该端口转发到公网；语音状态内部接口仅绑定 `127.0.0.1:6055`。

也可以使用官方 daemon 安装 API（把 `ROBOT_IP` 换成你的机器人地址）：

```sh
curl -X POST http://ROBOT_IP:8000/api/apps/install \
  -H 'Content-Type: application/json' \
  -d '{"name":"reachy_mini_ha_voice","source_kind":"hf_space","url":"https://huggingface.co/spaces/lichao622/reachy_mini_ha_voice"}'
```

停止其他占用机器人语音/动作的应用后再运行本应用。若启动失败，查看完整应用日志；应用会在发布 HA 自动发现前检查 SDK 是否能收到麦克风数据。

## 唤醒与动作

- **启动**：与官方对话应用一致，应用启动时只在机器人确实处于睡姿时执行一次官方唤醒动作（先通电再唤醒）；daemon 已唤醒（含启动应用）不会重复点头或播放唤醒音。
- **空闲**：0.3 秒后进入官方 `BreathingMove`，1 秒过渡到中性位，随后头部 5 mm/0.1 Hz、天线反向 ±15°/0.5 Hz，60 Hz 输出。
- **唤醒转向**：提示音前锁定最近的人声方向，结合实测头部姿态换算目标；偏差小于 3° 不转，其余使用完整角度，头与身体沿同一平滑轨迹转向，仅受身体 ±160° 边界限制。时长按目标角差计算，限制在 0.65–1.25 秒。
- **聆听**：只冻结天线（停在当时最后成功下发的角度，接近 0° 时用 0.2 秒挪到同方向 ±10°），已启动的呼吸继续；退出聆听用 0.4 秒混回。
- **思考/说话**：背景呼吸继续；说话时由实际 TTS PCM 驱动官方 `HeadWobbler`，偏移只叠加在头部。
- **结束**：播放完成且未继续聆听时，保持朝向 5 秒，再用 1.5 秒让头与身体一起回正；期间再次唤醒会取消回正并转向新声源。聆听或思考阶段 120 秒无更新会解除保持。

方向来自共用 SDK 媒体实例的 DOA，头部姿态使用 SDK 遥测缓存，约 20 Hz 取样，不另开录音设备。视觉追踪默认关闭；显式开启时会在朝向保持和回正期间暂停。

## 配置

默认持久化目录为机器人用户的 `~/.local/share/reachy_mini_ha_voice/`，包含 `config.json`、LVA 偏好及自定义模型下载；可用 `REACHY_HA_DATA_DIR` 指定其他目录。配置修改后重启应用。

可选 `config.json`（无需 HA token）：

```json
{
  "name": "Reachy Mini HA Voice",
  "head_tracking": false,
  "wake_model": "okay_nabu",
  "network_interface": "wlan0"
}
```

`head_tracking` 默认为 `false`，仅显式设为 `true` 才启用。只填需要覆盖的键；设备名和网卡名需符合你的机器人系统。唤醒词也可在 HA 设备页中配置。

0.4.0 起音频设备由 SDK 管理，旧配置中的 `audio_input_device`、`audio_output_device` 必须移除。

## 已知限制

- **DOA 只有半平面**：麦克风线性阵列输出 0–π（0=左、π/2=正前/正后、π=右），**无法区分正前与正后**。侧后方的声源会被折到前半球，转向可能偏向镜像位置。
- **侧面角度会被压缩**：实测站 45–60° 时读数只对应约 13–27° 的转向，因此转向幅度可能小于实际角度；这不是死区或 ±160° 限制造成的。
- **读数噪声**：唤醒词期间常只有少量 `speech=True` 样本，个别读数会跳变；0.6.5 起用语音样本中位数抑制，但不能保证每次都准。
- **HA 首次配置**：向导可能在“连接测试”时因并发公告报“无法连接到 Home Assistant”，通常与音频无关；等测试音结束后点一次重试，或手动添加 ESPHome 即可。
- **唤醒词为英文模型**：内置模型不含中文；需要中文唤醒词时通过 HA 的 external wake word 机制提供自定义模型。
- **天线零位抖动**：0° 是机械不稳定平衡点，软件只能避免“静止保持在 0°”，不能保证消除每台机器的齿隙抖动。
- 真机音频效果、唤醒率、转向准确度和 HA 全链路仍需安装后验收，见 `TESTING.md`。

## 工作原理与边界

- 保留 OHF 的 [Linux Voice Assistant](https://github.com/OHF-Voice/linux-voice-assistant) 运行时、ESPHome API、mDNS 和本地唤醒模型；其公开 peripheral WebSocket 事件经队列交给专用动作线程，统一执行单个 60 Hz 控制循环。
- 唤醒提示音使用 SDK 本地文件播放：专用线程调用 SDK `media.play_sound()`，按文件时长等待后通知 LVA 开始聆听；取消不会触发过期回调。时长等待不是声卡播放完成确认。其他提示音和 TTS 不走这条专用路径。
- 动作用法参考 [Reachy Mini 官方对话应用](https://github.com/pollen-robotics/reachy_mini_conversation_app)：单一控制入口、平滑转换、聆听仅冻结天线并保留已运行的呼吸。
- TTS 播放 HA 返回的音频 URL，解码 PCM 经共享 SDK 音频后端输出，并按 SDK 播放时钟交给官方 `HeadWobbler/SwayRollRT`，通过官方 `SetSpeechOffsetsCmd` 叠加到头部。音乐同样走 GStreamer，但不驱动头部动作。无需 OpenAI API key。
- 为保留 URL 播放与完成回调，音频适配层由本应用实现；复用官方音频分析与定时摆动算法，但不是复制整个官方对话应用。SDK 固定 `>=1.12,<1.13`，因为播放排空时钟使用该版本的内部接口。
- 原始对话文本由 LVA/HA 处理，本应用不保存对话记录。macOS 仅用于开发测试，实际语音运行要求 Linux。

## 开发与验证

```sh
python -m pip install -e '.[test]'
python -m pytest -q
ruff check reachy_mini_ha_voice tests
python -m build
reachy-mini-app-assistant check .
```

本地直接运行 `python -m reachy_mini_ha_voice.main` 会连接机器人并启动语音，不应与 Dashboard 中已启动的同一应用同时运行。

源码以 GitHub 为主，检查通过后同步到 Hugging Face。上游版本与许可见 `THIRD_PARTY.md`，测试与环境说明见 `TESTING.md`。

## 变更记录

见 [CHANGELOG.md](CHANGELOG.md)。
