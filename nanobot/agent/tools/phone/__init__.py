"""Phone tool package."""

from nanobot.agent.tools.base import Tool
from nanobot.agent.tools.phone.actions import (
    PhoneDoubleTapTool,
    PhoneLongPressTool,
    PhoneSwipeTool,
    PhoneTapTool,
    PhoneTypeTool,
    PhoneWaitTool,
)
from nanobot.agent.tools.phone.common import PhoneRuntimeState
from nanobot.agent.tools.phone.navigation import (
    PhoneBackTool,
    PhoneHomeTool,
    PhoneLaunchTool,
)
from nanobot.agent.tools.phone.screenshot import PhoneScreenshotTool
from nanobot.config.schema import PhoneAgentConfig


def build_phone_toolset(config: PhoneAgentConfig) -> list[Tool]:
    """
    构建一组共享运行时状态的手机工具。

    Args:
        config: 手机能力配置。

    Returns:
        可直接注册到 ``ToolRegistry`` 的手机工具列表。
    """
    state = PhoneRuntimeState()
    return [
        PhoneScreenshotTool(config, state),
        PhoneTapTool(config, state),
        PhoneDoubleTapTool(config, state),
        PhoneLongPressTool(config, state),
        PhoneSwipeTool(config, state),
        PhoneTypeTool(config, state),
        PhoneWaitTool(config, state),
        PhoneLaunchTool(config, state),
        PhoneBackTool(config, state),
        PhoneHomeTool(config, state),
    ]

__all__ = [
    "build_phone_toolset",
    "PhoneBackTool",
    "PhoneDoubleTapTool",
    "PhoneHomeTool",
    "PhoneLaunchTool",
    "PhoneLongPressTool",
    "PhoneRuntimeState",
    "PhoneScreenshotTool",
    "PhoneSwipeTool",
    "PhoneTapTool",
    "PhoneTypeTool",
    "PhoneWaitTool",
]
