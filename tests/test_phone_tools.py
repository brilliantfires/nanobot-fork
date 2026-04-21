"""Tests for Phase 1 phone device tools."""

from __future__ import annotations

import base64
from unittest.mock import AsyncMock, MagicMock

import pytest

from nanobot.agent.loop import AgentLoop
from nanobot.agent.tools.phone_agent import PhoneAgentTool
from nanobot.agent.tools.phone import (
    PhoneBackTool,
    PhoneHomeTool,
    PhoneLaunchTool,
    PhoneRuntimeState,
    PhoneScreenshotTool,
    PhoneTapTool,
    PhoneTypeTool,
    PhoneWaitTool,
)
from nanobot.agent.tools.phone.runtime import (
    AndroidDeviceInfo,
    detect_and_set_adb_keyboard,
    launch_android_app,
    resolve_adb_path,
)
from nanobot.bus.queue import MessageBus
from nanobot.config.schema import Config, PhoneAgentConfig
from nanobot.providers.base import LLMProvider, LLMResponse


class _DummyProvider(LLMProvider):
    """Minimal provider stub used to instantiate AgentLoop in tests."""

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
        """Return a deterministic default model for loop construction."""
        return "test/model"


class _FakeScreenshot:
    """Minimal screenshot stub used by tool tests."""

    def __init__(self, *, width: int = 1080, height: int = 2400, is_sensitive: bool = False):
        raw = b"\x89PNG\r\n\x1a\nfake-phone-png"
        self.base64_data = base64.b64encode(raw).decode("utf-8")
        self.width = width
        self.height = height
        self.is_sensitive = is_sensitive


@pytest.mark.asyncio
async def test_phone_screenshot_returns_multimodal_blocks(monkeypatch) -> None:
    config = PhoneAgentConfig()
    state = PhoneRuntimeState()
    tool = PhoneScreenshotTool(config, state)

    def _fake_get_screenshot() -> _FakeScreenshot:
        screenshot = _FakeScreenshot()
        state.screen_width = screenshot.width
        state.screen_height = screenshot.height
        return screenshot

    def _fake_get_current_app() -> str:
        state.current_app = "微信"
        return "微信"

    monkeypatch.setattr(tool._adapter, "get_screenshot", _fake_get_screenshot)
    monkeypatch.setattr(tool._adapter, "get_current_app", _fake_get_current_app)

    result = await tool.execute()

    assert isinstance(result, list)
    assert result[0]["type"] == "image_url"
    assert result[0]["image_url"]["url"].startswith("data:image/png;base64,")
    assert result[1]["type"] == "text"
    assert "当前应用: 微信" in result[1]["text"]
    assert state.screen_width == 1080
    assert state.screen_height == 2400
    assert state.current_app == "微信"


@pytest.mark.asyncio
async def test_phone_tap_converts_relative_coordinates(monkeypatch) -> None:
    config = PhoneAgentConfig()
    state = PhoneRuntimeState(screen_width=1000, screen_height=2000)
    tool = PhoneTapTool(config, state)
    captured: dict[str, tuple[int, int]] = {}

    monkeypatch.setattr(
        tool._adapter,
        "tap",
        lambda x, y: captured.__setitem__("coords", (x, y)),
    )

    result = await tool.execute(x=250, y=500)

    assert captured["coords"] == (250, 1000)
    assert "已点击相对坐标" in result


@pytest.mark.asyncio
async def test_phone_tap_requires_prior_screenshot() -> None:
    config = PhoneAgentConfig()
    state = PhoneRuntimeState()
    tool = PhoneTapTool(config, state)

    with pytest.raises(RuntimeError, match="phone_screenshot must run before"):
        await tool.execute(x=1, y=1)


@pytest.mark.asyncio
async def test_phone_type_delegates_to_adapter(monkeypatch) -> None:
    config = PhoneAgentConfig()
    state = PhoneRuntimeState()
    tool = PhoneTypeTool(config, state)
    captured: dict[str, str] = {}

    monkeypatch.setattr(
        tool._adapter,
        "type_text",
        lambda text: captured.__setitem__("text", text),
    )

    result = await tool.execute(text="hello")

    assert captured["text"] == "hello"
    assert "已输入文本" in result


@pytest.mark.asyncio
async def test_phone_launch_raises_on_failed_launch(monkeypatch) -> None:
    config = PhoneAgentConfig()
    state = PhoneRuntimeState()
    tool = PhoneLaunchTool(config, state)

    monkeypatch.setattr(tool._adapter, "launch_app", lambda app_name: False)

    with pytest.raises(RuntimeError, match="Failed to launch app"):
        await tool.execute(app_name="不存在的应用")


@pytest.mark.asyncio
async def test_phone_navigation_tools_delegate_to_adapter(monkeypatch) -> None:
    config = PhoneAgentConfig()
    state = PhoneRuntimeState()
    back_tool = PhoneBackTool(config, state)
    home_tool = PhoneHomeTool(config, state)
    seen: list[str] = []

    monkeypatch.setattr(back_tool._adapter, "back", lambda: seen.append("back"))
    monkeypatch.setattr(home_tool._adapter, "home", lambda: seen.append("home"))

    back_result = await back_tool.execute()
    home_result = await home_tool.execute()

    assert seen == ["back", "home"]
    assert back_result == "已执行返回。"
    assert home_result == "已回到桌面。"


@pytest.mark.asyncio
async def test_phone_wait_uses_sleep(monkeypatch) -> None:
    config = PhoneAgentConfig()
    state = PhoneRuntimeState()
    tool = PhoneWaitTool(config, state)
    calls: list[float] = []

    monkeypatch.setattr("nanobot.agent.tools.phone.actions.time.sleep", lambda seconds: calls.append(seconds))

    result = await tool.execute(seconds=1.5)

    assert calls == [1.5]
    assert result == "已等待 1.5 秒。"


def test_config_includes_phone_agent_block() -> None:
    config = Config()

    dumped = config.model_dump(by_alias=True)

    assert "phoneAgent" in dumped["tools"]
    assert dumped["tools"]["phoneAgent"]["deviceType"] == "adb"
    assert dumped["tools"]["phoneAgent"]["enable"] is False
    assert dumped["tools"]["phoneAgent"]["autoUseBundledPlatformTools"] is True
    assert dumped["tools"]["phoneAgent"]["requireAdbKeyboard"] is False
    assert dumped["tools"]["phoneAgent"]["experienceMemory"]["enable"] is False


def test_agent_loop_registers_phone_agent_profile_when_enabled(monkeypatch, tmp_path) -> None:
    phone_config = PhoneAgentConfig(enable=True)
    monkeypatch.setattr(AgentLoop, "_create_phone_provider", lambda self: _DummyProvider())
    loop = AgentLoop(
        bus=MessageBus(),
        provider=_DummyProvider(),
        workspace=tmp_path,
        phone_config=phone_config,
    )

    assert loop.tools.has("phone_agent")
    assert not loop.tools.has("phone_screenshot")
    assert not loop.tools.has("phone_tap")
    assert not loop.tools.has("phone_launch")
    assert "phone" in loop.subagents._profiles
    prompt = loop.context.build_system_prompt()
    assert "Connected Phone Control" in prompt
    assert "`phone_agent`" in prompt


@pytest.mark.asyncio
async def test_phone_agent_tool_spawns_phone_profile() -> None:
    manager = MagicMock()
    manager.spawn = AsyncMock(return_value="started")
    tool = PhoneAgentTool(manager)
    tool.set_context("telegram", "chat-1")

    result = await tool.execute(task="打开微信", context="当前已在桌面", label="手机任务")

    assert result == "started"
    manager.spawn.assert_awaited_once_with(
        task="打开微信\n\n补充上下文：\n当前已在桌面",
        label="手机任务",
        origin_channel="telegram",
        origin_chat_id="chat-1",
        session_key="telegram:chat-1",
        profile="phone",
    )


def test_resolve_adb_path_prefers_explicit_binary(tmp_path) -> None:
    adb = tmp_path / "adb"
    adb.write_text("", encoding="utf-8")
    adb.chmod(0o755)
    config = PhoneAgentConfig(adb_path=str(adb))

    assert resolve_adb_path(config) == adb.resolve()


def test_android_device_selection_pins_runtime_device(monkeypatch) -> None:
    config = PhoneAgentConfig(device_type="adb")
    state = PhoneRuntimeState()
    tool = PhoneTapTool(config, state)

    monkeypatch.setattr(
        "nanobot.agent.tools.phone.common.select_operable_adb_device",
        lambda cfg: AndroidDeviceInfo(
            device_id="device-123",
            status="device",
            model="Pixel",
            connection_type="usb",
        ),
    )

    selected = tool._adapter._ensure_operable_android_device()

    assert selected == "device-123"
    assert tool._config.device_id == "device-123"


def test_launch_android_app_accepts_successful_start_output_when_focus_probe_lags(monkeypatch) -> None:
    config = PhoneAgentConfig(device_type="adb")

    monkeypatch.setattr(
        "nanobot.agent.tools.phone.runtime.resolve_android_package",
        lambda app_name: "com.tencent.mm",
    )
    monkeypatch.setattr(
        "nanobot.agent.tools.phone.runtime.is_android_package_installed",
        lambda cfg, *, device_id, package_name: True,
    )
    monkeypatch.setattr(
        "nanobot.agent.tools.phone.runtime.resolve_android_launcher_activity",
        lambda cfg, *, device_id, package_name: "com.tencent.mm/.ui.LauncherUI",
    )
    monkeypatch.setattr(
        "nanobot.agent.tools.phone.runtime.wait_for_android_package",
        lambda cfg, *, device_id, package_name, timeout_seconds, poll_interval_seconds: "com.android.launcher",
    )

    def _fake_run_adb_command(cfg, args, *, device_id=None, timeout=10, text=True, check=True):
        class _Result:
            stdout = "Status: ok\nActivity: com.tencent.mm/.ui.LauncherUI\n"

        return _Result()

    monkeypatch.setattr("nanobot.agent.tools.phone.runtime.run_adb_command", _fake_run_adb_command)

    assert launch_android_app(config, device_id="device-123", app_name="微信") is True


def test_launch_android_app_returns_false_when_install_check_fails(monkeypatch) -> None:
    config = PhoneAgentConfig(device_type="adb")

    monkeypatch.setattr(
        "nanobot.agent.tools.phone.runtime.resolve_android_package",
        lambda app_name: "com.eg.android.AlipayGphone",
    )
    monkeypatch.setattr(
        "nanobot.agent.tools.phone.runtime.is_android_package_installed",
        lambda cfg, *, device_id, package_name: False,
    )

    assert launch_android_app(config, device_id="device-123", app_name="支付宝") is False


def test_detect_and_set_adb_keyboard_only_switches_ime(monkeypatch) -> None:
    config = PhoneAgentConfig(device_type="adb")
    calls: list[list[str]] = []

    monkeypatch.setattr(
        "nanobot.agent.tools.phone.runtime.read_current_ime",
        lambda cfg, *, device_id: "com.android.inputmethod/.LatinIME",
    )

    def _fake_run_adb_command(cfg, args, *, device_id=None, timeout=10, text=True, check=True):
        calls.append(args)

        class _Result:
            stdout = "Input method changed"

        return _Result()

    monkeypatch.setattr("nanobot.agent.tools.phone.runtime.run_adb_command", _fake_run_adb_command)

    original = detect_and_set_adb_keyboard(config, device_id="device-123")

    assert original == "com.android.inputmethod/.LatinIME"
    assert calls == [["shell", "ime", "set", "com.android.adbkeyboard/.AdbIME"]]
