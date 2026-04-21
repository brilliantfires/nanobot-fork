"""Android phone runtime helpers for adb resolution, device probing, and smoke checks."""

from __future__ import annotations

import base64
import os
import platform
import re
import shutil
import subprocess
import time
from contextlib import contextmanager
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Iterator

from nanobot.config.schema import PhoneAgentConfig

ANDROID_APP_PACKAGES: dict[str, str] = {
    "微信": "com.tencent.mm",
    "WeChat": "com.tencent.mm",
    "wechat": "com.tencent.mm",
    "QQ": "com.tencent.mobileqq",
    "微博": "com.sina.weibo",
    "支付宝": "com.eg.android.AlipayGphone",
    "淘宝": "com.taobao.taobao",
    "京东": "com.jingdong.app.mall",
    "拼多多": "com.xunmeng.pinduoduo",
    "小红书": "com.xingin.xhs",
    "豆瓣": "com.douban.frodo",
    "知乎": "com.zhihu.android",
    "高德地图": "com.autonavi.minimap",
    "百度地图": "com.baidu.BaiduMap",
    "美团": "com.sankuai.meituan",
    "大众点评": "com.dianping.v1",
    "饿了么": "me.ele",
    "携程": "ctrip.android.view",
    "12306": "com.MobileTicket",
    "抖音": "com.ss.android.ugc.aweme",
    "快手": "com.smile.gifmaker",
    "腾讯视频": "com.tencent.qqlive",
    "爱奇艺": "com.qiyi.video",
    "优酷视频": "com.youku.phone",
    "网易云音乐": "com.netease.cloudmusic",
    "QQ音乐": "com.tencent.qqmusic",
    "飞书": "com.ss.android.lark",
    "QQ邮箱": "com.tencent.androidqqmail",
    "豆包": "com.larus.nova",
    "腾讯新闻": "com.tencent.news",
    "今日头条": "com.ss.android.article.news",
    "Chrome": "com.android.chrome",
    "chrome": "com.android.chrome",
    "Google Chrome": "com.android.chrome",
    "Settings": "com.android.settings",
    "设置": "com.android.settings",
    "AndroidSystemSettings": "com.android.settings",
    "Files": "com.android.fileexplorer",
    "Gmail": "com.google.android.gm",
    "Google Maps": "com.google.android.apps.maps",
    "Google Play Store": "com.android.vending",
    "Telegram": "org.telegram.messenger",
    "WhatsApp": "com.whatsapp",
}

_ADB_KEYBOARD_IME = "com.android.adbkeyboard/.AdbIME"


@dataclass
class AndroidDeviceInfo:
    """
    Android 设备信息。

    Args:
        device_id: adb 识别到的设备序列号。
        status: adb 设备状态，例如 ``device``、``unauthorized``、``offline``。
        model: 解析到的设备型号，可为空。
        connection_type: 连接类型摘要，例如 ``usb``、``remote``、``emulator``。
    """

    device_id: str
    status: str
    model: str | None
    connection_type: str


@dataclass
class AndroidScreenshot:
    """
    Android 截图结果。

    Args:
        base64_data: PNG 原始字节的 base64 编码。
        width: 截图宽度。
        height: 截图高度。
        is_sensitive: 保留与上游截图对象兼容的字段，当前固定为 False。
    """

    base64_data: str
    width: int
    height: int
    is_sensitive: bool = False


def get_nanobot_root() -> Path:
    """
    Return the nanobot project root directory.

    Returns:
        The repository-local ``nanobot/`` project root.
    """
    return Path(__file__).resolve().parents[4]


def get_host_platform_slug() -> str:
    """
    Build a stable host-platform slug for bundled adb discovery.

    Returns:
        Slug such as ``darwin-arm64`` or ``linux-x86_64``.
    """
    system = platform.system().lower()
    machine = platform.machine().lower()
    aliases = {
        "amd64": "x86_64",
        "aarch64": "arm64",
        "arm64e": "arm64",
    }
    return f"{system}-{aliases.get(machine, machine)}"


def get_bundled_adb_keyboard_candidates(config: PhoneAgentConfig) -> list[Path]:
    """
    Collect candidate local APK paths for ADB Keyboard.

    Args:
        config: Phone runtime configuration.

    Returns:
        Ordered list of candidate APK paths.
    """
    candidates: list[Path] = []
    if config.adb_keyboard_apk_path:
        candidates.append(Path(config.adb_keyboard_apk_path).expanduser())

    candidates.append(get_nanobot_root() / "vendor" / "android" / "adbkeyboard" / "ADBKeyboard.apk")

    seen: set[Path] = set()
    unique: list[Path] = []
    for candidate in candidates:
        resolved = candidate.expanduser()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(resolved)
    return unique


def resolve_adb_keyboard_apk_path(config: PhoneAgentConfig) -> Path | None:
    """
    Resolve the local ADB Keyboard installer path if available.

    Args:
        config: Phone runtime configuration.

    Returns:
        APK path when a local installer is available, otherwise ``None``.
    """
    for candidate in get_bundled_adb_keyboard_candidates(config):
        if candidate.is_file():
            return candidate.resolve()
    return None


def get_bundled_platform_tools_candidates(config: PhoneAgentConfig) -> list[Path]:
    """
    Collect candidate bundled platform-tools directories.

    Args:
        config: Phone runtime configuration.

    Returns:
        Ordered list of candidate directories to probe.
    """
    candidates: list[Path] = []
    if config.platform_tools_dir:
        candidates.append(Path(config.platform_tools_dir).expanduser())

    if config.auto_use_bundled_platform_tools:
        nanobot_root = get_nanobot_root()
        host_slug = get_host_platform_slug()
        candidates.extend(
            [
                nanobot_root / "vendor" / "android" / "platform-tools" / host_slug,
                nanobot_root / "vendor" / "android" / "platform-tools",
            ]
        )

    # 保留顺序并去重，避免同一路径被重复探测。
    seen: set[Path] = set()
    unique: list[Path] = []
    for candidate in candidates:
        resolved = candidate.expanduser()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(resolved)
    return unique


def resolve_adb_path(config: PhoneAgentConfig) -> Path:
    """
    Resolve the adb executable path for Android operations.

    Resolution order:
    1. ``config.adb_path``
    2. ``config.platform_tools_dir``
    3. bundled ``nanobot/vendor/android/platform-tools``
    4. system ``PATH``

    Args:
        config: Phone runtime configuration.

    Returns:
        Absolute path to the adb executable.

    Raises:
        RuntimeError: If adb cannot be found.
    """
    executable_name = "adb.exe" if os.name == "nt" else "adb"

    if config.adb_path:
        explicit = Path(config.adb_path).expanduser()
        if explicit.is_file():
            return explicit.resolve()
        raise RuntimeError(f"Configured adb path does not exist: {explicit}")

    for directory in get_bundled_platform_tools_candidates(config):
        candidate = directory / executable_name
        if candidate.is_file():
            return candidate.resolve()

    system_adb = shutil.which("adb")
    if system_adb:
        return Path(system_adb).resolve()

    raise RuntimeError(
        "ADB executable not found. Set tools.phoneAgent.adbPath, "
        "set tools.phoneAgent.platformToolsDir, or place platform-tools under "
        "`nanobot/vendor/android/platform-tools`."
    )


@contextmanager
def adb_path_environment(config: PhoneAgentConfig) -> Iterator[Path]:
    """
    Temporarily prepend the resolved adb directory to ``PATH``.

    This is useful when a local helper still shells out to the literal ``adb`` name.

    Args:
        config: Phone runtime configuration.

    Yields:
        The resolved adb executable path.
    """
    adb_path = resolve_adb_path(config)
    original_path = os.environ.get("PATH", "")
    adb_dir = str(adb_path.parent)
    os.environ["PATH"] = adb_dir if not original_path else f"{adb_dir}{os.pathsep}{original_path}"
    try:
        yield adb_path
    finally:
        os.environ["PATH"] = original_path


def run_adb_command(
    config: PhoneAgentConfig,
    args: list[str],
    *,
    device_id: str | None = None,
    timeout: int = 10,
    text: bool = True,
    check: bool = True,
) -> subprocess.CompletedProcess[str] | subprocess.CompletedProcess[bytes]:
    """
    Run an adb command using the resolved adb executable.

    Args:
        config: Phone runtime configuration.
        args: adb subcommand arguments without the adb executable itself.
        device_id: Optional explicit device selector.
        timeout: Command timeout in seconds.
        text: Whether to capture text output.
        check: Whether to raise on non-zero exit code.

    Returns:
        The completed subprocess result.

    Raises:
        RuntimeError: If command execution fails or exits non-zero when ``check`` is True.
    """
    adb_path = resolve_adb_path(config)
    cmd = [str(adb_path)]
    if device_id:
        cmd.extend(["-s", device_id])
    cmd.extend(args)

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=text,
        timeout=timeout,
    )
    if check and result.returncode != 0:
        stderr = result.stderr if isinstance(result.stderr, str) else (result.stderr or b"").decode("utf-8", errors="replace")
        stdout = result.stdout if isinstance(result.stdout, str) else (result.stdout or b"").decode("utf-8", errors="replace")
        detail = stderr.strip() or stdout.strip() or f"exit code {result.returncode}"
        raise RuntimeError(f"ADB command failed: {' '.join(args)}: {detail}")
    return result


def get_adb_version(config: PhoneAgentConfig) -> str:
    """
    Read the adb version string.

    Args:
        config: Phone runtime configuration.

    Returns:
        First non-empty line of ``adb version`` output.
    """
    result = run_adb_command(config, ["version"], timeout=10, text=True, check=True)
    output = (result.stdout or "").strip().splitlines()
    return output[0] if output else "adb installed"


def list_adb_devices(config: PhoneAgentConfig) -> list[AndroidDeviceInfo]:
    """
    List devices currently visible to adb.

    Args:
        config: Phone runtime configuration.

    Returns:
        Parsed device list from ``adb devices -l``.
    """
    result = run_adb_command(config, ["devices", "-l"], timeout=10, text=True, check=True)
    devices: list[AndroidDeviceInfo] = []
    lines = (result.stdout or "").strip().splitlines()
    for line in lines[1:]:
        stripped = line.strip()
        if not stripped:
            continue

        parts = stripped.split()
        if len(parts) < 2:
            continue

        device_id = parts[0]
        status = parts[1]
        model = None
        for part in parts[2:]:
            if part.startswith("model:"):
                model = part.split(":", 1)[1]
                break

        if ":" in device_id:
            connection_type = "remote"
        elif device_id.startswith("emulator-"):
            connection_type = "emulator"
        else:
            connection_type = "usb"

        devices.append(
            AndroidDeviceInfo(
                device_id=device_id,
                status=status,
                model=model,
                connection_type=connection_type,
            )
        )
    return devices


def list_installed_android_packages(config: PhoneAgentConfig, *, device_id: str) -> list[str]:
    """
    List installed Android package names on the selected device.

    Args:
        config: Phone runtime configuration.
        device_id: Device identifier that adb should target.

    Returns:
        Sorted package-name list.
    """
    result = run_adb_command(
        config,
        ["shell", "pm", "list", "packages"],
        device_id=device_id,
        timeout=20,
        text=True,
        check=True,
    )
    packages: list[str] = []
    for line in (result.stdout or "").splitlines():
        stripped = line.strip()
        if not stripped.startswith("package:"):
            continue
        packages.append(stripped.split("package:", 1)[1])
    return sorted(packages)


def is_android_package_installed(
    config: PhoneAgentConfig,
    *,
    device_id: str,
    package_name: str,
) -> bool:
    """
    Check whether a package exists on the target Android device.

    Args:
        config: Phone runtime configuration.
        device_id: Device identifier that adb should target.
        package_name: Android package name to check.

    Returns:
        True if the package is installed, otherwise False.
    """
    installed_packages = list_installed_android_packages(config, device_id=device_id)
    return package_name in installed_packages


def resolve_android_package(app_name: str) -> str | None:
    """
    Resolve a human-readable Android app name to its package name.

    Args:
        app_name: Human-readable app name or direct package name.

    Returns:
        Android package name, or ``None`` when it cannot be resolved.
    """
    if app_name in ANDROID_APP_PACKAGES:
        return ANDROID_APP_PACKAGES[app_name]
    if "." in app_name:
        return app_name
    return None


def get_android_app_name(package_name: str) -> str:
    """
    Convert a package name back to a human-readable app identifier.

    Args:
        package_name: Android package name.

    Returns:
        Known app name when mapped, otherwise the original package name.
    """
    for app_name, package in ANDROID_APP_PACKAGES.items():
        if package == package_name:
            return app_name
    return package_name


def select_operable_adb_device(config: PhoneAgentConfig) -> AndroidDeviceInfo:
    """
    Select a usable Android device for the current configuration.

    Args:
        config: Phone runtime configuration.

    Returns:
        The chosen device information.

    Raises:
        RuntimeError: If no usable device exists or the configured device is unavailable.
    """
    devices = list_adb_devices(config)
    if not devices:
        raise RuntimeError("No adb devices detected. Connect a device and authorize USB debugging first.")

    if config.device_id:
        for device in devices:
            if device.device_id == config.device_id:
                if device.status != "device":
                    raise RuntimeError(
                        f"Configured adb device is not operable: {device.device_id} ({device.status})"
                    )
                return device
        raise RuntimeError(f"Configured adb device not found: {config.device_id}")

    for device in devices:
        if device.status == "device":
            return device

    rendered = ", ".join(f"{device.device_id} ({device.status})" for device in devices)
    raise RuntimeError(f"No operable adb device detected. Current entries: {rendered}")


def is_adb_keyboard_installed(config: PhoneAgentConfig, *, device_id: str) -> bool:
    """
    Check whether ADB Keyboard is available on the selected device.

    Args:
        config: Phone runtime configuration.
        device_id: Device identifier that adb should target.

    Returns:
        True when ``com.android.adbkeyboard/.AdbIME`` is present.
    """
    result = run_adb_command(
        config,
        ["shell", "ime", "list", "-s"],
        device_id=device_id,
        timeout=10,
        text=True,
        check=True,
    )
    return "com.android.adbkeyboard/.AdbIME" in (result.stdout or "")


def capture_android_screenshot(config: PhoneAgentConfig, *, device_id: str) -> AndroidScreenshot:
    """
    Capture a real Android screenshot without silent fallback.

    Args:
        config: Phone runtime configuration.
        device_id: Device identifier that adb should target.

    Returns:
        Screenshot payload compatible with existing phone tool expectations.

    Raises:
        RuntimeError: If Pillow is missing or screenshot capture fails.
    """
    try:
        from PIL import Image
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Missing Pillow dependency. Install it in the nanobot uv environment before using phone screenshots."
        ) from exc

    result = run_adb_command(
        config,
        ["exec-out", "screencap", "-p"],
        device_id=device_id,
        timeout=20,
        text=False,
        check=True,
    )
    raw = result.stdout or b""
    if not raw:
        raise RuntimeError("ADB screenshot returned empty output.")

    try:
        image = Image.open(BytesIO(raw))
        image.load()
    except Exception as exc:
        raise RuntimeError(f"Failed to decode adb screenshot output: {exc}") from exc

    return AndroidScreenshot(
        base64_data=base64.b64encode(raw).decode("utf-8"),
        width=image.width,
        height=image.height,
        is_sensitive=False,
    )


def get_current_android_app(config: PhoneAgentConfig, *, device_id: str) -> str:
    """
    Read the currently focused Android application.

    Args:
        config: Phone runtime configuration.
        device_id: Device identifier that adb should target.

    Returns:
        Human-readable app name when known, otherwise the package name.
    """
    package_name = get_current_android_package(config, device_id=device_id)
    return get_android_app_name(package_name) if package_name else "System Home"


def extract_android_package_name(
    output: str,
    *,
    markers: tuple[str, ...] = (),
) -> str | None:
    """
    Extract a package name from adb diagnostic output.

    Args:
        output: Raw adb command output.
        markers: Preferred line markers used to narrow the search scope.

    Returns:
        The first detected package name, or ``None`` when no package can be found.
    """
    if not output.strip():
        return None

    lines = output.splitlines()
    if markers:
        # 优先只看与焦点窗口、前台 Activity 直接相关的行，避免被长输出中的无关包名干扰。
        lines = [line for line in lines if any(marker in line for marker in markers)]

    package_pattern = re.compile(r"([A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+)")
    for line in lines:
        package_match = package_pattern.search(line)
        if package_match:
            return package_match.group(1)
    return None


def get_current_android_package(config: PhoneAgentConfig, *, device_id: str) -> str | None:
    """
    Read the currently focused Android package name.

    Args:
        config: Phone runtime configuration.
        device_id: Device identifier that adb should target.

    Returns:
        Focused package name when available, otherwise ``None``.
    """
    window_result = run_adb_command(
        config,
        ["shell", "dumpsys", "window"],
        device_id=device_id,
        timeout=10,
        text=True,
        check=True,
    )
    window_output = window_result.stdout or ""
    package_name = extract_android_package_name(
        window_output,
        markers=("mCurrentFocus", "mFocusedApp"),
    )
    if package_name:
        return package_name

    activity_result = run_adb_command(
        config,
        ["shell", "dumpsys", "activity", "activities"],
        device_id=device_id,
        timeout=10,
        text=True,
        check=False,
    )
    activity_output = activity_result.stdout or ""
    package_name = extract_android_package_name(
        activity_output,
        markers=("topResumedActivity", "mResumedActivity", "ResumedActivity", "mFocusedApp"),
    )
    if package_name:
        return package_name

    package_name = extract_android_package_name(window_output)
    if package_name:
        return package_name
    return extract_android_package_name(activity_output)


def launch_output_indicates_success(output: str, *, package_name: str) -> bool:
    """
    Decide whether a launch command output indicates a successful launch intent.

    Args:
        output: Raw stdout returned by ``am start`` or ``monkey``.
        package_name: Target Android package name.

    Returns:
        True when the output contains explicit success markers.
    """
    normalized = output.lower()
    if "error:" in normalized or "exception" in normalized:
        return False

    if "status: ok" in normalized:
        return True
    if "warning: activity not started" in normalized:
        return True
    if "events injected: 1" in normalized:
        return True
    return package_name.lower() in normalized and "activity" in normalized


def wait_for_android_package(
    config: PhoneAgentConfig,
    *,
    device_id: str,
    package_name: str,
    timeout_seconds: float = 5.0,
    poll_interval_seconds: float = 0.5,
) -> str | None:
    """
    Poll the device for the current foreground package after a launch action.

    Args:
        config: Phone runtime configuration.
        device_id: Device identifier that adb should target.
        package_name: Target Android package name.
        timeout_seconds: Maximum wait time.
        poll_interval_seconds: Poll interval between checks.

    Returns:
        The last detected package name, or ``None`` when no package could be read.
    """
    deadline = time.monotonic() + timeout_seconds
    last_package: str | None = None

    while time.monotonic() < deadline:
        try:
            current_package = get_current_android_package(config, device_id=device_id)
        except RuntimeError:
            current_package = None

        if current_package:
            last_package = current_package
            if current_package == package_name:
                return current_package

        time.sleep(poll_interval_seconds)

    return last_package


def tap_android(config: PhoneAgentConfig, *, device_id: str, x: int, y: int) -> None:
    """
    Tap an Android screen coordinate.

    Args:
        config: Phone runtime configuration.
        device_id: Device identifier that adb should target.
        x: Absolute X coordinate.
        y: Absolute Y coordinate.
    """
    run_adb_command(
        config,
        ["shell", "input", "tap", str(x), str(y)],
        device_id=device_id,
        timeout=10,
        text=True,
        check=True,
    )
    time.sleep(0.8)


def double_tap_android(config: PhoneAgentConfig, *, device_id: str, x: int, y: int) -> None:
    """
    Double tap an Android screen coordinate.

    Args:
        config: Phone runtime configuration.
        device_id: Device identifier that adb should target.
        x: Absolute X coordinate.
        y: Absolute Y coordinate.
    """
    tap_android(config, device_id=device_id, x=x, y=y)
    time.sleep(0.1)
    tap_android(config, device_id=device_id, x=x, y=y)


def long_press_android(
    config: PhoneAgentConfig,
    *,
    device_id: str,
    x: int,
    y: int,
    duration_ms: int = 3000,
) -> None:
    """
    Long press an Android screen coordinate.

    Args:
        config: Phone runtime configuration.
        device_id: Device identifier that adb should target.
        x: Absolute X coordinate.
        y: Absolute Y coordinate.
        duration_ms: Press duration in milliseconds.
    """
    run_adb_command(
        config,
        ["shell", "input", "swipe", str(x), str(y), str(x), str(y), str(duration_ms)],
        device_id=device_id,
        timeout=max(10, int(duration_ms / 1000) + 5),
        text=True,
        check=True,
    )
    time.sleep(0.8)


def swipe_android(
    config: PhoneAgentConfig,
    *,
    device_id: str,
    start_x: int,
    start_y: int,
    end_x: int,
    end_y: int,
    duration_ms: int | None = None,
) -> None:
    """
    Swipe on Android between two absolute screen coordinates.

    Args:
        config: Phone runtime configuration.
        device_id: Device identifier that adb should target.
        start_x: Absolute start X coordinate.
        start_y: Absolute start Y coordinate.
        end_x: Absolute end X coordinate.
        end_y: Absolute end Y coordinate.
        duration_ms: Optional swipe duration in milliseconds.
    """
    if duration_ms is None:
        dist_sq = (start_x - end_x) ** 2 + (start_y - end_y) ** 2
        duration_ms = max(300, min(int(dist_sq / 1000), 1500))

    run_adb_command(
        config,
        [
            "shell",
            "input",
            "swipe",
            str(start_x),
            str(start_y),
            str(end_x),
            str(end_y),
            str(duration_ms),
        ],
        device_id=device_id,
        timeout=max(10, int(duration_ms / 1000) + 5),
        text=True,
        check=True,
    )
    time.sleep(0.8)


def back_android(config: PhoneAgentConfig, *, device_id: str) -> None:
    """
    Press Android back.

    Args:
        config: Phone runtime configuration.
        device_id: Device identifier that adb should target.
    """
    run_adb_command(
        config,
        ["shell", "input", "keyevent", "4"],
        device_id=device_id,
        timeout=10,
        text=True,
        check=True,
    )
    time.sleep(0.5)


def home_android(config: PhoneAgentConfig, *, device_id: str) -> None:
    """
    Press Android home.

    Args:
        config: Phone runtime configuration.
        device_id: Device identifier that adb should target.
    """
    run_adb_command(
        config,
        ["shell", "input", "keyevent", "KEYCODE_HOME"],
        device_id=device_id,
        timeout=10,
        text=True,
        check=True,
    )
    time.sleep(0.8)


def launch_android_app(config: PhoneAgentConfig, *, device_id: str, app_name: str) -> bool:
    """
    Launch an Android app by app name or package name.

    Args:
        config: Phone runtime configuration.
        device_id: Device identifier that adb should target.
        app_name: Human-readable app name or direct package name.

    Returns:
        True when the app launch command was issued, False when the app cannot be resolved.
    """
    package_name = resolve_android_package(app_name)
    if package_name is None:
        return False
    if not is_android_package_installed(config, device_id=device_id, package_name=package_name):
        return False

    launcher_activity = resolve_android_launcher_activity(
        config,
        device_id=device_id,
        package_name=package_name,
    )
    launch_output = ""
    if launcher_activity:
        result = run_adb_command(
            config,
            ["shell", "am", "start", "-W", "-n", launcher_activity],
            device_id=device_id,
            timeout=15,
            text=True,
            check=True,
        )
        launch_output = result.stdout or ""
    else:
        result = run_adb_command(
            config,
            [
                "shell",
                "monkey",
                "-p",
                package_name,
                "-c",
                "android.intent.category.LAUNCHER",
                "1",
            ],
            device_id=device_id,
            timeout=15,
            text=True,
            check=True,
        )
        launch_output = result.stdout or ""

    current_package = wait_for_android_package(
        config,
        device_id=device_id,
        package_name=package_name,
        timeout_seconds=5.0,
        poll_interval_seconds=0.5,
    )
    if current_package == package_name:
        return True

    # 某些 ROM 会在启动后短暂把焦点留在桌面或系统过渡页，但 am/monkey 输出本身已明确成功。
    return launch_output_indicates_success(launch_output, package_name=package_name)


def resolve_android_launcher_activity(
    config: PhoneAgentConfig,
    *,
    device_id: str,
    package_name: str,
) -> str | None:
    """
    Resolve the launchable activity component for a package.

    Args:
        config: Phone runtime configuration.
        device_id: Device identifier that adb should target.
        package_name: Android package name.

    Returns:
        ``package/activity`` component string when resolvable, otherwise ``None``.
    """
    result = run_adb_command(
        config,
        ["shell", "cmd", "package", "resolve-activity", "--brief", package_name],
        device_id=device_id,
        timeout=10,
        text=True,
        check=False,
    )
    output = (result.stdout or "").strip().splitlines()
    for line in reversed(output):
        stripped = line.strip()
        if "/" in stripped and package_name in stripped:
            return stripped
    return None


def read_current_ime(config: PhoneAgentConfig, *, device_id: str) -> str:
    """
    Read the current Android input method identifier.

    Args:
        config: Phone runtime configuration.
        device_id: Device identifier that adb should target.

    Returns:
        Current IME identifier.
    """
    result = run_adb_command(
        config,
        ["shell", "settings", "get", "secure", "default_input_method"],
        device_id=device_id,
        timeout=10,
        text=True,
        check=True,
    )
    return (result.stdout or "").strip()


def clear_android_text(config: PhoneAgentConfig, *, device_id: str) -> None:
    """
    Clear text through ADB Keyboard on Android.

    Args:
        config: Phone runtime configuration.
        device_id: Device identifier that adb should target.
    """
    run_adb_command(
        config,
        ["shell", "am", "broadcast", "-a", "ADB_CLEAR_TEXT"],
        device_id=device_id,
        timeout=10,
        text=True,
        check=True,
    )


def type_android_text(config: PhoneAgentConfig, *, device_id: str, text: str) -> None:
    """
    Input text through ADB Keyboard on Android.

    Args:
        config: Phone runtime configuration.
        device_id: Device identifier that adb should target.
        text: Text content to input.
    """
    encoded_text = base64.b64encode(text.encode("utf-8")).decode("utf-8")
    run_adb_command(
        config,
        [
            "shell",
            "am",
            "broadcast",
            "-a",
            "ADB_INPUT_B64",
            "--es",
            "msg",
            encoded_text,
        ],
        device_id=device_id,
        timeout=10,
        text=True,
        check=True,
    )


def detect_and_set_adb_keyboard(config: PhoneAgentConfig, *, device_id: str) -> str:
    """
    Switch the active IME to ADB Keyboard and return the previous IME.

    Args:
        config: Phone runtime configuration.
        device_id: Device identifier that adb should target.

    Returns:
        The previous IME identifier.
    """
    current_ime = read_current_ime(config, device_id=device_id)
    if _ADB_KEYBOARD_IME not in current_ime:
        run_adb_command(
            config,
            ["shell", "ime", "set", _ADB_KEYBOARD_IME],
            device_id=device_id,
            timeout=10,
            text=True,
            check=True,
        )
    # 不要在切换 IME 后发送空文本广播。
    # 某些 ROM 上 `am broadcast --es msg ""` 会直接报参数错误，
    # 这会让 `phone_type` 在真正输入前就失败。
    return current_ime


def restore_android_keyboard(config: PhoneAgentConfig, *, device_id: str, ime: str) -> None:
    """
    Restore the previous Android input method.

    Args:
        config: Phone runtime configuration.
        device_id: Device identifier that adb should target.
        ime: IME identifier to restore.
    """
    if not ime:
        return
    run_adb_command(
        config,
        ["shell", "ime", "set", ime],
        device_id=device_id,
        timeout=10,
        text=True,
        check=True,
    )
