"""Phone screenshot tool."""

from __future__ import annotations

from typing import Any

from nanobot.utils.helpers import build_image_content_blocks

from nanobot.agent.tools.phone.common import PhoneToolBase


class PhoneScreenshotTool(PhoneToolBase):
    """Capture the current phone screen and return multimodal content blocks."""

    @property
    def name(self) -> str:
        return "phone_screenshot"

    @property
    def description(self) -> str:
        return "截取手机当前屏幕并返回截图、当前应用和屏幕尺寸信息。"

    @property
    def parameters(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    async def execute(self, **kwargs: Any) -> list[dict[str, Any]]:
        """
        Capture the current screen state.

        Returns:
            Multimodal content blocks containing the screenshot and screen summary.
        """
        loop = self._loop()

        # 先截图，再读取当前应用，确保后续坐标工具使用的是最新屏幕尺寸。
        screenshot = await loop.run_in_executor(None, self._adapter.get_screenshot)
        current_app = await loop.run_in_executor(None, self._adapter.get_current_app)
        raw, mime = self._adapter.decode_screenshot(screenshot)

        sensitive_flag = "，疑似敏感页面" if getattr(screenshot, "is_sensitive", False) else ""
        label = (
            f"当前应用: {current_app}，屏幕尺寸: "
            f"{screenshot.width}x{screenshot.height}{sensitive_flag}"
        )
        return build_image_content_blocks(raw, mime, "phone://current-screen", label)
