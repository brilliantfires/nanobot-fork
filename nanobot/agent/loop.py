"""Agent loop：核心处理引擎。"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import time
from contextlib import AsyncExitStack
from pathlib import Path
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from loguru import logger

from nanobot import __version__
from nanobot.agent.context import ContextBuilder
from nanobot.agent.memory import MemoryConsolidator
from nanobot.agent.phone_experience import PhoneExperienceManager
from nanobot.agent.phone_prompt import build_phone_round_messages, build_phone_system_prompt
from nanobot.agent.subagent import SubagentManager
from nanobot.agent.subagent_profiles import SubagentProfile
from nanobot.agent.tools.cron import CronTool
from nanobot.agent.skills import BUILTIN_SKILLS_DIR
from nanobot.agent.tools.filesystem import EditFileTool, ListDirTool, ReadFileTool, WriteFileTool
from nanobot.agent.tools.message import MessageTool
from nanobot.agent.tools.phone_agent import PhoneAgentTool
from nanobot.agent.tools.registry import ToolRegistry
from nanobot.agent.tools.shell import ExecTool
from nanobot.agent.tools.spawn import SpawnTool
from nanobot.agent.tools.web import WebFetchTool, WebSearchTool
from nanobot.bus.events import InboundMessage, OutboundMessage
from nanobot.utils.helpers import build_status_content
from nanobot.bus.queue import MessageBus
from nanobot.providers.base import LLMProvider
from nanobot.session.manager import Session, SessionManager

if TYPE_CHECKING:
    from nanobot.config.schema import ChannelsConfig, ExecToolConfig, PhoneAgentConfig, WebSearchConfig
    from nanobot.cron.service import CronService


class AgentLoop:
    """
    Agent loop 是系统的核心处理引擎。

    它负责：
    1. 从消息总线接收消息
    2. 基于历史、记忆、技能构建上下文
    3. 调用 LLM
    4. 执行工具调用
    5. 回传响应
    """

    _TOOL_RESULT_MAX_CHARS = 16_000

    def __init__(
        self,
        bus: MessageBus,
        provider: LLMProvider,
        workspace: Path,
        model: str | None = None,
        max_iterations: int = 40,
        context_window_tokens: int = 65_536,
        web_search_config: WebSearchConfig | None = None,
        web_proxy: str | None = None,
        exec_config: ExecToolConfig | None = None,
        phone_config: PhoneAgentConfig | None = None,
        cron_service: CronService | None = None,
        restrict_to_workspace: bool = False,
        session_manager: SessionManager | None = None,
        mcp_servers: dict | None = None,
        channels_config: ChannelsConfig | None = None,
    ):
        from nanobot.config.schema import ExecToolConfig, PhoneAgentConfig, WebSearchConfig

        self.bus = bus
        self.channels_config = channels_config
        self.provider = provider
        self.workspace = workspace
        self.model = model or provider.get_default_model()
        self.max_iterations = max_iterations
        self.context_window_tokens = context_window_tokens
        self.web_search_config = web_search_config or WebSearchConfig()
        self.web_proxy = web_proxy
        self.exec_config = exec_config or ExecToolConfig()
        self.phone_config = phone_config or PhoneAgentConfig()
        self.cron_service = cron_service
        self.restrict_to_workspace = restrict_to_workspace
        self._start_time = time.time()
        self._last_usage: dict[str, int] = {}

        self.context = ContextBuilder(
            workspace,
            capability_notes=self._build_runtime_capability_notes(),
        )
        self.sessions = session_manager or SessionManager(workspace)
        self.tools = ToolRegistry()
        self.subagents = SubagentManager(
            provider=provider,
            workspace=workspace,
            bus=bus,
            model=self.model,
            web_search_config=self.web_search_config,
            web_proxy=web_proxy,
            exec_config=self.exec_config,
            restrict_to_workspace=restrict_to_workspace,
        )
        self.phone_experiences: PhoneExperienceManager | None = None
        self._register_subagent_profiles()

        self._running = False
        self._mcp_servers = mcp_servers or {}
        self._mcp_stack: AsyncExitStack | None = None
        self._mcp_connected = False
        self._mcp_connecting = False
        self._active_tasks: dict[str, list[asyncio.Task]] = {}  # session_key -> tasks
        self._background_tasks: list[asyncio.Task] = []
        self._processing_lock = asyncio.Lock()
        self.memory_consolidator = MemoryConsolidator(
            workspace=workspace,
            provider=provider,
            model=self.model,
            sessions=self.sessions,
            context_window_tokens=context_window_tokens,
            build_messages=self.context.build_messages,
            get_tool_definitions=self.tools.get_definitions,
        )
        self._register_default_tools()

    def _build_runtime_capability_notes(self) -> list[str]:
        """
        构建当前主 agent 的运行时能力说明。

        Returns:
            会被注入到主 agent system prompt 的动态能力说明列表。
        """
        notes: list[str] = []
        if self.phone_config.enable:
            notes.append(
                "## 已连接的手机控制能力\n\n"
                "当前运行时通过 `phone_agent` 工具提供了可用的手机控制能力。\n"
                "当用户要求执行真实的手机界面操作时，你可以直接把任务委托给 `phone_agent`。\n"
                "典型场景包括打开 App、浏览页面、在美团下单、在微信发送消息、"
                "在 App 内搜索、填写输入框，以及执行多步骤的手机操作流程。\n\n"
                "如果 `phone_agent` 工具可用，不要声称自己无法操作手机。\n"
                "相反，应当使用 `phone_agent` 处理手机任务，并让专用的手机子 agent 去执行。\n"
                "如果任务后续遇到真正的阻塞，例如登录、验证、权限弹窗或支付确认，"
                "请把具体阻塞点清楚说明。"
            )
        return notes

    def _register_default_tools(self) -> None:
        """注册默认工具集。"""
        allowed_dir = self.workspace if self.restrict_to_workspace else None
        extra_read = [BUILTIN_SKILLS_DIR] if allowed_dir else None
        self.tools.register(ReadFileTool(workspace=self.workspace, allowed_dir=allowed_dir, extra_allowed_dirs=extra_read))
        for cls in (WriteFileTool, EditFileTool, ListDirTool):
            self.tools.register(cls(workspace=self.workspace, allowed_dir=allowed_dir))
        if self.exec_config.enable:
            self.tools.register(ExecTool(
                working_dir=str(self.workspace),
                timeout=self.exec_config.timeout,
                restrict_to_workspace=self.restrict_to_workspace,
                path_append=self.exec_config.path_append,
            ))
        self.tools.register(WebSearchTool(config=self.web_search_config, proxy=self.web_proxy))
        self.tools.register(WebFetchTool(proxy=self.web_proxy))
        self.tools.register(MessageTool(send_callback=self.bus.publish_outbound))
        self.tools.register(SpawnTool(manager=self.subagents))
        if self.phone_config.enable:
            self.tools.register(PhoneAgentTool(manager=self.subagents))
        if self.cron_service:
            self.tools.register(CronTool(self.cron_service))

    def _register_subagent_profiles(self) -> None:
        """
        注册当前 loop 需要的专用 subagent profiles。

        当前默认 profile 由 ``SubagentManager`` 内置注册。这里仅在启用手机能力时
        额外补充 ``phone`` profile。
        """
        if not self.phone_config.enable:
            return
        if not self.phone_config.use_tool_calling:
            raise RuntimeError(
                "当前手机子 agent 仅支持 tool-calling 模式。"
                "请设置 tools.phoneAgent.useToolCalling=true。"
            )

        from nanobot.agent.tools.phone import build_phone_toolset

        phone_provider = self._create_phone_provider()
        self.phone_experiences = PhoneExperienceManager(
            workspace=self.workspace,
            provider=phone_provider,
            model=self.phone_config.model,
            phone_api_key=self.phone_config.api_key,
            phone_base_url=self.phone_config.base_url,
            phone_extra_headers=self.phone_config.extra_headers,
            config=self.phone_config.experience_memory,
        )
        phone_prompt = build_phone_system_prompt(self.phone_config.lang)

        def _build_phone_tools() -> list:
            """
            为每次 phone subagent spawn 构建独立的手机工具实例。

            Returns:
                共享同一份运行时状态的 phone tools 列表。
            """
            phone_runtime_config = self.phone_config.model_copy(deep=True)
            phone_runtime_config.enable = True
            return build_phone_toolset(phone_runtime_config)

        async def _prepare_phone_round(state, tools) -> None:
            """
            在每轮 phone 子 agent 请求前自动采集最新截图。

            Args:
                state: 当前轮次状态。
                tools: phone profile 的工具注册表。
            """
            screenshot_tool = tools.get("phone_screenshot")
            if screenshot_tool is None:
                raise RuntimeError("phone profile 需要 `phone_screenshot` 来提供每轮观察结果。")
            state.latest_observation = await screenshot_tool.execute()

        async def _prepare_phone_task(state, session_key) -> None:
            if self.phone_experiences is None:
                return
            await self.phone_experiences.prepare_task(state, session_key)

        async def _finalize_phone_run(state, final_result, status, session_key) -> None:
            if self.phone_experiences is None:
                return
            await self.phone_experiences.finalize_task(state, final_result, status, session_key)

        self.subagents.register_profile(
            SubagentProfile(
                name="phone",
                build_tools=_build_phone_tools,
                system_prompt=phone_prompt,
                provider=phone_provider,
                model=self.phone_config.model,
                max_iterations=self.phone_config.max_steps,
                loop_mode="tool_calling",
                prepare_task_state=_prepare_phone_task,
                prepare_round_state=_prepare_phone_round,
                build_round_messages=lambda state: build_phone_round_messages(
                    state,
                    lang=self.phone_config.lang,
                ),
                finalize_run_state=_finalize_phone_run,
                allow_image_fallback=False,
            )
        )

    def _create_phone_provider(self) -> LLMProvider:
        """
        根据 ``PhoneAgentConfig`` 构建 phone profile 使用的独立 provider。

        Returns:
            供 phone subagent 独立使用的 LLM provider。

        Raises:
            RuntimeError: 当 provider 配置不完整或当前未支持时抛出。
        """
        from nanobot.providers.azure_openai_provider import AzureOpenAIProvider
        from nanobot.providers.base import GenerationSettings
        from nanobot.providers.custom_provider import CustomProvider
        from nanobot.providers.litellm_provider import LiteLLMProvider
        from nanobot.providers.registry import find_by_name

        provider_name = self.phone_config.provider

        if provider_name == "custom":
            provider: LLMProvider = CustomProvider(
                api_key=self.phone_config.api_key,
                api_base=self.phone_config.base_url,
                default_model=self.phone_config.model,
                extra_headers=self.phone_config.extra_headers,
            )
        elif provider_name == "azure_openai":
            try:
                provider = AzureOpenAIProvider(
                    api_key=self.phone_config.api_key,
                    api_base=self.phone_config.base_url,
                    default_model=self.phone_config.model,
                )
            except ValueError as exc:
                raise RuntimeError(f"无效的手机 Azure OpenAI 配置：{exc}") from exc
        else:
            spec = find_by_name(provider_name)
            if spec is None:
                raise RuntimeError(f"不支持的手机 provider：{provider_name}")
            if spec.is_oauth:
                raise RuntimeError(
                    f"当前配置流程不支持该手机 provider：{provider_name}。"
                    "基于 OAuth 的 provider 目前尚未接入 phone profile 的创建流程。"
                )
            provider = LiteLLMProvider(
                api_key=self.phone_config.api_key or None,
                api_base=self.phone_config.base_url or None,
                default_model=self.phone_config.model,
                extra_headers=self.phone_config.extra_headers,
                provider_name=provider_name,
            )

        provider.generation = GenerationSettings(
            temperature=self.phone_config.temperature,
            max_tokens=self.phone_config.max_tokens,
            reasoning_effort=self.phone_config.reasoning_effort,
        )
        return provider

    async def _connect_mcp(self) -> None:
        """懒加载连接已配置的 MCP 服务，只执行一次。"""
        if self._mcp_connected or self._mcp_connecting or not self._mcp_servers:
            return
        self._mcp_connecting = True
        from nanobot.agent.tools.mcp import connect_mcp_servers
        try:
            self._mcp_stack = AsyncExitStack()
            await self._mcp_stack.__aenter__()
            await connect_mcp_servers(self._mcp_servers, self.tools, self._mcp_stack)
            self._mcp_connected = True
        except BaseException as e:
            logger.error("连接 MCP 服务失败（下条消息会重试）：{}", e)
            if self._mcp_stack:
                try:
                    await self._mcp_stack.aclose()
                except Exception:
                    pass
                self._mcp_stack = None
        finally:
            self._mcp_connecting = False

    def _set_tool_context(self, channel: str, chat_id: str, message_id: str | None = None) -> None:
        """为所有需要路由信息的工具更新上下文。"""
        for name in ("message", "spawn", "cron", "phone_agent"):
            if tool := self.tools.get(name):
                if hasattr(tool, "set_context"):
                    tool.set_context(channel, chat_id, *([message_id] if name == "message" else []))

    @staticmethod
    def _strip_think(text: str | None) -> str | None:
        """移除部分模型在内容中嵌入的 <think>…</think> 块。"""
        if not text:
            return None
        from nanobot.utils.helpers import strip_think
        return strip_think(text) or None

    @staticmethod
    def _tool_hint(tool_calls: list) -> str:
        """将工具调用格式化为简短提示，例如 `web_search("query")`。"""
        def _fmt(tc):
            args = (tc.arguments[0] if isinstance(tc.arguments, list) else tc.arguments) or {}
            val = next(iter(args.values()), None) if isinstance(args, dict) else None
            if not isinstance(val, str):
                return tc.name
            return f'{tc.name}("{val[:40]}…")' if len(val) > 40 else f'{tc.name}("{val}")'
        return ", ".join(_fmt(tc) for tc in tool_calls)

    def _status_response(self, msg: InboundMessage, session: Session) -> OutboundMessage:
        """为当前会话构建状态响应消息。"""
        ctx_est = 0
        try:
            ctx_est, _ = self.memory_consolidator.estimate_session_prompt_tokens(session)
        except Exception:
            pass
        if ctx_est <= 0:
            ctx_est = self._last_usage.get("prompt_tokens", 0)
        return OutboundMessage(
            channel=msg.channel,
            chat_id=msg.chat_id,
            content=build_status_content(
                version=__version__, model=self.model,
                start_time=self._start_time, last_usage=self._last_usage,
                context_window_tokens=self.context_window_tokens,
                session_msg_count=len(session.get_history(max_messages=0)),
                context_tokens_estimate=ctx_est,
            ),
            metadata={"render_as": "text"},
        )

    async def _run_agent_loop(
        self,
        initial_messages: list[dict],
        on_progress: Callable[..., Awaitable[None]] | None = None,
        on_stream: Callable[[str], Awaitable[None]] | None = None,
        on_stream_end: Callable[..., Awaitable[None]] | None = None,
    ) -> tuple[str | None, list[str], list[dict]]:
        """运行 agent 的迭代循环。

        ``on_stream``：流式输出时，每收到一段内容增量就调用一次。
        ``on_stream_end(resuming)``：一次流式输出结束时调用。
        ``resuming=True`` 表示后面还有工具调用（界面上的加载状态应重新开始）；
        ``resuming=False`` 表示当前已经是最终回复。
        """
        messages = initial_messages
        iteration = 0
        final_content = None
        tools_used: list[str] = []

        # 给 on_stream 包一层带状态的 think 标签过滤器，
        # 确保下游消费者（CLI、各类通道）不会看到 <think> 块。
        _raw_stream = on_stream
        _stream_buf = ""

        async def _filtered_stream(delta: str) -> None:
            nonlocal _stream_buf
            from nanobot.utils.helpers import strip_think
            prev_clean = strip_think(_stream_buf)
            _stream_buf += delta
            new_clean = strip_think(_stream_buf)
            incremental = new_clean[len(prev_clean):]
            if incremental and _raw_stream:
                await _raw_stream(incremental)

        while iteration < self.max_iterations:
            iteration += 1

            tool_defs = self.tools.get_definitions()

            if on_stream:
                response = await self.provider.chat_stream_with_retry(
                    messages=messages,
                    tools=tool_defs,
                    model=self.model,
                    on_content_delta=_filtered_stream,
                )
            else:
                response = await self.provider.chat_with_retry(
                    messages=messages,
                    tools=tool_defs,
                    model=self.model,
                )

            usage = response.usage or {}
            self._last_usage = {
                "prompt_tokens": int(usage.get("prompt_tokens", 0) or 0),
                "completion_tokens": int(usage.get("completion_tokens", 0) or 0),
            }

            if response.has_tool_calls:
                if on_stream and on_stream_end:
                    await on_stream_end(resuming=True)
                    _stream_buf = ""

                if on_progress:
                    if not on_stream:
                        thought = self._strip_think(response.content)
                        if thought:
                            await on_progress(thought)
                    tool_hint = self._tool_hint(response.tool_calls)
                    tool_hint = self._strip_think(tool_hint)
                    await on_progress(tool_hint, tool_hint=True)

                tool_call_dicts = [
                    tc.to_openai_tool_call()
                    for tc in response.tool_calls
                ]
                messages = self.context.add_assistant_message(
                    messages, response.content, tool_call_dicts,
                    reasoning_content=response.reasoning_content,
                    thinking_blocks=response.thinking_blocks,
                )

                for tool_call in response.tool_calls:
                    tools_used.append(tool_call.name)
                    args_str = json.dumps(tool_call.arguments, ensure_ascii=False)
                    logger.info("Tool call: {}({})", tool_call.name, args_str[:200])
                    result = await self.tools.execute(tool_call.name, tool_call.arguments)
                    messages = self.context.add_tool_result(
                        messages, tool_call.id, tool_call.name, result
                    )
            else:
                if on_stream and on_stream_end:
                    await on_stream_end(resuming=False)
                    _stream_buf = ""

                clean = self._strip_think(response.content)
                if response.finish_reason == "error":
                    logger.error("LLM returned error: {}", (clean or "")[:200])
                    final_content = clean or "抱歉，调用 AI 模型时出现了错误。"
                    break
                messages = self.context.add_assistant_message(
                    messages, clean, reasoning_content=response.reasoning_content,
                    thinking_blocks=response.thinking_blocks,
                )
                final_content = clean
                break

        if final_content is None and iteration >= self.max_iterations:
            logger.warning("Max iterations ({}) reached", self.max_iterations)
            final_content = (
                f"我已经达到工具调用的最大迭代次数（{self.max_iterations}），"
                "但任务仍未完成。你可以尝试把任务拆成更小的步骤。"
            )

        return final_content, tools_used, messages

    async def run(self) -> None:
        """运行 agent loop，并将消息分发为任务，以保持对 `/stop` 的响应能力。"""
        self._running = True
        await self._connect_mcp()
        logger.info("Agent loop started")

        while self._running:
            try:
                msg = await asyncio.wait_for(self.bus.consume_inbound(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                # 保留真实的任务取消信号，确保关闭流程能正确完成。
                # 这里只忽略可能由外部集成泄漏出来的非任务级 CancelledError。
                if not self._running or asyncio.current_task().cancelling():
                    raise
                continue
            except Exception as e:
                logger.warning("消费入站消息时出错：{}，继续运行...", e)
                continue

            cmd = msg.content.strip().lower()
            if cmd == "/stop":
                await self._handle_stop(msg)
            elif cmd == "/restart":
                await self._handle_restart(msg)
            elif cmd == "/status":
                session = self.sessions.get_or_create(msg.session_key)
                await self.bus.publish_outbound(self._status_response(msg, session))
            else:
                task = asyncio.create_task(self._dispatch(msg))
                self._active_tasks.setdefault(msg.session_key, []).append(task)
                task.add_done_callback(lambda t, k=msg.session_key: self._active_tasks.get(k, []) and self._active_tasks[k].remove(t) if t in self._active_tasks.get(k, []) else None)

    async def _handle_stop(self, msg: InboundMessage) -> None:
        """取消当前会话下的所有活跃任务和子 agent。"""
        tasks = self._active_tasks.pop(msg.session_key, [])
        cancelled = sum(1 for t in tasks if not t.done() and t.cancel())
        for t in tasks:
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass
        sub_cancelled = await self.subagents.cancel_by_session(msg.session_key)
        total = cancelled + sub_cancelled
        content = f"已停止 {total} 个任务。" if total else "当前没有可停止的活跃任务。"
        await self.bus.publish_outbound(OutboundMessage(
            channel=msg.channel, chat_id=msg.chat_id, content=content,
        ))

    async def _handle_restart(self, msg: InboundMessage) -> None:
        """通过 `os.execv` 原地重启当前进程。"""
        await self.bus.publish_outbound(OutboundMessage(
            channel=msg.channel, chat_id=msg.chat_id, content="正在重启...",
        ))

        async def _do_restart():
            await asyncio.sleep(1)
            # 为了兼容 Windows，这里使用 -m nanobot，而不是 sys.argv[0]
            # （在 Windows 上，sys.argv[0] 可能只是 "nanobot"，没有完整路径）
            os.execv(sys.executable, [sys.executable, "-m", "nanobot"] + sys.argv[1:])

        asyncio.create_task(_do_restart())

    async def _dispatch(self, msg: InboundMessage) -> None:
        """在全局锁保护下处理一条消息。"""
        async with self._processing_lock:
            try:
                on_stream = on_stream_end = None
                if msg.metadata.get("_wants_stream"):
                    async def on_stream(delta: str) -> None:
                        await self.bus.publish_outbound(OutboundMessage(
                            channel=msg.channel, chat_id=msg.chat_id,
                            content=delta, metadata={"_stream_delta": True},
                        ))

                    async def on_stream_end(*, resuming: bool = False) -> None:
                        await self.bus.publish_outbound(OutboundMessage(
                            channel=msg.channel, chat_id=msg.chat_id,
                            content="", metadata={"_stream_end": True, "_resuming": resuming},
                        ))

                response = await self._process_message(
                    msg, on_stream=on_stream, on_stream_end=on_stream_end,
                )
                if response is not None:
                    await self.bus.publish_outbound(response)
                elif msg.channel == "cli":
                    await self.bus.publish_outbound(OutboundMessage(
                        channel=msg.channel, chat_id=msg.chat_id,
                        content="", metadata=msg.metadata or {},
                    ))
            except asyncio.CancelledError:
                logger.info("Task cancelled for session {}", msg.session_key)
                raise
            except Exception:
                logger.exception("Error processing message for session {}", msg.session_key)
                await self.bus.publish_outbound(OutboundMessage(
                    channel=msg.channel, chat_id=msg.chat_id,
                    content="抱歉，处理消息时出现了错误。",
                ))

    async def close_mcp(self) -> None:
        """先等待后台归档任务完成，再关闭 MCP 连接。"""
        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)
            self._background_tasks.clear()
        if self._mcp_stack:
            try:
                await self._mcp_stack.aclose()
            except (RuntimeError, BaseExceptionGroup):
                pass  # MCP SDK 在取消作用域清理时日志较吵，但通常无害
            self._mcp_stack = None

    def _schedule_background(self, coro) -> None:
        """将协程加入受跟踪的后台任务列表，并在关闭时统一等待完成。"""
        task = asyncio.create_task(coro)
        self._background_tasks.append(task)
        task.add_done_callback(self._background_tasks.remove)

    def stop(self) -> None:
        """停止 agent loop。"""
        self._running = False
        logger.info("Agent loop stopping")

    async def _process_message(
        self,
        msg: InboundMessage,
        session_key: str | None = None,
        on_progress: Callable[[str], Awaitable[None]] | None = None,
        on_stream: Callable[[str], Awaitable[None]] | None = None,
        on_stream_end: Callable[..., Awaitable[None]] | None = None,
    ) -> OutboundMessage | None:
        """处理单条入站消息，并返回响应。"""
        # system 消息：从 chat_id 中解析来源（格式为 "channel:chat_id"）
        if msg.channel == "system":
            channel, chat_id = (msg.chat_id.split(":", 1) if ":" in msg.chat_id
                                else ("cli", msg.chat_id))
            logger.info("Processing system message from {}", msg.sender_id)
            key = f"{channel}:{chat_id}"
            session = self.sessions.get_or_create(key)
            await self.memory_consolidator.maybe_consolidate_by_tokens(session)
            self._set_tool_context(channel, chat_id, msg.metadata.get("message_id"))
            history = session.get_history(max_messages=0)
            current_role = "assistant" if msg.sender_id == "subagent" else "user"
            messages = self.context.build_messages(
                history=history,
                current_message=msg.content, channel=channel, chat_id=chat_id,
                current_role=current_role,
            )
            final_content, _, all_msgs = await self._run_agent_loop(messages)
            self._save_turn(session, all_msgs, 1 + len(history))
            self.sessions.save(session)
            self._schedule_background(self.memory_consolidator.maybe_consolidate_by_tokens(session))
            return OutboundMessage(channel=channel, chat_id=chat_id,
                                  content=final_content or "后台任务已完成。")

        preview = msg.content[:80] + "..." if len(msg.content) > 80 else msg.content
        logger.info("Processing message from {}:{}: {}", msg.channel, msg.sender_id, preview)

        key = session_key or msg.session_key
        session = self.sessions.get_or_create(key)

        # 斜杠命令
        cmd = msg.content.strip().lower()
        if cmd == "/new":
            snapshot = session.messages[session.last_consolidated:]
            session.clear()
            self.sessions.save(session)
            self.sessions.invalidate(session.key)

            if snapshot:
                self._schedule_background(self.memory_consolidator.archive_messages(snapshot))

            return OutboundMessage(channel=msg.channel, chat_id=msg.chat_id,
                                  content="已开始新的会话。")
        if cmd == "/status":
            return self._status_response(msg, session)
        if cmd == "/help":
            lines = [
                "🐈 nanobot 命令：",
                "/new — 开启新会话",
                "/stop — 停止当前任务",
                "/restart — 重启机器人",
                "/status — 查看机器人状态",
                "/help — 查看可用命令",
            ]
            return OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content="\n".join(lines),
                metadata={"render_as": "text"},
            )
        if self.phone_experiences and self.phone_experiences.enabled and not cmd.startswith("/"):
            self.phone_experiences.observe_feedback(key, msg.content)
        await self.memory_consolidator.maybe_consolidate_by_tokens(session)

        self._set_tool_context(msg.channel, msg.chat_id, msg.metadata.get("message_id"))
        if message_tool := self.tools.get("message"):
            if isinstance(message_tool, MessageTool):
                message_tool.start_turn()

        history = session.get_history(max_messages=0)
        initial_messages = self.context.build_messages(
            history=history,
            current_message=msg.content,
            media=msg.media if msg.media else None,
            channel=msg.channel, chat_id=msg.chat_id,
        )

        async def _bus_progress(content: str, *, tool_hint: bool = False) -> None:
            meta = dict(msg.metadata or {})
            meta["_progress"] = True
            meta["_tool_hint"] = tool_hint
            await self.bus.publish_outbound(OutboundMessage(
                channel=msg.channel, chat_id=msg.chat_id, content=content, metadata=meta,
            ))

        final_content, _, all_msgs = await self._run_agent_loop(
            initial_messages,
            on_progress=on_progress or _bus_progress,
            on_stream=on_stream,
            on_stream_end=on_stream_end,
        )

        if final_content is None:
            final_content = "我已经完成处理，但当前没有可返回的内容。"

        self._save_turn(session, all_msgs, 1 + len(history))
        self.sessions.save(session)
        self._schedule_background(self.memory_consolidator.maybe_consolidate_by_tokens(session))

        if (mt := self.tools.get("message")) and isinstance(mt, MessageTool) and mt._sent_in_turn:
            return None

        preview = final_content[:120] + "..." if len(final_content) > 120 else final_content
        logger.info("Response to {}:{}: {}", msg.channel, msg.sender_id, preview)

        meta = dict(msg.metadata or {})
        if on_stream is not None:
            meta["_streamed"] = True
        return OutboundMessage(
            channel=msg.channel, chat_id=msg.chat_id, content=final_content,
            metadata=meta,
        )

    @staticmethod
    def _image_placeholder(block: dict[str, Any]) -> dict[str, str]:
        """将内联图片块转换为紧凑的文本占位符。"""
        path = (block.get("_meta") or {}).get("path", "")
        return {"type": "text", "text": f"[图片：{path}]" if path else "[图片]"}

    def _sanitize_persisted_blocks(
        self,
        content: list[dict[str, Any]],
        *,
        truncate_text: bool = False,
        drop_runtime: bool = False,
    ) -> list[dict[str, Any]]:
        """在写入会话历史前移除易变的多模态负载。"""
        filtered: list[dict[str, Any]] = []
        for block in content:
            if not isinstance(block, dict):
                filtered.append(block)
                continue

            if (
                drop_runtime
                and block.get("type") == "text"
                and isinstance(block.get("text"), str)
                and block["text"].startswith(ContextBuilder._RUNTIME_CONTEXT_TAG)
            ):
                continue

            if (
                block.get("type") == "image_url"
                and block.get("image_url", {}).get("url", "").startswith("data:image/")
            ):
                filtered.append(self._image_placeholder(block))
                continue

            if block.get("type") == "text" and isinstance(block.get("text"), str):
                text = block["text"]
                if truncate_text and len(text) > self._TOOL_RESULT_MAX_CHARS:
                    text = text[:self._TOOL_RESULT_MAX_CHARS] + "\n...（已截断）"
                filtered.append({**block, "text": text})
                continue

            filtered.append(block)

        return filtered

    def _save_turn(self, session: Session, messages: list[dict], skip: int) -> None:
        """将本轮新增消息保存到会话中，并截断过大的工具结果。"""
        from datetime import datetime
        for m in messages[skip:]:
            entry = dict(m)
            role, content = entry.get("role"), entry.get("content")
            if role == "assistant" and not content and not entry.get("tool_calls"):
                continue  # 跳过空 assistant 消息，避免污染会话上下文
            if role == "tool":
                if isinstance(content, str) and len(content) > self._TOOL_RESULT_MAX_CHARS:
                    entry["content"] = content[:self._TOOL_RESULT_MAX_CHARS] + "\n...（已截断）"
                elif isinstance(content, list):
                    filtered = self._sanitize_persisted_blocks(content, truncate_text=True)
                    if not filtered:
                        continue
                    entry["content"] = filtered
            elif role == "user":
                if isinstance(content, str) and content.startswith(ContextBuilder._RUNTIME_CONTEXT_TAG):
                    # 去掉运行时上下文前缀，仅保留用户原始文本。
                    parts = content.split("\n\n", 1)
                    if len(parts) > 1 and parts[1].strip():
                        entry["content"] = parts[1]
                    else:
                        continue
                if isinstance(content, list):
                    filtered = self._sanitize_persisted_blocks(content, drop_runtime=True)
                    if not filtered:
                        continue
                    entry["content"] = filtered
            entry.setdefault("timestamp", datetime.now().isoformat())
            session.messages.append(entry)
        session.updated_at = datetime.now()

    async def process_direct(
        self,
        content: str,
        session_key: str = "cli:direct",
        channel: str = "cli",
        chat_id: str = "direct",
        on_progress: Callable[[str], Awaitable[None]] | None = None,
        on_stream: Callable[[str], Awaitable[None]] | None = None,
        on_stream_end: Callable[..., Awaitable[None]] | None = None,
    ) -> OutboundMessage | None:
        """直接处理一条消息，并返回出站负载。"""
        await self._connect_mcp()
        msg = InboundMessage(channel=channel, sender_id="user", chat_id=chat_id, content=content)
        return await self._process_message(
            msg, session_key=session_key, on_progress=on_progress,
            on_stream=on_stream, on_stream_end=on_stream_end,
        )
