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
4. 说 **Okay Nabu** 唤醒。监听时冻结天线，思考时按官方背景呼吸运行，说话时由实际 TTS 音频驱动头部摆动，播放结束后继续已有呼吸。空闲 0.3 秒后用 1 秒过渡，随后头部上下 ±5 mm（0.1 Hz，每分钟 6 次），天线反向摆动 ±15°（0.5 Hz），参数采用官方对话应用的 BreathingMove；监听时冻结天线；已启动的呼吸继续，尚未启动则等待聆听结束，头部追踪默认关闭（可配置开启，需机器人系统支持）。

### 唤醒转向与回正（0.3.1）

唤醒时从 daemon 缓存锁定最近的人声方向（提示音播放前），结合当时实际头部姿态换算目标方向。偏差小于 6°不转；其余使用完整角度，头部和身体沿同一平滑轨迹协同转向，仅在身体 ±160°边界内限制目标；这不是让头部相对身体扭转 ±160°。转向时长为实际目标角差 ÷ 75°/秒，限制在 0.65～1.25 秒。

对话期间保持该朝向，思考和官方音频驱动动作叠加其上。回复实际播放结束、且未继续聆听时，等待 5 秒，再用 1.5 秒让头部与身体一起平滑回正，背景呼吸独立持续（聆听期间不新启动呼吸）。等待或回正途中再次唤醒会取消旧任务，并从当前位置转向新声源；方向缺失或过期则保持当前位置继续对话。连续聆听会取消回正倒计时，错误/断线会安排回正；聆听或思考阶段 120 秒没有更新的异常对话也会解除朝向保持。

方向从共用 SDK 媒体实例读取，头部姿态使用 SDK 的遥测缓存，以约 20 Hz 取样，不另开录音设备，也不逐次请求 HTTP。需 ReSpeaker 返回有效方向数据；不可用时跳过转向，语音照常工作。视觉追踪默认关闭；即使显式开启，也会在声源朝向保持和回正期间暂停，避免抢占头部。

此功能尚需真机校准左右方向、侧头后的角度换算与电机声影响。DOA 不能保证区分前后声源；唤醒转向由头部与身体共同完成；说话时身体保持基础朝向，仅头部叠加语音摆动。

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
- 通过上游公开 peripheral WebSocket 事件监听 `listening`、`thinking`、`tts_speaking`、`tts_finished`，在同一个 60 Hz 控制循环中驱动机器人。
- 动作设计参考 [Reachy Mini 官方对话应用](https://github.com/pollen-robotics/reachy_mini_conversation_app)：单一控制入口、平滑转换、监听阶段仅冻结天线，保留已运行的呼吸。
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

### 0.5.1：天线与唤醒转向（下述持续偏置已在0.6.0撤回）
- 启动/停止和静止目标采用右 -10°、左 +10°，对应官方防抖建议；不会写入电机 PID 或固件。聆听仍冻结当前位置，因此不能保证每台机器在任意冻结角度都没有机械抖动。
- 指令循环60Hz，扣除计算耗时。呼吸保留官方0.1Hz/5mm、天线0.5Hz/15°参数，聆听后0.4秒混合恢复。说话时允许背景呼吸，语音摆头仍由实际TTS音频驱动。
- 与上游代码的明确差异：天线摆动持续叠加±10°偏置（范围右-25°～+5°、左-5°～+25°），用平滑过渡接入，避免上游插值阶段结束时从偏置突然跳回零基线。不是逐帧复刻整个官方对话动作系统。
- 唤醒仍按完整测得角度转动：6°死区、0.65～1.25秒、头身协同、身体±160°边界均未改变。SDK当前DOA接口是0～π，正前方π/2，左右对应±90°，不能单靠它区分正前与正后。不会人为放大声源角度。
- 日志 `Wake turn:` 显示原始DOA、相对角度、目标和取样年龄；`Wake turn measured:` 显示转向结束后SDK实测头/身朝向；跳过时会说明死区或缺少新鲜语音读数。真机幅度问题须结合这些日志确认。

### 0.5.2：首次公告播放
修复播放器把尚未启动时的 `appsink.eos=true` 误判为播放结束的问题。现在仅在收到真实 GStreamer EOS 消息、PCM 队列及已提交声音均结束后完成播放。增加公告接收、下载解码首帧与结束日志（不记录完整签名 URL 或公告文本）。新增冷启动 EOS 回归及真实 LVA 首次公告到 HTTP 音频获取测试；不延长 HA 测试超时，也不修改动作参数。实际 HA 首次设置仍需安装后验收。

### 0.6.0：官方动作与持续运行
- 恢复官方 BreathingMove 两阶段公式：1秒线性过渡至±0.1745rad，再以零为中心进行15°/0.5Hz天线摆动，头部5mm/0.1Hz。撤销持续偏置、自定义插值和固定思考摆头。非聆听阶段使用同一背景呼吸；声源朝向独立叠加，仍保留5秒等待和1.5秒回中。
- 聆听冻结当时的天线目标，解冻0.4秒。完全冻结仍可能停在零位，官方机制并不保证消除机械齿隙抖动；记录冻结目标和实测角度，不擅改PID或角度。
- 唤醒已确认后使用0.6秒内方向读数，不再要求硬件VAD仍为真；禁止使用播放期间读数。完整角度、6°死区、±160°身体边界不变。方向小或前后歧义不能靠软件任意放大解决。
- SDK动作心跳暂失不再使语音退出；持续5秒失败后仅重连SDK WebSocket，保留LVA/音频/HA连接。日志记录接收线程、关闭码、原因和恢复耗时。SDK1.12无公开重连方法，此兼容层只替换client，不修改SDK或daemon。
- 修复HA仍连接时退出等待阻塞；先关闭已接受的连接，再等待服务结束。wobbler发送失败按官方SDK作为可忽略的动作错误处理，不中断音频或清理。
- 历史故障已确认是set_target连接错误触发应用退出，随后清理超时；历史日志不足以判定最初是心跳间隙还是socket关闭。新日志区分两者。持续运行的模拟/CI测试不代替真机长时间验收。

### 0.6.1：呼吸与天线的行为核对修正
- 对照固定官方版本 `c178d4aa375f2a3968b1340932870b4c54af83c9`：直接采用 `BreathingMove` 类体；0.3秒空闲后排队、下一控制帧启动，1秒从反馈姿态过渡到中性位。天线稳态围绕0°反向摆动±15°/0.5Hz；±0.1745rad仅为过渡目标，不是持续偏置。
- 纠正0.6.0的整帧冻结：聆听只冻结天线最后指令，已有（含已排队）的呼吸继续；未启动呼吸则不在聆听时新启动。退出聆听用0.4秒混合接回原相位，不重新计时。
- 声源朝向独立合成，保留头身完整角度协同、±160°身体边界、5秒保持及1.5秒回正。转向不是官方呼吸的一部分。
- **未对齐范围**：不含官方180秒后的随机空闲工具/舞蹈情绪库和完整动作队列；LVA状态来源、音频适配与HeadWobbler接入、可选追踪的交接逻辑仍为本应用实现。此次没有修改它们，也未修复HA公告忙碌问题。
- 自动化对比覆盖呼吸/聆听基础动作；不等同于真机天线不抖或实际声源定位准确的验证。
