# 通道插件指南

只需三步即可构建一个自定义 nanobot 通道：继承、打包、安装。

## 工作原理

nanobot 通过 Python 的 [entry points](https://packaging.python.org/en/latest/specifications/entry-points/) 发现通道插件。当你执行 `nanobot gateway start` 启动 gateway 时，会扫描：

1. `nanobot/channels/` 中的内建通道
2. 注册在 `nanobot.channels` entry point 组下的外部包

如果对应的配置段包含 `"enabled": true`，该通道就会被实例化并启动。

## 快速开始

我们来构建一个最小化的 webhook 通道：它通过 HTTP POST 接收消息，并把回复发回去。

### 项目结构

```
nanobot-channel-webhook/
├── nanobot_channel_webhook/
│   ├── __init__.py          # 重新导出 WebhookChannel
│   └── channel.py           # 通道实现
└── pyproject.toml
```

### 1. 创建你的通道

```python
# nanobot_channel_webhook/__init__.py
from nanobot_channel_webhook.channel import WebhookChannel

__all__ = ["WebhookChannel"]
```

```python
# nanobot_channel_webhook/channel.py
import asyncio
from typing import Any

from aiohttp import web
from loguru import logger

from nanobot.channels.base import BaseChannel
from nanobot.bus.events import OutboundMessage


class WebhookChannel(BaseChannel):
    name = "webhook"
    display_name = "Webhook"

    @classmethod
    def default_config(cls) -> dict[str, Any]:
        return {"enabled": False, "port": 9000, "allowFrom": []}

    async def start(self) -> None:
        """启动一个 HTTP 服务，监听传入消息。

        重要：start() 必须永久阻塞（或直到 stop() 被调用）。
        如果它返回了，通道会被视为已失效。
        """
        self._running = True
        port = self.config.get("port", 9000)

        app = web.Application()
        app.router.add_post("/message", self._on_request)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()
        logger.info("Webhook 监听于 :{}", port)

        # 一直阻塞，直到被停止
        while self._running:
            await asyncio.sleep(1)

        await runner.cleanup()

    async def stop(self) -> None:
        self._running = False

    async def send(self, msg: OutboundMessage) -> None:
        """投递一条外发消息。

        msg.content  — markdown 文本（按需转换为平台格式）
        msg.media    — 要附带的本地文件路径列表
        msg.chat_id  — 接收方（与你传给 _handle_message 的 chat_id 相同）
        msg.metadata — 可能包含 "_progress": True，用于流式输出片段
        """
        logger.info("[webhook] -> {}: {}", msg.chat_id, msg.content[:80])
        # 真实插件里可在这里 POST 到回调地址、调用 SDK 等。

    async def _on_request(self, request: web.Request) -> web.Response:
        """处理传入的 HTTP POST。"""
        body = await request.json()
        sender = body.get("sender", "unknown")
        chat_id = body.get("chat_id", sender)
        text = body.get("text", "")
        media = body.get("media", [])       # URL 列表

        # 这是关键调用：会校验 allowFrom，然后把消息放到
        # bus 中交给 agent 处理。
        await self._handle_message(
            sender_id=sender,
            chat_id=chat_id,
            content=text,
            media=media,
        )

        return web.json_response({"ok": True})
```

### 2. 注册 Entry Point

```toml
# pyproject.toml
[project]
name = "nanobot-channel-webhook"
version = "0.1.0"
dependencies = ["nanobot", "aiohttp"]

[project.entry-points."nanobot.channels"]
webhook = "nanobot_channel_webhook:WebhookChannel"

[build-system]
requires = ["setuptools"]
build-backend = "setuptools.backends._legacy:_Backend"
```

这里的键（`webhook`）会成为配置段名称，值则指向你的 `BaseChannel` 子类。

### 3. 安装并配置

```bash
pip install -e .
nanobot plugins list      # 验证 "Webhook" 显示为 "plugin"
nanobot onboard           # 为已检测到的插件自动添加默认配置
```

编辑 `~/.nanobot/config.json`：

```json
{
  "channels": {
    "webhook": {
      "enabled": true,
      "port": 9000,
      "allowFrom": ["*"]
    }
  }
}
```

### 4. 运行并测试

```bash
nanobot gateway start
```

在另一个终端中：

```bash
curl -X POST http://localhost:9000/message \
  -H "Content-Type: application/json" \
  -d '{"sender": "user1", "chat_id": "user1", "text": "Hello!"}'
```

agent 会收到消息并进行处理。回复会通过你的 `send()` 方法送出。

## BaseChannel API

### 必需项（抽象方法）

| 方法 | 说明 |
|--------|-------------|
| `async start()` | **必须永久阻塞。** 连接平台、监听消息，并在每条消息上调用 `_handle_message()`。如果该方法返回，说明通道已失效。 |
| `async stop()` | 设置 `self._running = False` 并清理资源。会在 gateway 关闭时调用。 |
| `async send(msg: OutboundMessage)` | 将外发消息投递到目标平台。 |

### Base 提供的能力

| 方法 / 属性 | 说明 |
|-------------------|-------------|
| `_handle_message(sender_id, chat_id, content, media?, metadata?, session_key?)` | **收到消息时调用它。** 会检查 `is_allowed()`，然后把消息发布到 bus。如果 `supports_streaming` 为真，也会自动设置 `_wants_stream`。 |
| `is_allowed(sender_id)` | 根据 `config["allowFrom"]` 检查是否允许；`"*"` 表示允许所有人，`[]` 表示拒绝所有人。 |
| `default_config()` (classmethod) | 返回 `nanobot onboard` 使用的默认配置字典。重写它以声明你的字段。 |
| `transcribe_audio(file_path)` | 通过 Groq Whisper 转写音频（若已配置）。 |
| `supports_streaming` (property) | 当配置中有 `"streaming": true` **且** 子类重写了 `send_delta()` 时返回 `True`。 |
| `is_running` | 返回 `self._running`。 |

### 可选项（流式输出）

| 方法 | 说明 |
|--------|-------------|
| `async send_delta(chat_id, delta, metadata?)` | 重写它以接收流式输出片段。详见 [流式支持](#流式支持)。 |

### 消息类型

```python
@dataclass
class OutboundMessage:
    channel: str        # 你的通道名称
    chat_id: str        # 接收方（与你传给 _handle_message 的值相同）
    content: str        # markdown 文本 —— 按需转换为平台格式
    media: list[str]    # 要附带的本地文件路径（图片、音频、文档）
    metadata: dict      # 可能包含："_progress"（bool，用于流式片段），
                        #              "message_id"（用于回复串联）
```

## 流式支持

通道可以选择支持实时流式输出，agent 会逐 token 发送内容，而不是只发一条最终消息。这完全是可选的；即便不支持流式，通道也能正常工作。

### 工作方式

当以下 **两个条件同时满足** 时，agent 会通过你的通道进行流式输出：

1. 配置中有 `"streaming": true`
2. 你的子类重写了 `send_delta()`

如果缺少任一条件，agent 会退回到常规的一次性 `send()` 路径。

### 实现 `send_delta`

重写 `send_delta` 来处理两类调用：

```python
async def send_delta(self, chat_id: str, delta: str, metadata: dict[str, Any] | None = None) -> None:
    meta = metadata or {}

    if meta.get("_stream_end"):
        # 流式输出结束 —— 在这里做最终格式化、清理等
        return

    # 常规增量 —— 追加文本，更新屏幕上的消息
    # delta 是一小段文本（几个 token）
```

**Metadata 标记：**

| 标记 | 含义 |
|------|---------|
| `_stream_delta: True` | 一段内容增量（delta 中是新增文本） |
| `_stream_end: True` | 流式输出完成（delta 为空） |
| `_resuming: True` | 后面还会继续来新的流式轮次（例如工具调用后继续回复） |

### 示例：带流式输出的 Webhook

```python
class WebhookChannel(BaseChannel):
    name = "webhook"
    display_name = "Webhook"

    def __init__(self, config, bus):
        super().__init__(config, bus)
        self._buffers: dict[str, str] = {}

    async def send_delta(self, chat_id: str, delta: str, metadata: dict[str, Any] | None = None) -> None:
        meta = metadata or {}
        if meta.get("_stream_end"):
            text = self._buffers.pop(chat_id, "")
            # 最终投递 —— 格式化并发送完整消息
            await self._deliver(chat_id, text, final=True)
            return

        self._buffers.setdefault(chat_id, "")
        self._buffers[chat_id] += delta
        # 增量更新 —— 把部分文本推送给客户端
        await self._deliver(chat_id, self._buffers[chat_id], final=False)

    async def send(self, msg: OutboundMessage) -> None:
        # 非流式路径 —— 保持不变
        await self._deliver(msg.chat_id, msg.content, final=True)
```

### 配置

按通道启用流式输出：

```json
{
  "channels": {
    "webhook": {
      "enabled": true,
      "streaming": true,
      "allowFrom": ["*"]
    }
  }
}
```

当 `streaming` 为 `false`（默认）或未设置时，只会调用 `send()`，不会有流式开销。

### BaseChannel 的流式 API

| 方法 / 属性 | 说明 |
|-------------------|-------------|
| `async send_delta(chat_id, delta, metadata?)` | 重写以处理流式输出片段。默认是 no-op。 |
| `supports_streaming` (property) | 当配置中有 `streaming: true` **且** 子类重写了 `send_delta` 时，返回 `True`。 |

## 配置

你的通道会收到普通的 `dict` 配置。用 `.get()` 访问字段：

```python
async def start(self) -> None:
    port = self.config.get("port", 9000)
    token = self.config.get("token", "")
```

`allowFrom` 会由 `_handle_message()` 自动处理，你不需要自己检查。

重写 `default_config()`，这样 `nanobot onboard` 会自动填充 `config.json`：

```python
@classmethod
def default_config(cls) -> dict[str, Any]:
    return {"enabled": False, "port": 9000, "allowFrom": []}
```

如果不重写，基类默认返回 `{"enabled": false}`。

## 命名约定

| 项目 | 格式 | 示例 |
|------|--------|---------|
| PyPI 包名 | `nanobot-channel-{name}` | `nanobot-channel-webhook` |
| Entry point 键 | `{name}` | `webhook` |
| 配置段 | `channels.{name}` | `channels.webhook` |
| Python 包名 | `nanobot_channel_{name}` | `nanobot_channel_webhook` |

## 本地开发

```bash
git clone https://github.com/you/nanobot-channel-webhook
cd nanobot-channel-webhook
pip install -e .
nanobot plugins list    # 应显示 "Webhook" 且来源为 "plugin"
nanobot gateway start   # 端到端测试
```

## 验证

```bash
$ nanobot plugins list

  Name       Source    Enabled
  telegram   builtin  yes
  discord    builtin  no
  webhook    plugin   yes
```
