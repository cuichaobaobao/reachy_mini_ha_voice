# Reachy Mini HA Voice

[![Tests](https://github.com/cuichaobaobao/reachy_mini_ha_voice/actions/workflows/test.yml/badge.svg)](https://github.com/cuichaobaobao/reachy_mini_ha_voice/actions/workflows/test.yml)
[![Release](https://img.shields.io/github/v/release/cuichaobaobao/reachy_mini_ha_voice)](https://github.com/cuichaobaobao/reachy_mini_ha_voice/releases)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)

[English](README.md) | **简体中文**

给 Reachy Mini Wireless 用的 Home Assistant 语音助手。喊一声唤醒词就能和 Home Assistant 对话，机器人会转向你，在听和回答时做出相应的动作。

## 功能

- 唤醒词在机器人本地识别（默认 **Okay Nabu**，也可以用中文 **小派小派**），你说的话交给 Home Assistant 的 Assist 处理。
- 在 Home Assistant 里是一个 ESPHome 设备，会被自动发现。
- 谁喊的唤醒词，头和身体就转向谁。
- 呼吸、聆听、说话时的动作参照官方对话应用。
- 在 Home Assistant 里用滑块调头和身体的朝向。
- 不依赖额外的云服务，也不需要 API 密钥。

## 安装

1. 在 Reachy Mini Control 的应用商店里安装 **Reachy Mini HA Voice** 并启动。
2. 在 Home Assistant「设置 → 设备与服务」里添加发现的 ESPHome 设备，选一个配置好语音识别和语音合成的 Assist 流程。
3. 喊“Okay Nabu”。

如果没有被自动发现，在 ESPHome 集成里手动添加：机器人 IP，端口 `6053`。机器人和 Home Assistant 要在同一个局域网，不要把这个端口开放到公网。

需要 Reachy Mini Wireless，SDK 1.12 或更新版本。

## 在 Home Assistant 里能调什么

设备页上有：

- **唤醒词**选择（最多同时两个）和**灵敏度**。
- **音量**（Media Player）、**静音**（停止监听）、思考提示音和麦克风设置。
- **手动方向**（应用运行时可用）：

| 控件 | 范围 | 作用 |
|---|---|---|
| Body Turn | ±160° | 头和身体一起转（负值向左） |
| Head Turn | ±65° | 只转头（负值向左） |
| Head Tilt | ±40° | 抬头或低头（正值抬头） |
| Center | — | 回到待机姿势 |

有人唤醒时，机器人会转向说话的人，结束后回到你设的方向。应用重启后，手动方向回到正前方。

## 设置

可选文件：机器人上的 `~/.local/share/reachy_mini_ha_voice/config.json`，改完后重启应用。

```json
{
  "name": "Reachy Mini HA Voice",
  "head_tracking": false,
  "wake_model": "okay_nabu",
  "network_interface": "wlan0"
}
```

| 键 | 含义 |
|---|---|
| `name` | 在 Home Assistant 里显示的设备名 |
| `head_tracking` | 用摄像头跟随人脸（默认关闭） |
| `wake_model` | 默认唤醒词 |
| `network_interface` | 用哪个网卡对外发布 |

## 已知限制

- 麦克风阵列分不清正前和正后，从背后说话时机器人可能转到对称的方向。
- 侧面方向的校正数据来自一台机器人，换个房间可能没那么准。
- 小派小派是自己训练的模型，请在家里实际试试唤醒效果，按需调灵敏度。
- 对话时 Media Player 一直显示“空闲”，因为回答是直接播放的，不经过 Media Player。想看对话状态，请看“语音助手卫星”实体。

## 原理

应用内置 OHF 的 [Linux Voice Assistant](https://github.com/OHF-Voice/linux-voice-assistant) 负责 Home Assistant 这一侧（ESPHome 接口、自动发现、唤醒词）。声音走 Reachy Mini SDK，动作由一个动作循环统一控制，用的是官方[对话应用](https://github.com/pollen-robotics/reachy_mini_conversation_app)的动作代码。

## 开发

```sh
python -m pip install -e '.[test]'
python -m pytest -q
ruff check reachy_mini_ha_voice tests
reachy-mini-app-assistant check .
```

发布：在 `pyproject.toml` 提升版本号，在 [CHANGELOG.md](CHANGELOG.md) 加上该版本的说明，推送到 `main`。测试通过后，CI 会自动发布 Hugging Face Space 和 GitHub Release。测试说明见 [TESTING.md](TESTING.md)。

## 致谢与许可

- Open Home Foundation 的 [Linux Voice Assistant](https://github.com/OHF-Voice/linux-voice-assistant)
- Pollen Robotics 的 [Reachy Mini 对话应用](https://github.com/pollen-robotics/reachy_mini_conversation_app)

这是社区应用，不是 Pollen Robotics 官方出品。采用 Apache-2.0 许可，内置的第三方代码见 [THIRD_PARTY.md](THIRD_PARTY.md)。
