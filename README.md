<div align="center">
  <h1>nanobot fork：PhoneAgent 与 Specialist Subagent 实验分支</h1>
  <p>
    <img src="https://img.shields.io/badge/python-≥3.11-blue" alt="Python">
    <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
    <a href="https://github.com/HKUDS/nanobot"><img src="https://img.shields.io/badge/upstream-HKUDS%2Fnanobot-lightgrey" alt="Upstream"></a>
  </p>
</div>

本项目基于开源项目 [HKUDS/nanobot](https://github.com/HKUDS/nanobot) 二次开发，继续沿用其轻量 agent、聊天通道、工具调用、provider 接入、长期记忆和后台任务能力，同时重点扩展 **PhoneAgent**、手机操作经验记忆，以及可演进为更多领域 specialist agent 的 **SubagentProfile** 架构。

如果说上游 nanobot 是一个超轻量个人 AI 助手基座，那么这个分支更关注一个问题：主 agent 如何把真实环境里的复杂任务，委托给一个有专用模型、专用工具、专用 prompt 和专用记忆的领域子 agent 来完成。

## 项目定位

这个 fork 当前聚焦三件事：

- **真实手机执行**：通过 `phone_agent` 工具把手机 GUI 操作委托给专用 phone subagent，在真实连接的 Android 设备上完成打开应用、点击、滑动、输入、返回、截图观察等多步任务。
- **经验可沉淀**：PhoneAgent 可以把成功的任务轨迹压缩成结构化经验，并在相似任务开始前检索复用，减少重复探索。
- **Specialist agent 架构**：`SubagentProfile` 把子 agent 的工具集、system prompt、模型、每轮观察、任务前准备和任务后收尾解耦。PhoneAgent 是第一个 specialist，后续可以扩展到浏览器、办公、数据分析、客服、设备运维等垂直领域。

## 与上游 nanobot 的关系

本仓库不是从零开始的新项目，而是基于上游 nanobot 的 fork。上游 nanobot 受 [OpenClaw](https://github.com/openclaw/openclaw) 启发，目标是用尽可能少的代码提供一个可运行、可读、可扩展的个人 AI assistant 框架。

本分支保留并继续受益于上游的基础能力：

- 多 provider LLM 接入，包括 OpenRouter、OpenAI、Anthropic、Gemini、DeepSeek、Ollama、自定义 OpenAI-compatible endpoint 等。
- 多聊天通道，包括 Telegram、Discord、WhatsApp、Feishu、DingTalk、Slack、Email、QQ、WeCom、Matrix 等。
- 文件、Shell、网页搜索、网页抓取、MCP、定时任务、Heartbeat、长期记忆和 session 管理。
- 小型、清晰的 Python 代码结构，适合快速实验和二次开发。

在此基础上，本分支新增或强化了手机执行、phone specialist profile、手机经验记忆、subagent profile 生命周期钩子等能力。许可仍为 MIT；发布、分发或二次开发时请保留原项目的版权与许可证声明。

## 新增能力概览

### PhoneAgent

`PhoneAgentTool` 是主 agent 暴露给用户的高层入口。当用户提出真实手机操作任务时，主 agent 会调用 `phone_agent`，由后台 phone subagent 继续执行，并在完成后把结果回传到原会话。

PhoneAgent 当前支持：

- 每轮自动截图，把最新屏幕状态作为多模态输入交给 phone profile。
- `phone_launch`、`phone_tap`、`phone_double_tap`、`phone_long_press`、`phone_swipe`、`phone_type`、`phone_back`、`phone_home`、`phone_wait` 等手机工具。
- 基于 ADB 的 Android 真机或模拟器操作，支持本地 `adb`、自定义 `platform-tools` 路径，以及仓库内置 platform-tools 探测。
- 独立的 phone provider、模型、temperature、max tokens、max steps 配置，使手机 GUI 任务可以使用更适合视觉和工具调用的模型。
- 遇到登录、验证码、权限、支付确认、设备异常或工具错误时，要求 phone subagent 明确报告真实阻塞点。

### Phone Experience Memory

PhoneAgent 的经验记忆是专门面向手机 GUI 任务的轻量结构化记忆系统。它会在任务开始前抽取任务签名，在任务结束后总结可复用经验，并根据用户后续反馈修正经验质量。

当前机制包括：

- 任务签名抽取：`task_intent`、`app_name`、`operation_mode`。
- 相似经验检索：基于 embedding 和 Chroma 存储检索历史成功经验。
- 执行轨迹总结：把最近工具调用、截图观察和最终结果压缩成可复用 guidance。
- 反馈窗口：用户在任务完成后的短期反馈可以用于强化或降低某条经验的可信度。

### SubagentProfile

`SubagentProfile` 是本分支后续扩展 specialist agent 的核心抽象。一个 profile 可以定义：

- 每次 spawn 时构建的专属工具集。
- 专属 system prompt。
- 专属 provider 和模型。
- 最大迭代次数和 loop 模式。
- 任务开始前的准备逻辑，例如抽取任务签名、检索经验。
- 每轮模型请求前的观察逻辑，例如自动截图。
- 自定义 round message 构建逻辑，例如把截图、最近动作、经验块合并进多模态输入。
- 任务结束后的收尾逻辑，例如经验总结和持久化。

PhoneAgent 只是第一个落地的 specialist。未来可以按同样模式扩展：

- `browser` profile：专门处理浏览器和网页自动化。
- `office` profile：专门处理文档、表格、PPT。
- `data` profile：专门处理数据分析、图表和报表。
- `support` profile：专门处理客服工单、知识库检索和标准作业流程。
- `ops` profile：专门处理服务巡检、日志分析和运维操作。

## 🏗️ 架构

本分支的关键路径可以理解为：

```text
User / Chat Channel
        |
        v
Main AgentLoop
        |
        | phone_agent(task)
        v
SubagentManager
        |
        | profile="phone"
        v
Phone SubagentProfile
        |
        | screenshot -> VLM reasoning -> phone tool call
        v
Android device via ADB
        |
        | finalize
        v
Phone Experience Memory
```

## 目录

- [项目定位](#项目定位)
- [与上游 nanobot 的关系](#与上游-nanobot-的关系)
- [新增能力概览](#新增能力概览)
- [架构](#️-架构)
- [安装](#-安装)
- [快速开始](#-快速开始)
- [PhoneAgent 配置](#phoneagent-配置)
- [聊天应用](#-聊天应用)
- [Agent 社交网络](#-agent-社交网络)
- [配置](#️-配置)
- [多实例](#-多实例)
- [CLI 参考](#-cli-参考)
- [Docker](#-docker)
- [Linux 服务](#-linux-服务)
- [项目结构](#-项目结构)
- [贡献与路线图](#-贡献与路线图)
- [许可证](#许可证)

## 📦 安装

**从源码安装**（推荐；包含本分支的 PhoneAgent 与 specialist profile 功能）

```bash
git clone https://github.com/brilliantfires/nanobot-fork.git
cd nanobot-fork
pip install -e .
```

如果你是在当前仓库中开发，也可以直接运行：

```bash
pip install -e .
```

**使用 [uv](https://github.com/astral-sh/uv) 安装**（稳定、快速）

```bash
uv tool install nanobot-ai
```

**从 PyPI 安装**（稳定版）

```bash
pip install nanobot-ai
```

> PyPI 上的 `nanobot-ai` 是上游发布包，可能不包含本 fork 中正在开发的 PhoneAgent、phone experience memory 和 specialist profile 扩展。要使用这些功能，请从本仓库源码安装。

### 升级到最新版本

**PyPI / pip**

```bash
pip install -U nanobot-ai
nanobot --version
```

**uv**

```bash
uv tool upgrade nanobot-ai
nanobot --version
```

**在使用 WhatsApp？** 升级后请重建本地 bridge：

```bash
rm -rf ~/.nanobot/bridge
nanobot channels login
```

## 🚀 快速开始

> [!TIP]
> 在 `~/.nanobot/config.json` 中设置你的 API key。
> 获取 API key: [OpenRouter](https://openrouter.ai/keys)（全球用户）
>
> 其他 LLM provider 请参见 [Providers](#providers) 一节。
>
> 网页搜索能力配置请参见 [Web Search](#web-search)。

**1. 初始化**

```bash
nanobot onboard
```

如果你想使用交互式初始化向导，可执行 `nanobot onboard --wizard`。

**2. 配置**（`~/.nanobot/config.json`）

在配置中完成这 **两部分** 即可（其他选项都有默认值）。

*设置 API key*（例如 OpenRouter，推荐全球用户）：

```json
{
  "providers": {
    "openrouter": {
      "apiKey": "sk-or-v1-xxx"
    }
  }
}
```

*设置模型*（也可以显式指定 provider，默认会自动检测）：

```json
{
  "agents": {
    "defaults": {
      "model": "anthropic/claude-opus-4-5",
      "provider": "openrouter"
    }
  }
}
```

**3. 聊天**

```bash
nanobot agent
```

就这些！2 分钟内即可拥有一个可工作的 AI 助手。

## PhoneAgent 配置

PhoneAgent 默认配置位于 `tools.phoneAgent`。如果你只想先使用普通聊天助手，可以把它关闭：

```json
{
  "tools": {
    "phoneAgent": {
      "enable": false
    }
  }
}
```

要启用真实手机操作，需要准备 Android 设备或模拟器，并确保 ADB 可用。最小配置示例：

```json
{
  "tools": {
    "phoneAgent": {
      "enable": true,
      "provider": "custom",
      "baseUrl": "https://api.siliconflow.cn/v1",
      "apiKey": "YOUR_PHONE_MODEL_API_KEY",
      "model": "Qwen/Qwen3.5-397B-A17B",
      "deviceType": "adb",
      "maxSteps": 50,
      "lang": "cn"
    }
  }
}
```

如果你的机器上没有全局 `adb`，可以指定路径：

```json
{
  "tools": {
    "phoneAgent": {
      "adbPath": "/absolute/path/to/adb",
      "platformToolsDir": "/absolute/path/to/platform-tools"
    }
  }
}
```

手机经验记忆默认关闭。开启后，PhoneAgent 会在成功任务结束后总结结构化经验，并在相似任务中检索复用：

```json
{
  "tools": {
    "phoneAgent": {
      "experienceMemory": {
        "enable": true,
        "embeddingModel": "text-embedding-3-small",
        "topK": 3,
        "minScore": 0.55
      }
    }
  }
}
```

典型使用方式：

```text
帮我打开微信，给张三发消息说我十分钟后到。
```

主 agent 会把这个请求委托给 `phone_agent`，phone subagent 会在后台持续观察手机截图、调用手机工具，并在完成或遇到真实阻塞时把结果回传到当前会话。

## 💬 聊天应用

把 nanobot 接到你喜欢的聊天平台上。如果你想自己做一个通道，请参考 [Channel Plugin Guide](./docs/CHANNEL_PLUGIN_GUIDE.md)。

> 通道插件支持已在 `main` 分支可用，但尚未发布到 PyPI。

| 通道               | 需要准备什么                       |
| ------------------ | ---------------------------------- |
| **Telegram** | 从 @BotFather 获取 Bot token       |
| **Discord**  | Bot token + Message Content intent |
| **WhatsApp** | 扫码绑定                           |
| **Feishu**   | App ID + App Secret                |
| **Mochat**   | Claw token（支持自动配置）         |
| **DingTalk** | App Key + App Secret               |
| **Slack**    | Bot token + App-Level token        |
| **Email**    | IMAP/SMTP 凭据                     |
| **QQ**       | App ID + App Secret                |
| **Wecom**    | Bot ID + Bot Secret                |

<details>
<summary><b>Telegram</b>（推荐）</summary>

**1. 创建 bot**

- 打开 Telegram，搜索 `@BotFather`
- 发送 `/newbot`，按提示操作
- 复制 token

**2. 配置**

```json
{
  "channels": {
    "telegram": {
      "enabled": true,
      "token": "YOUR_BOT_TOKEN",
      "allowFrom": ["YOUR_USER_ID"]
    }
  }
}
```

> 你可以在 Telegram 设置中找到自己的 **User ID**。它会显示为 `@yourUserId`。
> 复制时**不要带 `@` 符号**，然后把它填入配置文件。

**3. 运行**

```bash
nanobot gateway start
```

</details>

<details>
<summary><b>Mochat (Claw IM)</b></summary>

默认使用 **Socket.IO WebSocket**，并提供 HTTP polling 兜底。

**1. 让 nanobot 帮你配置 Mochat**

直接把下面这段消息发给 nanobot（将 `xxx@xxx` 替换为你的真实邮箱）：

```
Read https://raw.githubusercontent.com/HKUDS/MoChat/refs/heads/main/skills/nanobot/skill.md and register on MoChat. My Email account is xxx@xxx Bind me as your owner and DM me on MoChat.
```

nanobot 会自动完成注册、配置 `~/.nanobot/config.json`，并连接到 Mochat。

**2. 重启 gateway**

```bash
nanobot gateway start
```

就这样，剩下的都由 nanobot 自动处理。

<br>

<details>
<summary>手动配置（高级）</summary>

如果你更希望手动配置，请将以下内容加入 `~/.nanobot/config.json`：

> 请妥善保管 `claw_token`。它只应通过 `X-Claw-Token` 请求头发送到你的 Mochat API 端点。

```json
{
  "channels": {
    "mochat": {
      "enabled": true,
      "base_url": "https://mochat.io",
      "socket_url": "https://mochat.io",
      "socket_path": "/socket.io",
      "claw_token": "claw_xxx",
      "agent_user_id": "6982abcdef",
      "sessions": ["*"],
      "panels": ["*"],
      "reply_delay_mode": "non-mention",
      "reply_delay_ms": 120000
    }
  }
}
```

</details>

</details>

<details>
<summary><b>Discord</b></summary>

**1. 创建 bot**

- 前往 https://discord.com/developers/applications
- 创建应用 → Bot → Add Bot
- 复制 bot token

**2. 启用 intents**

- 在 Bot 设置中启用 **MESSAGE CONTENT INTENT**
- （可选）如果你计划基于成员信息使用 allow list，请启用 **SERVER MEMBERS INTENT**

**3. 获取你的 User ID**

- Discord Settings → Advanced → 启用 **Developer Mode**
- 右键你的头像 → **Copy User ID**

**4. 配置**

```json
{
  "channels": {
    "discord": {
      "enabled": true,
      "token": "YOUR_BOT_TOKEN",
      "allowFrom": ["YOUR_USER_ID"],
      "groupPolicy": "mention"
    }
  }
}
```

> `groupPolicy` 控制 bot 在群组频道中的响应方式：
>
> - `"mention"`（默认）— 仅在被 @ 提及时响应
> - `"open"` — 对所有消息都响应
>   只要发送者在 `allowFrom` 中，DM 总会响应。

**5. 邀请 bot**

- OAuth2 → URL Generator
- Scopes: `bot`
- Bot Permissions: `Send Messages`, `Read Message History`
- 打开生成的邀请链接，把 bot 加入你的服务器

**6. 运行**

```bash
nanobot gateway start
```

</details>

<details>
<summary><b>Matrix (Element)</b></summary>

先安装 Matrix 依赖：

```bash
pip install nanobot-ai[matrix]
```

**1. 创建 / 选择一个 Matrix 账号**

- 在你的 homeserver（例如 `matrix.org`）上创建或复用 Matrix 账号
- 确认你能用 Element 登录

**2. 获取凭据**

- 你需要：
  - `userId`（例如：`@nanobot:matrix.org`）
  - `accessToken`
  - `deviceId`（推荐，这样重启后可以恢复 sync token）
- 你可以通过 homeserver 的登录 API（`/_matrix/client/v3/login`）或客户端的高级会话设置获取这些信息。

**3. 配置**

```json
{
  "channels": {
    "matrix": {
      "enabled": true,
      "homeserver": "https://matrix.org",
      "userId": "@nanobot:matrix.org",
      "accessToken": "syt_xxx",
      "deviceId": "NANOBOT01",
      "e2eeEnabled": true,
      "allowFrom": ["@your_user:matrix.org"],
      "groupPolicy": "open",
      "groupAllowFrom": [],
      "allowRoomMentions": false,
      "maxMediaBytes": 20971520
    }
  }
}
```

> 请保持持久化的 `matrix-store` 和稳定的 `deviceId`，否则加密会话状态会在重启后丢失。

| 选项                  | 说明                                                                   |
| --------------------- | ---------------------------------------------------------------------- |
| `allowFrom`         | 允许交互的用户 ID。空数组表示拒绝所有人；用 `["*"]` 表示允许所有人。 |
| `groupPolicy`       | `open`（默认）、`mention` 或 `allowlist`。                       |
| `groupAllowFrom`    | 房间允许列表（当策略为 `allowlist` 时使用）。                        |
| `allowRoomMentions` | 在 mention 模式下是否接受 `@room`。                                  |
| `e2eeEnabled`       | 是否启用端到端加密，默认 `true`。设为 `false` 则仅明文。           |
| `maxMediaBytes`     | 附件大小上限（默认 `20MB`）。设为 `0` 则禁用所有媒体。             |

**4. 运行**

```bash
nanobot gateway start
```

</details>

<details>
<summary><b>WhatsApp</b></summary>

需要 **Node.js ≥18**。

**1. 绑定设备**

```bash
nanobot channels login
# 用 WhatsApp → 设置 → 已关联设备 扫码
```

**2. 配置**

```json
{
  "channels": {
    "whatsapp": {
      "enabled": true,
      "allowFrom": ["+1234567890"]
    }
  }
}
```

**3. 运行**（两个终端）

```bash
# 终端 1
nanobot channels login

# 终端 2
nanobot gateway start
```

> 已有安装不会自动应用 WhatsApp bridge 更新。
> 升级 nanobot 后，请执行以下命令重建本地 bridge：
> `rm -rf ~/.nanobot/bridge && nanobot channels login`

</details>

<details>
<summary><b>Feishu（飞书）</b></summary>

使用 **WebSocket 长连接**，不需要公网 IP。

**1. 创建飞书 bot**

- 访问 [Feishu Open Platform](https://open.feishu.cn/app)
- 创建新应用 → 启用 **Bot** 能力
- **Permissions**：添加 `im:message`（发消息）和 `im:message.p2p_msg:readonly`（收消息）
- **Events**：添加 `im.message.receive_v1`（收消息）
  - 选择 **Long Connection** 模式（需要先运行 nanobot 才能建立连接）
- 在 “Credentials & Basic Info” 中获取 **App ID** 和 **App Secret**
- 发布应用

**2. 配置**

```json
{
  "channels": {
    "feishu": {
      "enabled": true,
      "appId": "cli_xxx",
      "appSecret": "xxx",
      "encryptKey": "",
      "verificationToken": "",
      "allowFrom": ["ou_YOUR_OPEN_ID"],
      "groupPolicy": "mention"
    }
  }
}
```

> 在 Long Connection 模式下，`encryptKey` 和 `verificationToken` 是可选的。
> `allowFrom`：填入你的 open_id（你给 bot 发消息时，可在 nanobot 日志中看到）。使用 `["*"]` 可允许所有用户。
> `groupPolicy`：`"mention"`（默认，仅在被 @ 时回复）、`"open"`（回复所有群消息）。私聊始终会回复。

**3. 运行**

```bash
nanobot gateway start
```

> [!TIP]
> 飞书使用 WebSocket 接收消息，不需要 webhook 或公网 IP。

</details>

<details>
<summary><b>QQ（QQ 单聊）</b></summary>

使用 **botpy SDK** 配合 WebSocket，不需要公网 IP。目前仅支持 **私聊消息**。

**1. 注册并创建 bot**

- 访问 [QQ Open Platform](https://q.qq.com) → 注册开发者（个人或企业）
- 创建一个新的机器人应用
- 打开 **开发设置 (Developer Settings)** → 复制 **AppID** 和 **AppSecret**

**2. 为测试配置沙箱**

- 在机器人管理后台找到 **沙箱配置 (Sandbox Config)**
- 在 **在消息列表配置** 下点击 **添加成员**，加入你自己的 QQ 号
- 添加完成后，用手机 QQ 扫机器人的二维码 → 打开 bot 主页 → 点击“发消息”开始聊天

**3. 配置**

> - `allowFrom`：填入你的 openid（你给 bot 发消息时，可在 nanobot 日志中看到）。使用 `["*"]` 表示公开可用。
> - `msgFormat`：可选。`"plain"`（默认）对旧版 QQ 客户端兼容最好，`"markdown"` 在新版客户端上格式更丰富。
> - 生产环境中：请在 bot 控制台提交审核并发布。完整发布流程见 [QQ Bot Docs](https://bot.q.qq.com/wiki/)。

```json
{
  "channels": {
    "qq": {
      "enabled": true,
      "appId": "YOUR_APP_ID",
      "secret": "YOUR_APP_SECRET",
      "allowFrom": ["YOUR_OPENID"],
      "msgFormat": "plain"
    }
  }
}
```

**4. 运行**

```bash
nanobot gateway start
```

现在在 QQ 中给 bot 发消息，它就应该会回复。

</details>

<details>
<summary><b>DingTalk（钉钉）</b></summary>

使用 **Stream Mode**，不需要公网 IP。

**1. 创建钉钉机器人**

- 访问 [DingTalk Open Platform](https://open-dev.dingtalk.com/)
- 创建新应用 -> 添加 **Robot** 能力
- **Configuration**：
  - 打开 **Stream Mode**
- **Permissions**：添加发送消息所需权限
- 在 “Credentials” 中获取 **AppKey**（Client ID）和 **AppSecret**（Client Secret）
- 发布应用

**2. 配置**

```json
{
  "channels": {
    "dingtalk": {
      "enabled": true,
      "clientId": "YOUR_APP_KEY",
      "clientSecret": "YOUR_APP_SECRET",
      "allowFrom": ["YOUR_STAFF_ID"]
    }
  }
}
```

> `allowFrom`：填入你的 staff ID。使用 `["*"]` 可允许所有用户。

**3. 运行**

```bash
nanobot gateway start
```

</details>

<details>
<summary><b>Slack</b></summary>

使用 **Socket Mode**，不需要公网 URL。

**1. 创建 Slack 应用**

- 前往 [Slack API](https://api.slack.com/apps) → **Create New App** → "From scratch"
- 选择名称并绑定工作区

**2. 配置应用**

- **Socket Mode**：打开 → 生成带 `connections:write` scope 的 **App-Level Token** → 复制（`xapp-...`）
- **OAuth & Permissions**：添加 bot scopes：`chat:write`、`reactions:write`、`app_mentions:read`
- **Event Subscriptions**：打开 → 订阅 bot 事件：`message.im`、`message.channels`、`app_mention` → 保存
- **App Home**：滚动到 **Show Tabs** → 启用 **Messages Tab** → 勾选 **"Allow users to send Slash commands and messages from the messages tab"**
- **Install App**：点击 **Install to Workspace** → 授权 → 复制 **Bot Token**（`xoxb-...`）

**3. 配置 nanobot**

```json
{
  "channels": {
    "slack": {
      "enabled": true,
      "botToken": "xoxb-...",
      "appToken": "xapp-...",
      "allowFrom": ["YOUR_SLACK_USER_ID"],
      "groupPolicy": "mention"
    }
  }
}
```

**4. 运行**

```bash
nanobot gateway start
```

直接给 bot 发 DM，或在频道里 @ 它，它就应该会响应。

> [!TIP]
>
> - `groupPolicy`：`"mention"`（默认，仅在被 @ 时响应）、`"open"`（响应所有频道消息）或 `"allowlist"`（限制到指定频道）。
> - DM 默认是开放的。设置 `"dm": {"enabled": false}` 可禁用 DM。

</details>

<details>
<summary><b>Email</b></summary>

给 nanobot 一个专属邮箱账号。它会轮询 **IMAP** 收件箱，并通过 **SMTP** 回复，就像一个个人邮件助理。

**1. 获取凭据（以 Gmail 为例）**

- 为 bot 创建一个专用 Gmail 账号（例如 `my-nanobot@gmail.com`）
- 启用两步验证 → 创建一个 [App Password](https://myaccount.google.com/apppasswords)
- 将这个 app password 同时用于 IMAP 和 SMTP

**2. 配置**

> - `consentGranted` 必须为 `true` 才允许访问邮箱。这是一个安全开关；设为 `false` 即完全禁用。
> - `allowFrom`：填入你的邮箱地址。使用 `["*"]` 表示接收任意发件人的邮件。
> - `smtpUseTls` 和 `smtpUseSsl` 默认分别是 `true` / `false`，这正适用于 Gmail（587 + STARTTLS），无需显式设置。
> - 如果你只想读取 / 分析邮件而不自动回复，可设置 `"autoReplyEnabled": false`。

```json
{
  "channels": {
    "email": {
      "enabled": true,
      "consentGranted": true,
      "imapHost": "imap.gmail.com",
      "imapPort": 993,
      "imapUsername": "my-nanobot@gmail.com",
      "imapPassword": "your-app-password",
      "smtpHost": "smtp.gmail.com",
      "smtpPort": 587,
      "smtpUsername": "my-nanobot@gmail.com",
      "smtpPassword": "your-app-password",
      "fromAddress": "my-nanobot@gmail.com",
      "allowFrom": ["your-real-email@gmail.com"]
    }
  }
}
```

**3. 运行**

```bash
nanobot gateway start
```

</details>

<details>
<summary><b>Wecom（企业微信）</b></summary>

> 这里使用的是 [wecom-aibot-sdk-python](https://github.com/chengyongru/wecom_aibot_sdk)（官方 [@wecom/aibot-node-sdk](https://www.npmjs.com/package/@wecom/aibot-node-sdk) 的社区 Python 版本）。
>
> 使用 **WebSocket 长连接**，不需要公网 IP。

**1. 安装可选依赖**

```bash
pip install nanobot-ai[wecom]
```

**2. 创建企业微信 AI Bot**

进入企业微信管理后台 → 智能机器人 → 创建机器人 → 选择带 **长连接** 的 **API 模式**。复制 Bot ID 和 Secret。

**3. 配置**

```json
{
  "channels": {
    "wecom": {
      "enabled": true,
      "botId": "your_bot_id",
      "secret": "your_bot_secret",
      "allowFrom": ["your_id"]
    }
  }
}
```

**4. 运行**

```bash
nanobot gateway start
```

</details>

## 🌐 Agent 社交网络

🐈 nanobot 可以连接到 agent 社交网络（agent 社区）。**只需发一条消息，你的 nanobot 就会自动加入！**

| 平台                                         | 如何加入（把这条消息发给你的 bot）                                                   |
| -------------------------------------------- | ------------------------------------------------------------------------------------ |
| [**Moltbook**](https://www.moltbook.com/) | `Read https://moltbook.com/skill.md and follow the instructions to join Moltbook`  |
| [**ClawdChat**](https://clawdchat.ai/)    | `Read https://clawdchat.ai/skill.md and follow the instructions to join ClawdChat` |

只要把上面的命令发给你的 nanobot（通过 CLI 或任意聊天通道），它就会自动处理剩下的步骤。

## ⚙️ 配置

配置文件：`~/.nanobot/config.json`

### Providers

> [!TIP]
>
> - **Groq** 提供免费的 Whisper 语音转写。如果配置好了，Telegram 语音消息会自动转写。
> - **MiniMax Coding Plan**：nanobot 社区专属优惠链接：[海外](https://platform.minimax.io/subscribe/coding-plan?code=9txpdXw04g&source=link) · [中国大陆](https://platform.minimaxi.com/subscribe/token-plan?code=GILTJpMTqZ&source=link)
> - **MiniMax（中国大陆）**：如果你的 API key 来自 minimaxi.com，请在 minimax provider 配置中设置 `"apiBase": "https://api.minimaxi.com/v1"`。
> - **VolcEngine / BytePlus Coding Plan**：请使用专用 provider `volcengineCodingPlan` 或 `byteplusCodingPlan`，而不是按量计费的 `volcengine` / `byteplus`。
> - **Zhipu Coding Plan**：如果你使用的是智谱 coding plan，请在 zhipu provider 配置中设置 `"apiBase": "https://open.bigmodel.cn/api/coding/paas/v4"`。
> - **Alibaba Cloud BaiLian**：如果你使用的是阿里云百炼的 OpenAI 兼容端点，请在 dashscope provider 配置中设置 `"apiBase": "https://dashscope.aliyuncs.com/compatible-mode/v1"`。

| Provider           | 用途                                       | 获取 API Key                                                                                                                                                                                       |
| ------------------ | ------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `custom`         | 任意 OpenAI 兼容端点（直连，不经 LiteLLM） | —                                                                                                                                                                                                 |
| `openrouter`     | LLM（推荐，可访问全部模型）                | [openrouter.ai](https://openrouter.ai)                                                                                                                                                                |
| `volcengine`     | LLM（VolcEngine，按量计费）                | [Coding Plan](https://www.volcengine.com/activity/codingplan?utm_campaign=nanobot&utm_content=nanobot&utm_medium=devrel&utm_source=OWO&utm_term=nanobot) · [volcengine.com](https://www.volcengine.com) |
| `byteplus`       | LLM（VolcEngine 国际版，按量计费）         | [Coding Plan](https://www.byteplus.com/en/activity/codingplan?utm_campaign=nanobot&utm_content=nanobot&utm_medium=devrel&utm_source=OWO&utm_term=nanobot) · [byteplus.com](https://www.byteplus.com)    |
| `anthropic`      | LLM（Claude 直连）                         | [console.anthropic.com](https://console.anthropic.com)                                                                                                                                                |
| `azure_openai`   | LLM（Azure OpenAI）                        | [portal.azure.com](https://portal.azure.com)                                                                                                                                                          |
| `openai`         | LLM（GPT 直连）                            | [platform.openai.com](https://platform.openai.com)                                                                                                                                                    |
| `deepseek`       | LLM（DeepSeek 直连）                       | [platform.deepseek.com](https://platform.deepseek.com)                                                                                                                                                |
| `groq`           | LLM +**语音转写**（Whisper）         | [console.groq.com](https://console.groq.com)                                                                                                                                                          |
| `minimax`        | LLM（MiniMax 直连）                        | [platform.minimaxi.com](https://platform.minimaxi.com)                                                                                                                                                |
| `gemini`         | LLM（Gemini 直连）                         | [aistudio.google.com](https://aistudio.google.com)                                                                                                                                                    |
| `aihubmix`       | LLM（API 网关，可访问全部模型）            | [aihubmix.com](https://aihubmix.com)                                                                                                                                                                  |
| `siliconflow`    | LLM（SiliconFlow/硅基流动）                | [siliconflow.cn](https://siliconflow.cn)                                                                                                                                                              |
| `dashscope`      | LLM（Qwen）                                | [dashscope.console.aliyun.com](https://dashscope.console.aliyun.com)                                                                                                                                  |
| `moonshot`       | LLM（Moonshot/Kimi）                       | [platform.moonshot.cn](https://platform.moonshot.cn)                                                                                                                                                  |
| `zhipu`          | LLM（Zhipu GLM）                           | [open.bigmodel.cn](https://open.bigmodel.cn)                                                                                                                                                          |
| `ollama`         | LLM（本地，Ollama）                        | —                                                                                                                                                                                                 |
| `vllm`           | LLM（本地，任意 OpenAI 兼容服务）          | —                                                                                                                                                                                                 |
| `openai_codex`   | LLM（Codex，OAuth）                        | `nanobot provider login openai-codex`                                                                                                                                                            |
| `github_copilot` | LLM（GitHub Copilot，OAuth）               | `nanobot provider login github-copilot`                                                                                                                                                          |

<details>
<summary><b>OpenAI Codex（OAuth）</b></summary>

Codex 使用 OAuth 而不是 API key。需要 ChatGPT Plus 或 Pro 账号。
`config.json` 中不需要 `providers.openaiCodex` 配置块；`nanobot provider login` 会把 OAuth 会话存到配置文件之外。

**1. 登录：**

```bash
nanobot provider login openai-codex
```

**2. 设置模型**（合并到 `~/.nanobot/config.json`）：

```json
{
  "agents": {
    "defaults": {
      "model": "openai-codex/gpt-5.1-codex"
    }
  }
}
```

**3. 聊天：**

```bash
nanobot agent -m "Hello!"

# 在本地指定某个 workspace/config
nanobot agent -c ~/.nanobot-telegram/config.json -m "Hello!"

# 在该配置基础上临时覆盖 workspace
nanobot agent -c ~/.nanobot-telegram/config.json -w /tmp/nanobot-telegram-test -m "Hello!"
```

> Docker 用户：交互式 OAuth 登录请使用 `docker run -it`。

</details>

<details>
<summary><b>GitHub Copilot（OAuth）</b></summary>

GitHub Copilot 使用 OAuth 而不是 API key。需要一个已开通 [GitHub 计划](https://github.com/features/copilot/plans) 的账号。
`config.json` 中不需要 `providers.githubCopilot` 配置块；`nanobot provider login` 会把 OAuth 会话存到配置文件之外。

**1. 登录：**

```bash
nanobot provider login github-copilot
```

**2. 设置模型**（合并到 `~/.nanobot/config.json`）：

```json
{
  "agents": {
    "defaults": {
      "model": "github-copilot/gpt-4.1"
    }
  }
}
```

**3. 聊天：**

```bash
nanobot agent -m "Hello!"

# 在本地指定某个 workspace/config
nanobot agent -c ~/.nanobot-telegram/config.json -m "Hello!"

# 在该配置基础上临时覆盖 workspace
nanobot agent -c ~/.nanobot-telegram/config.json -w /tmp/nanobot-telegram-test -m "Hello!"
```

> Docker 用户：交互式 OAuth 登录请使用 `docker run -it`。

</details>

<details>
<summary><b>Custom Provider（任意 OpenAI 兼容 API）</b></summary>

可直接连接任意 OpenAI 兼容端点，例如 LM Studio、llama.cpp、Together AI、Fireworks、Azure OpenAI，或任何自托管服务。它会绕过 LiteLLM，模型名会原样透传。

```json
{
  "providers": {
    "custom": {
      "apiKey": "your-api-key",
      "apiBase": "https://api.your-provider.com/v1"
    }
  },
  "agents": {
    "defaults": {
      "model": "your-model-name"
    }
  }
}
```

> 对于不需要 key 的本地服务，请把 `apiKey` 设为任意非空字符串（例如 `"no-key"`）。

</details>

<details>
<summary><b>Ollama（本地）</b></summary>

先通过 Ollama 跑起本地模型，然后写入配置：

**1. 启动 Ollama**（示例）：

```bash
ollama run llama3.2
```

**2. 添加到配置**（局部配置，合并到 `~/.nanobot/config.json`）：

```json
{
  "providers": {
    "ollama": {
      "apiBase": "http://localhost:11434"
    }
  },
  "agents": {
    "defaults": {
      "provider": "ollama",
      "model": "llama3.2"
    }
  }
}
```

> 当 `providers.ollama.apiBase` 已配置时，`provider: "auto"` 也可工作，但显式设置 `"provider": "ollama"` 更清楚。

</details>

<details>
<summary><b>vLLM（本地 / OpenAI 兼容）</b></summary>

用 vLLM 或任意 OpenAI 兼容服务运行你的模型，然后加入配置：

**1. 启动服务**（示例）：

```bash
vllm serve meta-llama/Llama-3.1-8B-Instruct --port 8000
```

**2. 添加到配置**（局部配置，合并到 `~/.nanobot/config.json`）：

*Provider（本地场景下 key 可为任意非空字符串）：*

```json
{
  "providers": {
    "vllm": {
      "apiKey": "dummy",
      "apiBase": "http://localhost:8000/v1"
    }
  }
}
```

*模型：*

```json
{
  "agents": {
    "defaults": {
      "model": "meta-llama/Llama-3.1-8B-Instruct"
    }
  }
}
```

</details>

<details>
<summary><b>新增一个 Provider（开发者指南）</b></summary>

nanobot 使用 **Provider Registry**（`nanobot/providers/registry.py`）作为单一事实来源。
新增一个 provider 只需 **2 步**，不需要改任何 if-elif 链。

**步骤 1.** 在 `nanobot/providers/registry.py` 的 `PROVIDERS` 中添加一个 `ProviderSpec`：

```python
ProviderSpec(
    name="myprovider",                   # 配置字段名
    keywords=("myprovider", "mymodel"),  # 用于自动匹配模型名的关键字
    env_key="MYPROVIDER_API_KEY",        # LiteLLM 使用的环境变量
    display_name="My Provider",          # 在 `nanobot status` 中展示
    litellm_prefix="myprovider",         # 自动前缀：model → myprovider/model
    skip_prefixes=("myprovider/",),      # 不要重复添加前缀
)
```

**步骤 2.** 在 `nanobot/config/schema.py` 的 `ProvidersConfig` 中添加一个字段：

```python
class ProvidersConfig(BaseModel):
    ...
    myprovider: ProviderConfig = ProviderConfig()
```

就这样！环境变量、模型前缀补全、配置匹配和 `nanobot status` 展示都会自动生效。

**常见 `ProviderSpec` 选项：**

| 字段                       | 说明                                  | 示例                                       |
| -------------------------- | ------------------------------------- | ------------------------------------------ |
| `litellm_prefix`         | 为 LiteLLM 自动添加模型前缀           | `"dashscope"` → `dashscope/qwen-max`  |
| `skip_prefixes`          | 如果模型已以这些前缀开头，就不要再加  | `("dashscope/", "openrouter/")`          |
| `env_extras`             | 需要额外设置的环境变量                | `(("ZHIPUAI_API_KEY", "{api_key}"),)`    |
| `model_overrides`        | 按模型定制参数覆盖                    | `(("kimi-k2.5", {"temperature": 1.0}),)` |
| `is_gateway`             | 是否可路由任意模型（例如 OpenRouter） | `True`                                   |
| `detect_by_key_prefix`   | 通过 API key 前缀识别网关             | `"sk-or-"`                               |
| `detect_by_base_keyword` | 通过 API base URL 关键字识别网关      | `"openrouter"`                           |
| `strip_model_prefix`     | 重加前缀前先移除已有前缀              | `True`（AiHubMix 适用）                  |

</details>

### Web Search

> [!TIP]
> 使用 `tools.web` 中的 `proxy`，可让所有 Web 请求（搜索 + 抓取）都走代理：
>
> ```json
> { "tools": { "web": { "proxy": "http://127.0.0.1:7890" } } }
> ```

nanobot 支持多个网页搜索 provider。请在 `~/.nanobot/config.json` 的 `tools.web.search` 下配置。

| Provider          | 配置字段    | 环境变量兜底         | 免费                   |
| ----------------- | ----------- | -------------------- | ---------------------- |
| `brave`（默认） | `apiKey`  | `BRAVE_API_KEY`    | 否                     |
| `tavily`        | `apiKey`  | `TAVILY_API_KEY`   | 否                     |
| `jina`          | `apiKey`  | `JINA_API_KEY`     | 免费额度（10M tokens） |
| `searxng`       | `baseUrl` | `SEARXNG_BASE_URL` | 是（自托管）           |
| `duckduckgo`    | —          | —                   | 是                     |

缺少凭据时，nanobot 会自动回退到 DuckDuckGo。

**Brave**（默认）：

```json
{
  "tools": {
    "web": {
      "search": {
        "provider": "brave",
        "apiKey": "BSA..."
      }
    }
  }
}
```

**Tavily：**

```json
{
  "tools": {
    "web": {
      "search": {
        "provider": "tavily",
        "apiKey": "tvly-..."
      }
    }
  }
}
```

**Jina**（免费额度 10M tokens）：

```json
{
  "tools": {
    "web": {
      "search": {
        "provider": "jina",
        "apiKey": "jina_..."
      }
    }
  }
}
```

**SearXNG**（自托管，不需要 API key）：

```json
{
  "tools": {
    "web": {
      "search": {
        "provider": "searxng",
        "baseUrl": "https://searx.example"
      }
    }
  }
}
```

**DuckDuckGo**（零配置）：

```json
{
  "tools": {
    "web": {
      "search": {
        "provider": "duckduckgo"
      }
    }
  }
}
```

| 选项           | 类型    | 默认值      | 说明                                                                   |
| -------------- | ------- | ----------- | ---------------------------------------------------------------------- |
| `provider`   | string  | `"brave"` | 搜索后端：`brave`、`tavily`、`jina`、`searxng`、`duckduckgo` |
| `apiKey`     | string  | `""`      | Brave 或 Tavily 的 API key                                             |
| `baseUrl`    | string  | `""`      | SearXNG 的基础 URL                                                     |
| `maxResults` | integer | `5`       | 每次搜索返回结果数（1–10）                                            |

### MCP (Model Context Protocol)

> [!TIP]
> 配置格式兼容 Claude Desktop / Cursor。你可以直接从任意 MCP server 的 README 中复制配置。

nanobot 支持 [MCP](https://modelcontextprotocol.io/) ，可连接外部工具服务器，并把它们当作原生 agent 工具使用。

把 MCP servers 加入 `config.json`：

```json
{
  "tools": {
    "mcpServers": {
      "filesystem": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/dir"]
      },
      "my-remote-mcp": {
        "url": "https://example.com/mcp/",
        "headers": {
          "Authorization": "Bearer xxxxx"
        }
      }
    }
  }
}
```

支持两种传输方式：

| 模式            | 配置                          | 示例                                        |
| --------------- | ----------------------------- | ------------------------------------------- |
| **Stdio** | `command` + `args`        | 通过 `npx` / `uvx` 启动本地进程         |
| **HTTP**  | `url` + `headers`（可选） | 远端端点（`https://mcp.example.com/sse`） |

对于较慢的服务，可使用 `toolTimeout` 覆盖默认的单次调用 30 秒超时：

```json
{
  "tools": {
    "mcpServers": {
      "my-slow-server": {
        "url": "https://example.com/mcp/",
        "toolTimeout": 120
      }
    }
  }
}
```

用 `enabledTools` 只注册某个 MCP server 的部分工具：

```json
{
  "tools": {
    "mcpServers": {
      "filesystem": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/dir"],
        "enabledTools": ["read_file", "mcp_filesystem_write_file"]
      }
    }
  }
}
```

`enabledTools` 既可接受 MCP 原始工具名（如 `read_file`），也可接受包装后的 nanobot 工具名（如 `mcp_filesystem_write_file`）。

- 省略 `enabledTools`，或设为 `["*"]`，表示注册全部工具
- 设为 `[]` 表示一个工具都不注册
- 设为非空名称列表时，仅注册该子集

MCP 工具会在启动时自动发现并注册。LLM 可像使用内建工具一样直接使用它们，不需要额外配置。

### Security

> [!TIP]
> 对生产环境部署，请在配置中设置 `"restrictToWorkspace": true`，以沙箱化 agent。
> 在 `v0.1.4.post3` 及更早版本中，空 `allowFrom` 允许所有发送者。从 `v0.1.4.post4` 起，空 `allowFrom` 默认拒绝所有访问。若需允许所有发送者，请设 `"allowFrom": ["*"]`。

| 选项                          | 默认值                 | 说明                                                                                                                            |
| ----------------------------- | ---------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| `tools.restrictToWorkspace` | `false`              | 当为 `true` 时，将 **所有** agent 工具（shell、文件读写 / 编辑、列表）限制在 workspace 目录中，防止路径穿越和越界访问。 |
| `tools.exec.enable`         | `true`               | 当为 `false` 时，shell `exec` 工具将完全不注册。可用于彻底禁用 shell 命令执行。                                             |
| `tools.exec.pathAppend`     | `""`                 | 执行 shell 命令时附加到 `PATH` 的额外目录（例如让 `ufw` 可用的 `/usr/sbin`）。                                            |
| `channels.*.allowFrom`      | `[]`（默认拒绝所有） | 用户 ID 白名单。空数组表示拒绝所有人；使用 `["*"]` 允许所有人。                                                               |

## 🧩 多实例

你可以用不同的配置和运行数据同时启动多个 nanobot 实例。以 `--config` 为主入口；当你希望为某个实例初始化或更新保存的工作区时，可在 `onboard` 时额外传入 `--workspace`。

### 快速开始

如果你希望每个实例从一开始就拥有自己的独立工作区，请在初始化时同时传入 `--config` 和 `--workspace`。

**初始化实例：**

```bash
# 创建独立的实例配置与工作区
nanobot onboard --config ~/.nanobot-telegram/config.json --workspace ~/.nanobot-telegram/workspace
nanobot onboard --config ~/.nanobot-discord/config.json --workspace ~/.nanobot-discord/workspace
nanobot onboard --config ~/.nanobot-feishu/config.json --workspace ~/.nanobot-feishu/workspace
```

**配置每个实例：**

编辑 `~/.nanobot-telegram/config.json`、`~/.nanobot-discord/config.json` 等，写入不同的通道配置。你在 `onboard` 时传入的 workspace 会被保存为该实例的默认 workspace。

**运行实例：**

```bash
# 实例 A - Telegram bot
nanobot gateway start --config ~/.nanobot-telegram/config.json

# 实例 B - Discord bot
nanobot gateway start --config ~/.nanobot-discord/config.json

# 实例 C - 飞书 bot，自定义端口
nanobot gateway start --config ~/.nanobot-feishu/config.json --port 18792
```

### 路径解析

使用 `--config` 时，nanobot 会根据配置文件路径推导运行数据目录。workspace 仍默认来自 `agents.defaults.workspace`，除非你用 `--workspace` 显式覆盖。

要在本地对其中某个实例开启 CLI 会话：

```bash
nanobot agent -c ~/.nanobot-telegram/config.json -m "Hello from Telegram instance"
nanobot agent -c ~/.nanobot-discord/config.json -m "Hello from Discord instance"

# 可选：临时覆盖 workspace
nanobot agent -c ~/.nanobot-telegram/config.json -w /tmp/nanobot-telegram-test
```

> `nanobot agent` 会在本地基于选定的 workspace/config 启动一个 CLI agent。它不会附着到，也不会通过已经运行的 `nanobot gateway start` 后台进程做代理。

| 组件                       | 解析来源               | 示例                         |
| -------------------------- | ---------------------- | ---------------------------- |
| **Config**           | `--config` 路径      | `~/.nanobot-A/config.json` |
| **Workspace**        | `--workspace` 或配置 | `~/.nanobot-A/workspace/`  |
| **Cron Jobs**        | 配置目录               | `~/.nanobot-A/cron/`       |
| **Media / 运行状态** | 配置目录               | `~/.nanobot-A/media/`      |

### 工作方式

- `--config` 用于选择加载哪个配置文件
- 默认情况下，workspace 来自该配置中的 `agents.defaults.workspace`
- 如果传入 `--workspace`，它会覆盖配置文件中的 workspace

### 最小化配置方式

1. 将你的基础配置复制到新的实例目录。
2. 为该实例设置不同的 `agents.defaults.workspace`。
3. 使用 `--config` 启动该实例。

示例配置：

```json
{
  "agents": {
    "defaults": {
      "workspace": "~/.nanobot-telegram/workspace",
      "model": "anthropic/claude-sonnet-4-6"
    }
  },
  "channels": {
    "telegram": {
      "enabled": true,
      "token": "YOUR_TELEGRAM_BOT_TOKEN"
    }
  },
  "gateway": {
    "port": 18790
  }
}
```

启动独立实例：

```bash
nanobot gateway start --config ~/.nanobot-telegram/config.json
nanobot gateway start --config ~/.nanobot-discord/config.json
```

必要时可在单次运行中覆盖 workspace：

```bash
nanobot gateway start --config ~/.nanobot-telegram/config.json --workspace /tmp/nanobot-telegram-test
```

### 常见使用场景

- 为 Telegram、Discord、Feishu 等平台分别运行独立 bot
- 隔离测试环境与生产环境
- 为不同团队使用不同模型或 provider
- 用独立配置和运行数据服务多个租户

### 注意事项

- 如果多个实例同时运行，它们必须使用不同端口
- 如果你想隔离记忆、会话和技能，请为每个实例使用不同 workspace
- `--workspace` 会覆盖配置文件中定义的 workspace
- Cron 任务和运行期媒体 / 状态目录都来自配置目录

## 💻 CLI 参考

| 命令                                           | 说明                                      |
| ---------------------------------------------- | ----------------------------------------- |
| `nanobot onboard`                            | 在 `~/.nanobot/` 初始化配置与 workspace |
| `nanobot onboard --wizard`                   | 启动交互式初始化向导                      |
| `nanobot onboard -c <config> -w <workspace>` | 初始化或刷新指定实例的配置和 workspace    |
| `nanobot agent -m "..."`                     | 与 agent 聊天                             |
| `nanobot agent -w <workspace>`               | 针对指定 workspace 聊天                   |
| `nanobot agent -w <workspace> -c <config>`   | 针对指定 workspace/config 聊天            |
| `nanobot agent`                              | 交互式聊天模式                            |
| `nanobot agent --no-markdown`                | 以纯文本显示回复                          |
| `nanobot agent --logs`                       | 聊天时显示运行日志                        |
| `nanobot gateway start`                      | 在后台启动 gateway                        |
| `nanobot gateway stop`                       | 停止后台 gateway                          |
| `nanobot gateway status`                     | 查看后台 gateway 状态                     |
| `nanobot status`                             | 查看状态                                  |
| `nanobot provider login openai-codex`        | provider 的 OAuth 登录                    |
| `nanobot channels login`                     | 绑定 WhatsApp（扫码）                     |
| `nanobot channels status`                    | 查看通道状态                              |

交互模式退出方式：`exit`、`quit`、`/exit`、`/quit`、`:q` 或 `Ctrl+D`。

<details>
<summary><b>Heartbeat（周期任务）</b></summary>

gateway 每 30 分钟唤醒一次，并检查你 workspace 中的 `HEARTBEAT.md`（`~/.nanobot/workspace/HEARTBEAT.md`）。如果文件中有任务，agent 就会执行它们，并把结果发送到你最近一次活跃的聊天通道。

**设置方法：** 编辑 `~/.nanobot/workspace/HEARTBEAT.md`（执行 `nanobot onboard` 时会自动创建）：

```markdown
## Periodic Tasks

- [ ] Check weather forecast and send a summary
- [ ] Scan inbox for urgent emails
```

agent 也可以自己维护这个文件。你只要对它说“添加一个周期任务”，它就会帮你更新 `HEARTBEAT.md`。

> **注意：** gateway 必须处于运行状态（`nanobot gateway start`），并且你至少和 bot 聊过一次，这样它才知道把结果发到哪个通道。

</details>

## 🐳 Docker

> [!TIP]
> `-v ~/.nanobot:/root/.nanobot` 会把你的本地配置目录挂载进容器，因此配置和 workspace 能在容器重启后保留。

### Docker Compose

```bash
docker compose run --rm nanobot-cli onboard   # 首次初始化
vim ~/.nanobot/config.json                     # 添加 API key
docker compose up -d nanobot-gateway           # 启动 gateway
```

```bash
docker compose run --rm nanobot-cli agent -m "Hello!"   # 运行 CLI
docker compose logs -f nanobot-gateway                   # 查看日志
docker compose down                                      # 停止
```

### Docker

```bash
# 构建镜像
docker build -t nanobot .

# 初始化配置（仅首次需要）
docker run -v ~/.nanobot:/root/.nanobot --rm nanobot onboard

# 在宿主机上编辑配置并加入 API key
vim ~/.nanobot/config.json

# 运行 gateway（连接已启用通道，例如 Telegram/Discord/Mochat）
docker run -v ~/.nanobot:/root/.nanobot -p 18790:18790 nanobot gateway run

# 或执行单条命令
docker run -v ~/.nanobot:/root/.nanobot --rm nanobot agent -m "Hello!"
docker run -v ~/.nanobot:/root/.nanobot --rm nanobot status
```

## 🐧 Linux 服务

将 gateway 作为 systemd 用户服务运行，这样它可以自动启动并在故障时自动重启。

**1. 找到 nanobot 可执行文件路径：**

```bash
which nanobot   # 例如 /home/user/.local/bin/nanobot
```

**2. 在 `~/.config/systemd/user/nanobot-gateway.service` 创建 service 文件**（如有需要请替换 `ExecStart` 路径）：

```ini
[Unit]
Description=Nanobot Gateway
After=network.target

[Service]
Type=simple
ExecStart=%h/.local/bin/nanobot gateway run
Restart=always
RestartSec=10
NoNewPrivileges=yes
ProtectSystem=strict
ReadWritePaths=%h

[Install]
WantedBy=default.target
```

**3. 启用并启动：**

```bash
systemctl --user daemon-reload
systemctl --user enable --now nanobot-gateway
```

**常用操作：**

```bash
systemctl --user status nanobot-gateway        # 查看状态
systemctl --user restart nanobot-gateway       # 配置变更后重启
journalctl --user -u nanobot-gateway -f        # 持续跟踪日志
```

如果你修改了 `.service` 文件本身，请在重启前运行 `systemctl --user daemon-reload`。

> **注意：** 用户级服务只会在你登录期间运行。若希望登出后仍继续运行，请启用 lingering：
>
> ```bash
> loginctl enable-linger $USER
> ```

## 📁 项目结构

```
nanobot/
├── agent/                       # 核心 agent 逻辑
│   ├── loop.py                  # Agent 循环、工具注册、phone profile 注册
│   ├── context.py               # Prompt 构建器
│   ├── memory.py                # 通用长期记忆
│   ├── phone_experience.py      # PhoneAgent 结构化经验记忆
│   ├── phone_prompt.py          # PhoneAgent system prompt 与 round message
│   ├── subagent.py              # 后台子 agent 生命周期管理
│   ├── subagent_profiles.py     # Specialist profile 抽象
│   └── tools/
│       ├── phone_agent.py       # 主 agent 暴露的 phone_agent 高层入口
│       └── phone/               # ADB 手机工具集
├── templates/                   # System prompt 与记忆模板
├── skills/                      # 内建技能
├── channels/                    # 聊天通道集成
├── bus/                         # 消息路由
├── cron/                        # 定时任务
├── heartbeat/                   # 主动唤醒
├── providers/                   # LLM providers
├── session/                     # 会话管理
├── config/                      # 配置 schema 与加载
└── cli/                         # 命令入口
```

## 🤝 贡献与路线图

欢迎 PR。这个分支希望继续保持上游 nanobot 的轻量和可读，同时把 specialist agent 的扩展路径打磨清楚。

### 分支策略

| 分支        | 用途                             |
| ----------- | -------------------------------- |
| `main`    | 稳定发布 —— bug 修复和小改进   |
| `nightly` | 实验功能 —— 新功能和破坏性变更 |

### 当前路线图

- [ ] 完善 PhoneAgent 的 Android ADB 稳定性、输入法体验和设备诊断。
- [ ] 强化 phone experience memory 的去重、反馈更新和跨会话复用。
- [ ] 抽象更多 `SubagentProfile` 示例，让 specialist agent 可以按领域快速接入。
- [ ] 为 phone profile 增加更完整的端到端测试和真实设备 smoke test 指南。
- [ ] 梳理上游同步策略，明确哪些基础能力继续跟随 nanobot，哪些能力在本分支独立演进。

## 许可证

本项目基于 MIT 许可证开源，并基于上游 [HKUDS/nanobot](https://github.com/HKUDS/nanobot) 二次开发。使用、修改、分发本项目时，请遵守 MIT License，并保留上游项目及本项目的版权与许可证声明。

### 上游贡献者

<a href="https://github.com/HKUDS/nanobot/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=HKUDS/nanobot&max=100&columns=12&updated=20260210" alt="Contributors" />
</a>

## 上游 Star 历史

<div align="center">
  <a href="https://star-history.com/#HKUDS/nanobot&Date">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=HKUDS/nanobot&type=Date&theme=dark" />
      <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=HKUDS/nanobot&type=Date" />
      <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=HKUDS/nanobot&type=Date" style="border-radius: 15px; box-shadow: 0 0 30px rgba(0, 217, 255, 0.3);" />
    </picture>
  </a>
</div>

<p align="center">
  <em> 感谢访问 ✨ nanobot！</em><br><br>
  <img src="https://visitor-badge.laobi.icu/badge?page_id=HKUDS.nanobot&style=for-the-badge&color=00d4ff" alt="Views">
</p>

<p align="center">
  <sub>nanobot 仅用于教育、研究和技术交流</sub>
</p>
