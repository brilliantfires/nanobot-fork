"""High-level tool for spawning the phone subagent profile."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from nanobot.agent.tools.base import Tool

if TYPE_CHECKING:
    from nanobot.agent.subagent import SubagentManager


class PhoneAgentTool(Tool):
    """高层手机任务入口工具。"""

    def __init__(self, manager: "SubagentManager"):
        """
        初始化手机子 agent 工具。

        Args:
            manager: 负责生命周期管理和 profile 分发的 SubagentManager。
        """
        self._manager = manager
        self._origin_channel = "cli"
        self._origin_chat_id = "direct"
        self._session_key = "cli:direct"

    def set_context(self, channel: str, chat_id: str) -> None:
        """
        记录消息来源上下文，便于结果回传给正确会话。

        Args:
            channel: 来源 channel 名称。
            chat_id: 来源会话 ID。
        """
        self._origin_channel = channel
        self._origin_chat_id = chat_id
        self._session_key = f"{channel}:{chat_id}"

    @property
    def name(self) -> str:
        return "phone_agent"

    @property
    def description(self) -> str:
        return (
            "在真实连接的手机上执行多步 UI 操作任务。"
            "适用于打开应用、浏览界面、搜索内容、点击按钮、输入文字、切换页面等连续手机操作场景。"
            "典型任务包括：用微信发消息、用美团下单、用支付宝或淘宝完成页面操作、在地图或设置中查找并点击目标项。"
            "当用户请求真实手机操作时，应优先使用这个工具，而不是口头说明自己无法操作手机，也不要优先退回到通用 spawn。"
            "该工具会启动一个后台 phone-agent，任务完成后会自动把结果回传到当前会话。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "手机子 agent 需要完成的任务描述",
                    "minLength": 1,
                },
                "context": {
                    "type": ["string", "null"],
                    "description": "可选的补充上下文，例如账号状态、目标页面、约束条件等",
                },
                "label": {
                    "type": ["string", "null"],
                    "description": "可选的短标签，用于后台任务展示",
                },
            },
            "required": ["task"],
        }

    async def execute(
        self,
        task: str,
        context: str | None = None,
        label: str | None = None,
        **kwargs: Any,
    ) -> str:
        """
        启动 phone profile 的后台子任务。

        Args:
            task: 手机任务描述。
            context: 可选补充上下文。
            label: 可选短标签。
            **kwargs: 兼容工具调用接口的额外参数，当前忽略。

        Returns:
            后台任务启动结果描述。
        """
        del kwargs
        subagent_task = task.strip()
        if context:
            # 将附加上下文显式拼入任务文本，保持 SubagentManager 接口简洁。
            subagent_task = f"{subagent_task}\n\n补充上下文：\n{context.strip()}"

        await self._manager.spawn(
            task=subagent_task,
            label=label,
            origin_channel=self._origin_channel,
            origin_chat_id=self._origin_chat_id,
            session_key=self._session_key,
            profile="phone",
        )
        return "已启动手机后台任务。phone-agent 会继续执行，并在完成后自动回传结果到当前会话。"
