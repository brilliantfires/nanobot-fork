"""Subagent profile definitions."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

from nanobot.agent.tools.base import Tool
from nanobot.providers.base import LLMProvider

if TYPE_CHECKING:
    from nanobot.agent.tools.registry import ToolRegistry


@dataclass
class SubagentToolEvent:
    """
    一次工具执行事件。

    Args:
        iteration: 发生在第几轮。
        tool_name: 工具名。
        arguments: 工具调用参数。
        result: 工具执行结果。
    """

    iteration: int
    tool_name: str
    arguments: dict[str, Any]
    result: Any


@dataclass
class SubagentRoundState:
    """
    子 agent 当前轮次的可重建状态。

    Args:
        original_task: 原始任务描述。
        iteration: 当前轮次，从 1 开始。
        tool_events: 已执行的工具事件列表。
        latest_observation: 当前轮次自动采集到的最新观察结果，例如手机截图。
        latest_assistant_content: 上一轮模型返回的文本内容，可为空。
        task_signature: 当前任务的轻量签名，例如任务意图、应用名、操作模式。
        retrieved_experience_block: 启动任务前检索到的经验块，可为空。
    """

    original_task: str
    iteration: int = 0
    tool_events: list[SubagentToolEvent] = field(default_factory=list)
    latest_observation: Any | None = None
    latest_assistant_content: str | None = None
    task_signature: dict[str, Any] | None = None
    retrieved_experience_block: str | None = None


@dataclass
class SubagentProfile:
    """
    定义一类子 agent 的运行配置。

    Args:
        name: Profile 名称，用于 ``spawn(profile=...)`` 分发。
        build_tools: 工具工厂函数。每次 spawn 都应返回新的 tool 实例列表。
        system_prompt: system prompt 字符串或动态构建函数。
        provider: 可选的专用 provider；为空时复用主 agent provider。
        model: 可选的专用模型；为空时使用 provider 默认模型。
        max_iterations: 子 agent 最大迭代次数。
        loop_mode: 子 agent loop 模式。当前仅正式支持 ``tool_calling``。
        prepare_round_state: 每轮构造消息前的状态准备器，可用于自动截图等观察动作。
        build_round_messages: 每轮消息构建器；为空时使用默认文本版任务重申模板。
        prepare_task_state: 任务开始前的状态准备器，可用于签名抽取、经验检索等。
        finalize_run_state: 任务结束后的收尾器，可用于经验总结、持久化等。
        allow_image_fallback: 遇到图片请求错误时，是否允许 provider 自动去图重试。
    """

    name: str
    build_tools: Callable[[], list[Tool]]
    system_prompt: str | Callable[[], str]
    provider: LLMProvider | None = None
    model: str | None = None
    max_iterations: int = 15
    loop_mode: Literal["tool_calling", "text_parsing"] = "tool_calling"
    prepare_round_state: Callable[
        [SubagentRoundState, "ToolRegistry"],
        Awaitable[None] | None,
    ] | None = None
    build_round_messages: Callable[
        [SubagentRoundState],
        Awaitable[list[dict[str, Any]]] | list[dict[str, Any]],
    ] | None = None
    prepare_task_state: Callable[
        [SubagentRoundState, str | None],
        Awaitable[None] | None,
    ] | None = None
    finalize_run_state: Callable[
        [SubagentRoundState, str | None, str, str | None],
        Awaitable[None] | None,
    ] | None = None
    allow_image_fallback: bool = True

    def build_prompt(self) -> str:
        """
        构建当前 profile 的 system prompt。

        Returns:
            可直接放入消息列表的 system prompt 文本。
        """
        if isinstance(self.system_prompt, str):
            return self.system_prompt
        return self.system_prompt()

    async def prepare_round(self, state: SubagentRoundState, tools: "ToolRegistry") -> None:
        """
        在每轮发起模型请求前准备状态。

        Args:
            state: 当前轮次状态。
            tools: 当前 profile 的工具注册表。
        """
        if self.prepare_round_state is None:
            return
        prepared = self.prepare_round_state(state, tools)
        if prepared is not None and hasattr(prepared, "__await__"):
            await prepared

    async def prepare_task(self, state: SubagentRoundState, session_key: str | None = None) -> None:
        """
        在子 agent 开始执行前准备任务级状态。

        Args:
            state: 当前任务状态。
            session_key: 来源会话键。
        """
        if self.prepare_task_state is None:
            return
        prepared = self.prepare_task_state(state, session_key)
        if prepared is not None and hasattr(prepared, "__await__"):
            await prepared

    async def finalize_run(
        self,
        state: SubagentRoundState,
        final_result: str | None,
        status: str,
        session_key: str | None = None,
    ) -> None:
        """
        在子 agent 完成后执行任务级收尾逻辑。

        Args:
            state: 当前任务状态。
            final_result: 最终文本结果。
            status: ``ok`` 或 ``error``。
            session_key: 来源会话键。
        """
        if self.finalize_run_state is None:
            return
        finalized = self.finalize_run_state(state, final_result, status, session_key)
        if finalized is not None and hasattr(finalized, "__await__"):
            await finalized

    async def build_messages_for_round(
        self,
        state: SubagentRoundState,
    ) -> list[dict[str, Any]] | None:
        """
        构建当前轮次的非 system 消息列表。

        Args:
            state: 当前轮次状态。

        Returns:
            profile 自定义的消息列表；若未提供构建器则返回 ``None``。
        """
        if self.build_round_messages is None:
            return None
        built = self.build_round_messages(state)
        if built is not None and hasattr(built, "__await__"):
            return await built
        return built
