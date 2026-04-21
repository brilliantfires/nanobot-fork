"""Phone action tools for direct screen interaction."""

from __future__ import annotations

import time
from typing import Any

from nanobot.agent.tools.phone.common import PhoneToolBase


class PhoneTapTool(PhoneToolBase):
    """Tap a relative screen coordinate."""

    @property
    def name(self) -> str:
        return "phone_tap"

    @property
    def description(self) -> str:
        return "点击手机屏幕指定位置。坐标范围为 0-999。"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "x": {"type": "integer", "minimum": 0, "maximum": 999},
                "y": {"type": "integer", "minimum": 0, "maximum": 999},
            },
            "required": ["x", "y"],
        }

    async def execute(self, x: int, y: int, **kwargs: Any) -> str:
        """
        Tap a relative coordinate on the active phone screen.

        Args:
            x: Relative X coordinate in the range 0-999.
            y: Relative Y coordinate in the range 0-999.

        Returns:
            Short human-readable execution result.
        """
        abs_x, abs_y = self._adapter.relative_to_absolute(x, y)
        loop = self._loop()
        await loop.run_in_executor(None, self._adapter.tap, abs_x, abs_y)
        return f"已点击相对坐标 ({x}, {y})。"


class PhoneDoubleTapTool(PhoneToolBase):
    """Double tap a relative screen coordinate."""

    @property
    def name(self) -> str:
        return "phone_double_tap"

    @property
    def description(self) -> str:
        return "双击手机屏幕指定位置。坐标范围为 0-999。"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "x": {"type": "integer", "minimum": 0, "maximum": 999},
                "y": {"type": "integer", "minimum": 0, "maximum": 999},
            },
            "required": ["x", "y"],
        }

    async def execute(self, x: int, y: int, **kwargs: Any) -> str:
        """
        Double tap a relative coordinate on the active phone screen.

        Args:
            x: Relative X coordinate in the range 0-999.
            y: Relative Y coordinate in the range 0-999.

        Returns:
            Short human-readable execution result.
        """
        abs_x, abs_y = self._adapter.relative_to_absolute(x, y)
        loop = self._loop()
        await loop.run_in_executor(None, self._adapter.double_tap, abs_x, abs_y)
        return f"已双击相对坐标 ({x}, {y})。"


class PhoneLongPressTool(PhoneToolBase):
    """Long press a relative screen coordinate."""

    @property
    def name(self) -> str:
        return "phone_long_press"

    @property
    def description(self) -> str:
        return "长按手机屏幕指定位置。坐标范围为 0-999。"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "x": {"type": "integer", "minimum": 0, "maximum": 999},
                "y": {"type": "integer", "minimum": 0, "maximum": 999},
                "duration_ms": {"type": "integer", "minimum": 100, "maximum": 10000},
            },
            "required": ["x", "y"],
        }

    async def execute(
        self,
        x: int,
        y: int,
        duration_ms: int = 3000,
        **kwargs: Any,
    ) -> str:
        """
        Long press a relative coordinate on the active phone screen.

        Args:
            x: Relative X coordinate in the range 0-999.
            y: Relative Y coordinate in the range 0-999.
            duration_ms: Press duration in milliseconds.

        Returns:
            Short human-readable execution result.
        """
        abs_x, abs_y = self._adapter.relative_to_absolute(x, y)
        loop = self._loop()
        await loop.run_in_executor(None, self._adapter.long_press, abs_x, abs_y, duration_ms)
        return f"已长按相对坐标 ({x}, {y})，持续 {duration_ms}ms。"


class PhoneSwipeTool(PhoneToolBase):
    """Swipe between two relative coordinates."""

    @property
    def name(self) -> str:
        return "phone_swipe"

    @property
    def description(self) -> str:
        return "在手机屏幕上滑动。所有坐标范围为 0-999。"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "start_x": {"type": "integer", "minimum": 0, "maximum": 999},
                "start_y": {"type": "integer", "minimum": 0, "maximum": 999},
                "end_x": {"type": "integer", "minimum": 0, "maximum": 999},
                "end_y": {"type": "integer", "minimum": 0, "maximum": 999},
                "duration_ms": {"type": "integer", "minimum": 100, "maximum": 10000},
            },
            "required": ["start_x", "start_y", "end_x", "end_y"],
        }

    async def execute(
        self,
        start_x: int,
        start_y: int,
        end_x: int,
        end_y: int,
        duration_ms: int | None = None,
        **kwargs: Any,
    ) -> str:
        """
        Swipe between two relative coordinates on the active phone screen.

        Args:
            start_x: Relative starting X coordinate in the range 0-999.
            start_y: Relative starting Y coordinate in the range 0-999.
            end_x: Relative ending X coordinate in the range 0-999.
            end_y: Relative ending Y coordinate in the range 0-999.
            duration_ms: Optional swipe duration in milliseconds.

        Returns:
            Short human-readable execution result.
        """
        start_abs = self._adapter.relative_to_absolute(start_x, start_y)
        end_abs = self._adapter.relative_to_absolute(end_x, end_y)
        loop = self._loop()
        await loop.run_in_executor(
            None,
            self._adapter.swipe,
            start_abs[0],
            start_abs[1],
            end_abs[0],
            end_abs[1],
            duration_ms,
        )
        return (
            "已滑动："
            f"({start_x}, {start_y}) -> ({end_x}, {end_y})。"
        )


class PhoneTypeTool(PhoneToolBase):
    """Type text into the focused phone input field."""

    @property
    def name(self) -> str:
        return "phone_type"

    @property
    def description(self) -> str:
        return "在当前已聚焦的输入框中输入文本。"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "text": {"type": "string", "minLength": 1},
            },
            "required": ["text"],
        }

    async def execute(self, text: str, **kwargs: Any) -> str:
        """
        Type text into the current phone input field.

        Args:
            text: Text to input.

        Returns:
            Short human-readable execution result.
        """
        loop = self._loop()
        await loop.run_in_executor(None, self._adapter.type_text, text)
        return f"已输入文本，共 {len(text)} 个字符。"


class PhoneWaitTool(PhoneToolBase):
    """Pause briefly to wait for UI transitions or page loading."""

    @property
    def name(self) -> str:
        return "phone_wait"

    @property
    def description(self) -> str:
        return "等待一段时间，适用于页面加载或动画过渡。"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "seconds": {"type": "number", "minimum": 0.1, "maximum": 30},
            },
            "required": ["seconds"],
        }

    async def execute(self, seconds: float, **kwargs: Any) -> str:
        """
        Wait for a short amount of time.

        Args:
            seconds: Duration to wait in seconds.

        Returns:
            Short human-readable execution result.
        """
        loop = self._loop()
        await loop.run_in_executor(None, time.sleep, seconds)
        return f"已等待 {seconds:.1f} 秒。"
