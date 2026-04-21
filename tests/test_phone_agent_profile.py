"""Tests for the standalone phone-agent profile loop."""

from __future__ import annotations

import asyncio
import base64
import os
from pathlib import Path
from typing import Any

import pytest

from nanobot.agent.loop import AgentLoop
from nanobot.agent.tools.base import Tool
from nanobot.agent.tools.phone_agent import PhoneAgentTool
from nanobot.bus.queue import MessageBus
from nanobot.config.loader import load_config
from nanobot.config.schema import PhoneAgentConfig
from nanobot.providers.base import LLMProvider, LLMResponse, ToolCallRequest


class _DummyMainProvider(LLMProvider):
    """Minimal main-agent provider stub for AgentLoop construction."""

    async def chat(
        self,
        messages,
        tools=None,
        model=None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        reasoning_effort=None,
        tool_choice=None,
    ) -> LLMResponse:
        return LLMResponse(content="unused", tool_calls=[])

    def get_default_model(self) -> str:
        """Return a stable default model name."""
        return "main/test-model"


class _FakePhoneProvider(LLMProvider):
    """Scripted multimodal provider used to validate the phone profile loop."""

    def __init__(self):
        super().__init__(api_key="EMPTY", api_base="http://localhost:8000/v1")
        self.calls: list[dict] = []

    async def chat(
        self,
        messages,
        tools=None,
        model=None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        reasoning_effort=None,
        tool_choice=None,
    ) -> LLMResponse:
        """
        Simulate a two-step phone-agent run.

        First request: validate auto-injected screenshot and ask for a phone action.
        Second request: validate the rebuilt round message still contains the original
        task plus the latest screenshot, then finish.
        """
        self.calls.append(
            {
                "messages": messages,
                "tools": tools,
                "model": model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "reasoning_effort": reasoning_effort,
            }
        )

        if len(self.calls) == 1:
            assert isinstance(messages[0]["content"], str)
            assert "手机子 Agent" in messages[0]["content"]
            assert messages[1]["role"] == "user"
            assert isinstance(messages[1]["content"], list)
            assert messages[1]["content"][0]["type"] == "text"
            assert "原始任务" in messages[1]["content"][0]["text"]
            assert messages[1]["content"][1]["type"] == "image_url"
            assert any(
                tool_def["function"]["name"] == "phone_tap"
                for tool_def in (tools or [])
            )
            return LLMResponse(
                content="先点击首页中的一个位置。",
                tool_calls=[
                    ToolCallRequest(
                        id="call_phone_tap",
                        name="phone_tap",
                        arguments={"x": 500, "y": 120},
                    )
                ],
            )

        round_user_message = messages[-1]
        assert round_user_message["role"] == "user"
        assert isinstance(round_user_message["content"], list)
        assert round_user_message["content"][0]["type"] == "text"
        assert "原始任务" in round_user_message["content"][0]["text"]
        assert "phone_tap" in round_user_message["content"][0]["text"]
        assert round_user_message["content"][1]["type"] == "image_url"
        assert round_user_message["content"][2]["type"] == "text"
        assert "当前应用" in round_user_message["content"][2]["text"]
        return LLMResponse(content="已确认界面状态，phone-agent 测试完成。", tool_calls=[])

    def get_default_model(self) -> str:
        """Return the phone-profile model name."""
        return "phone/test-model"


class _FakePhoneScreenshotTool(Tool):
    """Minimal phone screenshot tool that returns multimodal content blocks."""

    @property
    def name(self) -> str:
        return "phone_screenshot"

    @property
    def description(self) -> str:
        return "返回手机截图和当前应用信息。"

    @property
    def parameters(self) -> dict:
        return {"type": "object", "properties": {}}

    async def execute(self, **kwargs):
        """
        Return a deterministic multimodal screenshot result.

        Args:
            **kwargs: Unused tool arguments.

        Returns:
            A screenshot image block plus a text summary block.
        """
        del kwargs
        raw = base64.b64encode(b"\x89PNG\r\n\x1a\nfake-phone-agent").decode("utf-8")
        return [
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{raw}"},
            },
            {
                "type": "text",
                "text": "当前应用: 微信, 屏幕尺寸: 1080x2400",
            },
        ]


class _FakePhoneTapTool(Tool):
    """Minimal tap tool used to validate tool execution in the phone profile."""

    @property
    def name(self) -> str:
        return "phone_tap"

    @property
    def description(self) -> str:
        return "点击手机屏幕指定位置。"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "x": {"type": "integer"},
                "y": {"type": "integer"},
            },
            "required": ["x", "y"],
        }

    async def execute(self, x: int, y: int, **kwargs):
        """
        Return a deterministic tap result.

        Args:
            x: Relative X coordinate.
            y: Relative Y coordinate.
            **kwargs: Unused.

        Returns:
            A fake tap result string.
        """
        del kwargs
        return f"已点击相对坐标 ({x}, {y})。"


@pytest.mark.asyncio
async def test_phone_agent_profile_executes_with_multimodal_provider(monkeypatch, tmp_path: Path) -> None:
    """
    Verify the standalone phone-agent profile can run end-to-end.

    The test exercises:
    - `PhoneAgentTool` background spawning
    - `phone` profile registration
    - phone-specific system prompt injection
    - multimodal phone tool result delivery to the phone provider
    - async result announcement back to the bus

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary workspace path.
    """
    bus = MessageBus()
    phone_provider = _FakePhoneProvider()

    monkeypatch.setattr(AgentLoop, "_create_phone_provider", lambda self: phone_provider)
    monkeypatch.setattr(
        "nanobot.agent.tools.phone.build_phone_toolset",
        lambda config: [_FakePhoneScreenshotTool(), _FakePhoneTapTool()],
    )

    loop = AgentLoop(
        bus=bus,
        provider=_DummyMainProvider(),
        workspace=tmp_path,
        phone_config=PhoneAgentConfig(enable=True, use_tool_calling=True),
    )

    tool = loop.tools.get("phone_agent")
    assert isinstance(tool, PhoneAgentTool)

    start_message = await tool.execute(task="查看当前手机界面", label="phone smoke")
    assert "已启动手机后台任务" in start_message

    running_tasks = list(loop.subagents._running_tasks.values())
    assert len(running_tasks) == 1
    await asyncio.gather(*running_tasks)

    assert len(phone_provider.calls) == 2
    result = await bus.consume_inbound()
    assert result.channel == "system"
    assert result.sender_id == "subagent"
    assert "phone-agent 测试完成" in result.content


def _summarize_blocks(content: Any) -> str:
    """
    将消息或工具结果压缩成便于人工阅读的摘要。

    Args:
        content: 字符串或多模态内容块。

    Returns:
        简短摘要文本。
    """
    if isinstance(content, str):
        compact = content.replace("\n", " ").strip()
        return compact[:180] + ("..." if len(compact) > 180 else "")

    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if not isinstance(block, dict):
                parts.append(repr(block))
                continue
            block_type = block.get("type")
            if block_type == "text":
                text = str(block.get("text", "")).replace("\n", " ").strip()
                parts.append(f"text:{text[:80]}{'...' if len(text) > 80 else ''}")
            elif block_type == "image_url":
                url = block.get("image_url", {}).get("url", "")
                prefix = "data:image/" if url.startswith("data:image/") else "image"
                parts.append(f"{block_type}:{prefix}")
            else:
                parts.append(str(block_type))
        return " | ".join(parts)

    return repr(content)


class _TracingProvider(LLMProvider):
    """Wrap a real provider and print each phone-agent round."""

    def __init__(self, inner: LLMProvider):
        super().__init__(api_key=inner.api_key, api_base=inner.api_base)
        self._inner = inner
        self.generation = inner.generation
        self._round = 0

    async def chat(
        self,
        messages,
        tools=None,
        model=None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        reasoning_effort=None,
        tool_choice=None,
    ) -> LLMResponse:
        """
        打印 phone-agent 每一轮请求与响应摘要。

        Args:
            messages: 当前发送给模型的消息列表。
            tools: 当前可用工具定义。
            model: 当前使用的模型。
            max_tokens: 采样上限。
            temperature: 温度参数。
            reasoning_effort: 推理强度。
            tool_choice: 工具选择策略。

        Returns:
            实际 provider 的响应结果。
        """
        self._round += 1
        print(f"\n===== PHONE AGENT ROUND {self._round} =====")
        print(f"model: {model or self._inner.get_default_model()}")
        print(f"tools: {[tool['function']['name'] for tool in (tools or [])]}")
        print("last messages:")
        for msg in messages[-3:]:
            print(f"  - role={msg.get('role')}: {_summarize_blocks(msg.get('content'))}")

        response = await self._inner.chat(
            messages=messages,
            tools=tools,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            reasoning_effort=reasoning_effort,
            tool_choice=tool_choice,
        )

        print(f"assistant: {_summarize_blocks(response.content)}")
        if response.tool_calls:
            for tool_call in response.tool_calls:
                print(f"tool_call: {tool_call.name} args={tool_call.arguments}")
        return response

    def get_default_model(self) -> str:
        """Delegate default model lookup to the wrapped provider."""
        return self._inner.get_default_model()


class _TracingTool(Tool):
    """Wrap a real tool and print each invocation/result summary."""

    def __init__(self, inner: Tool):
        """
        初始化追踪包装器。

        Args:
            inner: 真实 tool 实例。
        """
        self._inner = inner

    @property
    def name(self) -> str:
        return self._inner.name

    @property
    def description(self) -> str:
        return self._inner.description

    @property
    def parameters(self) -> dict[str, Any]:
        return self._inner.parameters

    async def execute(self, **kwargs: Any) -> Any:
        """
        执行真实 tool，并打印入参与结果摘要。

        Args:
            **kwargs: 工具参数。

        Returns:
            真实 tool 的执行结果。
        """
        print(f"tool_execute: {self.name} kwargs={kwargs}")
        try:
            result = await self._inner.execute(**kwargs)
        except Exception as exc:
            print(f"tool_error: {self.name} -> {exc}")
            raise
        print(f"tool_result: {self.name} -> {_summarize_blocks(result)}")
        return result


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.getenv("NANOBOT_PHONE_AGENT_MANUAL") != "1",
    reason="set NANOBOT_PHONE_AGENT_MANUAL=1 to run the manual phone-agent trace",
)
async def test_phone_agent_manual_trace(monkeypatch) -> None:
    """
    手工追踪 phone-agent 的独立运行过程。

    这个测试不会做复杂断言，而是直接打印：
    - 每一轮发给多模态模型的消息摘要
    - 模型返回的 tool call / 文本结果
    - 每一次 phone tool 的执行参数与结果摘要
    - 最终回传给主会话的 system message

    运行方式示例：
        NANOBOT_PHONE_AGENT_MANUAL=1 \\
        NANOBOT_PHONE_AGENT_TASK="打开微信并查看当前首页" \\
        pytest -s tests/test_phone_agent_profile.py -k manual_trace
    """
    loaded = load_config()
    phone_config = loaded.tools.phone_agent.model_copy(deep=True)
    phone_config.enable = True

    if not phone_config.enable:
        raise RuntimeError("Phone agent config is disabled.")
    if not phone_config.use_tool_calling:
        raise RuntimeError("Manual phone-agent trace currently requires use_tool_calling=true.")

    task = os.getenv("NANOBOT_PHONE_AGENT_TASK", "打开微信并查看当前首页")
    bus = MessageBus()

    original_create_phone_provider = AgentLoop._create_phone_provider

    def _create_tracing_phone_provider(self: AgentLoop) -> LLMProvider:
        """Wrap the real phone provider with trace output."""
        return _TracingProvider(original_create_phone_provider(self))

    monkeypatch.setattr(AgentLoop, "_create_phone_provider", _create_tracing_phone_provider)

    from nanobot.agent.tools.phone import build_phone_toolset as real_build_phone_toolset

    monkeypatch.setattr(
        "nanobot.agent.tools.phone.build_phone_toolset",
        lambda config: [_TracingTool(tool) for tool in real_build_phone_toolset(config)],
    )

    loop = AgentLoop(
        bus=bus,
        provider=_DummyMainProvider(),
        workspace=loaded.workspace_path,
        phone_config=phone_config,
    )

    tool = loop.tools.get("phone_agent")
    assert isinstance(tool, PhoneAgentTool)

    print("\n===== PHONE AGENT MANUAL TRACE =====")
    print(f"workspace: {loaded.workspace_path}")
    print(f"task: {task}")
    print(f"model: {phone_config.model}")
    print(f"provider: {phone_config.provider}")
    print(f"device_type: {phone_config.device_type}")
    print(f"device_id: {phone_config.device_id or '(auto)'}")

    start_message = await tool.execute(task=task, label="manual phone trace")
    print(f"start_message: {start_message}")

    running_tasks = list(loop.subagents._running_tasks.values())
    if not running_tasks:
        raise RuntimeError("Phone-agent task was not spawned.")

    await asyncio.gather(*running_tasks)

    result = await asyncio.wait_for(bus.consume_inbound(), timeout=5.0)
    print("\n===== PHONE AGENT FINAL RESULT =====")
    print(result.content)
