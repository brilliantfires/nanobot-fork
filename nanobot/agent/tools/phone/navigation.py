"""Phone navigation tools."""

from __future__ import annotations

from typing import Any

from nanobot.agent.tools.phone.common import PhoneToolBase


class PhoneLaunchTool(PhoneToolBase):
    """Launch an app on the connected phone."""

    @property
    def name(self) -> str:
        return "phone_launch"

    @property
    def description(self) -> str:
        return "启动手机应用。参数为应用名称，例如 微信、美团、Settings。"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "app_name": {"type": "string", "minLength": 1},
            },
            "required": ["app_name"],
        }

    async def execute(self, app_name: str, **kwargs: Any) -> str:
        """
        Launch an app by name.

        Args:
            app_name: Human-readable app name supported by upstream mappings.

        Returns:
            Short human-readable execution result.
        """
        loop = self._loop()
        launched = await loop.run_in_executor(None, self._adapter.launch_app, app_name)
        if not launched:
            raise RuntimeError(f"Failed to launch app: {app_name}")
        return f"已启动应用：{app_name}。"


class PhoneBackTool(PhoneToolBase):
    """Navigate back on the phone."""

    @property
    def name(self) -> str:
        return "phone_back"

    @property
    def description(self) -> str:
        return "返回上一页。"

    @property
    def parameters(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    async def execute(self, **kwargs: Any) -> str:
        """
        Navigate back one step.

        Returns:
            Short human-readable execution result.
        """
        loop = self._loop()
        await loop.run_in_executor(None, self._adapter.back)
        return "已执行返回。"


class PhoneHomeTool(PhoneToolBase):
    """Return to the phone home screen."""

    @property
    def name(self) -> str:
        return "phone_home"

    @property
    def description(self) -> str:
        return "回到手机桌面。"

    @property
    def parameters(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    async def execute(self, **kwargs: Any) -> str:
        """
        Navigate to the home screen.

        Returns:
            Short human-readable execution result.
        """
        loop = self._loop()
        await loop.run_in_executor(None, self._adapter.home)
        return "已回到桌面。"
