"""Shared helpers for phone tools and runners."""

from __future__ import annotations

import asyncio
import base64
import binascii
from dataclasses import dataclass
from typing import Any

from nanobot.agent.tools.base import Tool
from nanobot.agent.tools.phone.runtime import (
    back_android,
    capture_android_screenshot,
    clear_android_text,
    detect_and_set_adb_keyboard,
    double_tap_android,
    get_current_android_app,
    home_android,
    is_adb_keyboard_installed,
    launch_android_app,
    long_press_android,
    restore_android_keyboard,
    select_operable_adb_device,
    swipe_android,
    tap_android,
    type_android_text,
)
from nanobot.config.schema import PhoneAgentConfig
from nanobot.utils.helpers import detect_image_mime


@dataclass
class PhoneRuntimeState:
    """Mutable runtime state shared by phone tools during one task."""

    screen_width: int | None = None
    screen_height: int | None = None
    current_app: str | None = None


class PhoneToolBase(Tool):
    """Shared base class for phone tools."""

    def __init__(self, config: PhoneAgentConfig, state: PhoneRuntimeState):
        """
        Initialize a phone tool.

        Args:
            config: Phone agent configuration.
            state: Shared runtime state for the active phone task.
        """
        self._config = config
        self._state = state
        self._adapter = PhoneDeviceAdapter(config, state)

    @staticmethod
    def _loop() -> asyncio.AbstractEventLoop:
        """Return the active event loop for executor-based tool calls."""
        return asyncio.get_running_loop()


class PhoneDeviceAdapter:
    """Adapter that normalizes phone operations across supported device runtimes."""

    def __init__(self, config: PhoneAgentConfig, state: PhoneRuntimeState):
        """
        Initialize the adapter.

        Args:
            config: Phone agent configuration.
            state: Shared runtime state for the active phone task.
        """
        self.config = config
        self.state = state

    @property
    def device_type(self) -> str:
        """Return the configured device type."""
        return self.config.device_type

    def get_screenshot(self) -> Any:
        """
        Capture a screenshot and refresh cached screen metadata.

        Returns:
            The upstream screenshot object with ``base64_data``, ``width`` and ``height``.
        """
        if self.device_type == "adb":
            device_id = self._ensure_operable_android_device()
            screenshot = capture_android_screenshot(self.config, device_id=device_id)
        else:
            raise RuntimeError(
                f"Unsupported phone device type for local runtime: {self.device_type}. "
                "Current nanobot phone tools support Android adb only."
            )

        self.state.screen_width = screenshot.width
        self.state.screen_height = screenshot.height
        return screenshot

    def get_current_app(self) -> str:
        """
        Read the current foreground app and refresh cached runtime state.

        Returns:
            Human-readable app name or bundle identifier.
        """
        if self.device_type != "adb":
            raise RuntimeError(
                f"Unsupported phone device type for local runtime: {self.device_type}. "
                "Current nanobot phone tools support Android adb only."
            )
        current_app = get_current_android_app(
            self.config,
            device_id=self._ensure_operable_android_device(),
        )

        self.state.current_app = current_app
        return current_app

    def tap(self, x: int, y: int) -> None:
        """Tap the screen at absolute pixel coordinates."""
        self._require_android_runtime()
        tap_android(self.config, device_id=self._ensure_operable_android_device(), x=x, y=y)

    def double_tap(self, x: int, y: int) -> None:
        """Double tap the screen at absolute pixel coordinates."""
        self._require_android_runtime()
        double_tap_android(self.config, device_id=self._ensure_operable_android_device(), x=x, y=y)

    def long_press(self, x: int, y: int, duration_ms: int = 3000) -> None:
        """Long press the screen at absolute pixel coordinates."""
        self._require_android_runtime()
        long_press_android(
            self.config,
            device_id=self._ensure_operable_android_device(),
            x=x,
            y=y,
            duration_ms=duration_ms,
        )

    def swipe(
        self,
        start_x: int,
        start_y: int,
        end_x: int,
        end_y: int,
        duration_ms: int | None = None,
    ) -> None:
        """Swipe using absolute pixel coordinates."""
        self._require_android_runtime()
        swipe_android(
            self.config,
            device_id=self._ensure_operable_android_device(),
            start_x=start_x,
            start_y=start_y,
            end_x=end_x,
            end_y=end_y,
            duration_ms=duration_ms,
        )

    def back(self) -> None:
        """Navigate back."""
        self._require_android_runtime()
        back_android(self.config, device_id=self._ensure_operable_android_device())

    def home(self) -> None:
        """Navigate to the device home screen."""
        self._require_android_runtime()
        home_android(self.config, device_id=self._ensure_operable_android_device())

    def launch_app(self, app_name: str) -> bool:
        """Launch an app by name."""
        self._require_android_runtime()
        return bool(
            launch_android_app(
                self.config,
                device_id=self._ensure_operable_android_device(),
                app_name=app_name,
            )
        )

    def type_text(self, text: str) -> None:
        """
        Type text into the currently focused input field.

        Args:
            text: Text to input.
        """
        self._require_android_runtime()
        device_id = self._ensure_operable_android_device()
        if not is_adb_keyboard_installed(self.config, device_id=device_id):
            raise RuntimeError(
                "ADB Keyboard is not installed on the selected device. "
                "Install and enable `com.android.adbkeyboard/.AdbIME` before using phone_type."
            )

        original_ime = detect_and_set_adb_keyboard(self.config, device_id=device_id)
        try:
            clear_android_text(self.config, device_id=device_id)
            type_android_text(self.config, device_id=device_id, text=text)
        finally:
            restore_android_keyboard(self.config, device_id=device_id, ime=original_ime)

    def relative_to_absolute(self, x: int, y: int) -> tuple[int, int]:
        """
        Convert 0-999 relative coordinates to absolute pixels.

        Args:
            x: Relative X coordinate.
            y: Relative Y coordinate.

        Returns:
            A tuple of absolute pixel coordinates.

        Raises:
            RuntimeError: If screen size has not been established yet.
        """
        if self.state.screen_width is None or self.state.screen_height is None:
            raise RuntimeError("phone_screenshot must run before coordinate-based phone actions")

        abs_x = int(x / 1000 * self.state.screen_width)
        abs_y = int(y / 1000 * self.state.screen_height)
        return abs_x, abs_y

    @staticmethod
    def decode_screenshot(screenshot: Any) -> tuple[bytes, str]:
        """
        Decode screenshot base64 into raw bytes and a detected MIME type.

        Args:
            screenshot: Screenshot object returned by upstream backend.

        Returns:
            Tuple of raw bytes and MIME type.
        """
        try:
            raw = base64.b64decode(screenshot.base64_data)
        except (ValueError, binascii.Error) as exc:
            raise RuntimeError(f"Failed to decode phone screenshot: {exc}") from exc

        mime = detect_image_mime(raw) or "image/png"
        return raw, mime

    def _ensure_operable_android_device(self) -> str:
        """
        Resolve and cache the active Android device identifier.

        Returns:
            The adb device identifier selected for the current task.
        """
        device = select_operable_adb_device(self.config)
        # 一旦自动选出设备，就固定到当前任务，避免中途在多设备环境下漂移。
        if self.config.device_id is None:
            self.config.device_id = device.device_id
        return device.device_id

    def _require_android_runtime(self) -> None:
        """
        Ensure the current adapter runs against the supported Android runtime.

        Raises:
            RuntimeError: If the configured device type is not adb.
        """
        if self.device_type != "adb":
            raise RuntimeError(
                f"Unsupported phone device type for local runtime: {self.device_type}. "
                "Current nanobot phone tools support Android adb only."
            )
