# Open-XiaoAI HA Gateway

小爱音箱语音网关的 Home Assistant OS 加载项：自定义唤醒词唤醒音箱后，把语音经本地 ASR 转成文字交给 Home Assistant 的 Assist 对话，再把回复用 TTS 合成后推回小爱播放。

> ⚠️ **版本要求**：本加载项需要较新的 Supervisor（2026.x「apps」体系，支持对象数组配置项）。旧版 Supervisor 无法解析本配置，加载项不会出现在商店中，请先升级 HAOS / Supervisor。

## 特性

- **自定义唤醒词**：本地 KWS（sherpa-onnx）识别，不依赖小爱云端的唤醒词
- **多 Agent 路由**：每个唤醒词可路由到 HA 中不同的 conversation agent，对话上下文互相隔离
- **按 Agent 配置音色**：每个 agent 可绑定独立的豆包 TTS 音色 ID（支持声音复刻）
- **连续对话**：一次唤醒后支持多轮问答，静音超时自动退出
- **本地 VAD + Paraformer ASR**：离线中文识别，不依赖云端 ASR
- **轻量部署**：复用预构建的 amd64 + arm64 多架构镜像，HAOS 上安装即用，不在设备上编译

## 与 open-xiaoai-bridge 的关系

本项目基于开源项目 [open-xiaoai-bridge](https://github.com/xiaoayu-code/open-xiaoai-bridge) 简化改造而来：

| | 本项目 | open-xiaoai-bridge |
|---|---|---|
| 定位 | 小爱音箱 → HA Assist 的轻量语音网关 | 通用小爱音箱接入框架 |
| 依赖 | 仅 HA Assist 对话（LLM 由 conversation agent 提供）+ 豆包 TTS | OpenClaw / 龙虾 / skill 等外部组件 |
| 部署 | 一个 Docker 镜像 / HA 加载项 | 需要自行搭建多个服务 |
| 可扩展性 | 聚焦 HA 场景，改动小 | 更强，可接入任意 agent 框架 |

简化的意义：本项目把链路精简为「小爱音箱 → HA Assist 对话（conversation agent 可接入任意大模型）→ TTS 播放」，不需要部署 OpenClaw、skill 等额外组件，配置和排障都更简单；对话智能由 HA 中的 conversation agent 提供（如 extended OpenAI Conversation 接入的大模型），并非仅限家居控制。原项目的优势在于通用性和可扩展性，适合需要接入其他大模型/agent 框架的玩法。

## 架构

```text
小爱音箱
   │  语音流（WebSocket，端口 4399）
   ▼
open-xiaoai-ha-gateway（本加载项）
   │  1. 本地 KWS 检测自定义唤醒词
   │  2. 唤醒后本地 VAD 采集语音 → Paraformer ASR 转文字
   │  3. 按唤醒词路由到对应 conversation agent
   ▼
Home Assistant Assist（conversation.process，如 extended_openai_conversation）
   │  回复文字
   ▼
豆包 TTS（火山引擎语音合成/声音复刻）
   │  PCM 音频流
   ▼
小爱音箱播放
```

## 前置条件

1. Home Assistant 中已配置至少一个 conversation agent（如 extended OpenAI Conversation），并通过 Assist 暴露所需实体。
2. 模型文件：VAD + KWS + Paraformer（见「模型文件」；开启 `auto_download_models` 可自动下载）。
3. 音箱端已安装 open-xiaoai-client（见下文「音箱端 Client」）。

## 安装

Home Assistant → 设置 → 加载项 → 加载项商店 → 右上角 ⋮ →「仓库」→ 添加：

```text
https://github.com/jenihk/ha-addon-open-xiaoai
```

然后安装 **Open-XiaoAI HA Gateway** 并启动。

## 音箱端 Client（必装）

加载项只是服务端，还需要在**小爱音箱上安装客户端**（open-xiaoai-client）把麦克风音频流和原生识别结果转发过来。前提是音箱已刷机/取得 root。

简要步骤（完整教程见 [open-xiaoai-client/README.md](https://github.com/jenihk/open-xiaoai-ha-gateway/tree/main/open-xiaoai-client)）：

1. 刷机并 SSH 登录音箱（[刷机教程](https://github.com/idootop/open-xiaoai/blob/main/docs/flash.md)）。
2. 填写服务端地址（`<HA 设备 IP>` 换成加载项所在 HA 设备的 IP）：

   ```shell
   mkdir -p /data/open-xiaoai
   echo 'ws://<HA 设备 IP>:4399' > /data/open-xiaoai/server.txt
   ```

3. 安装并设置开机自启：

   ```shell
   curl -sSfL https://gitee.com/coderzc/open-xiaoai/raw/main/packages/client-rust/init.sh | sh
   curl -L -o /data/init.sh https://gitee.com/coderzc/open-xiaoai/raw/main/packages/client-rust/boot.sh
   reboot
   ```

重启后音箱自动连接加载项 `4399` 端口；默认不鉴权。

## 配置

### UI 配置（推荐）

加载项 → 配置，保存后重启即生效：

| 字段 | 必填 | 说明 |
|------|------|------|
| `use_ui_config` | 否 | UI 生成配置 / 手动编辑 config.py |
| `auto_download_models` | 否 | 模型缺失时自动下载（约 340MB） |
| `github_proxy` | 否 | GitHub 下载代理前缀，如 `https://ghfast.top/`；留空自动尝试常见代理 |
| `hf_endpoint` | 否 | Paraformer 下载源，默认 `https://hf-mirror.com` |
| `ha_base_url` | 否 | HA 地址，默认 `http://homeassistant:8123` |
| `ha_token` | 是 | HA Long-Lived Access Token（密码框显示） |
| `default_agent_id` | 否 | 默认 conversation agent（未匹配路由时使用） |
| `doubao_api_key` | 否 | 豆包 TTS API Key（密码框显示；不填则用 `xiaoai` 原生 TTS） |
| `default_tts_speaker` | 否 | 默认音色；填 `xiaoai` 用小爱原生 TTS |
| `asr_replacements` | 否 | ASR 纠错表，每行 `错误词:正确词`，自动纠正本地识别结果 |
| `wake_entries` | 是 | 唤醒词路由表，每行一条 |
| `api_server_enable` | 否 | HTTP API（端口 9092），默认关闭，仅外部脚本/调试需要时开启 |

#### 唤醒词路由表（wake_entries）

在 UI 中点击「添加」，每一条就是一组独立配置，包含三个输入框：

```text
唤醒词         conversation agent_id          音色 ID（可留空）
```

音色留空时使用 `default_tts_speaker`。示例：

| 唤醒词 | Agent ID | 音色 ID |
|--------|----------|---------|
| 海绵宝宝 | conversation.hai_mian_bao_bao | zh_male_liangsangmengzai_uranus_bigtts |
| 你好小薇 | conversation.ni_hao_xiao_wei | zh_female_vv_uranus_bigtts |

- 说「海绵宝宝」→ 进入 `conversation.hai_mian_bao_bao`，回复用男声音色
- 说「你好小薇」→ 进入 `conversation.ni_hao_xiao_wei`，回复用女声音色
- 未匹配到路由的唤醒词 → 使用 `default_agent_id` + `default_tts_speaker`

#### 音频/唤醒参数

以下字段直接显示在配置页，均为带取值范围的数字输入框：

| 字段 | 默认 | 范围 | 说明 |
|------|------|------|------|
| `kws_keywords_score` | 0.8 | 0.1–2.0 | 唤醒词置信度加成（越大越难触发） |
| `kws_keywords_threshold` | 0.08 | 0.01–1.0 | 唤醒词检测阈值（越小越灵敏） |
| `kws_vad_threshold` | 0.02 | 0.001–1.0 | 唤醒链路 VAD 阈值 |
| `kws_min_silence_duration` | 480 | 100–2000 | 唤醒检测最小静默时长（ms） |
| `vad_threshold` | 0.20 | 0.01–1.0 | 连续对话 VAD 阈值（越小越灵敏） |
| `vad_min_speech_duration` | 250 | 50–2000 | 最小语音时长（ms） |
| `vad_min_silence_duration` | 500 | 100–3000 | 最小静默时长（ms） |
| `audio_input_gain` | 5.0 | 0.5–20.0 | 唤醒链路增益（远场唤醒可调大） |
| `audio_input_conversation_gain` | 1.5 | 0.5–5.0 | 连续对话增益（建议不超过 2.5） |

#### ASR 纠错表（asr_replacements）

本地识别（Paraformer）偶尔会把家居设备名听错。大模型虽然有一定纠错能力，但识别错误率过高时同样无法理解指令——例如你说「关掉主卧和次卧空调」，被识别成「关掉关注我和次我空调」时，大模型就可能理解不了或执行错对象。

每行添加一条 `错误词:正确词`（纯文本子串替换，识别结果会被自动纠正）：

```text
次我:次卧
主我:主卧
```

注意：替换作用于整句，错误词应选择「几乎不会作为正常词出现」的写法，不要映射「关注我」这类正常词，避免误伤正常语句。

### 手动编辑 config.py（高级）

把 `use_ui_config` 关掉，直接编辑：

```text
/config/open-xiaoai-ha-gateway/config.py
```

> **唤醒词改动必须重启加载项**（KWS 启动时加载 keywords.txt）。

## 模型文件

```text
/config/open-xiaoai-ha-gateway/models/
```

放入 VAD + KWS 模型文件与 `sherpa-onnx-paraformer-zh-2024-03-09/` 目录。模型下载地址见应用仓库服务端 README：
https://github.com/jenihk/open-xiaoai-ha-gateway/blob/main/open-xiaoai-server/README.md

开启 `auto_download_models` 后首次启动会自动下载缺失模型：VAD + KWS 来自 open-xiaoai-bridge 的 GitHub release（自动尝试 `ghfast.top` / `gh-proxy.com` 等代理，也可在 `github_proxy` 指定），Paraformer 来自 hf-mirror（可在 `hf_endpoint` 换镜像）。若设备无法访问 GitHub，请关闭该选项并手动放置模型（文件清单见仓库根 README）。

## 网络

音箱端 `/data/open-xiaoai/server.txt` 填 `ws://<HA 设备 IP>:4399` 即可直连；HTTP API 在 HA 设备的 `9092` 端口。加载项访问 HA 使用内置别名 `http://homeassistant:8123`，同机部署无需修改。

## 常见问题

- **启动后循环重启** → 检查 `/config/open-xiaoai-ha-gateway/models` 是否放入了模型文件，以及配置是否有效。
- **音箱连不上** → 确认 HA 设备与音箱在同一局域网，`server.txt` 地址正确。
- **设备无法访问 GitHub** → 关闭 `auto_download_models`，手动上传模型文件。
- **唤醒词改了没生效** → 修改后必须重启加载项。
