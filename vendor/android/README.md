# Android 运行时资源

此目录用于存放 `nanobot phone ...` 使用的 Android 运行时资源。

推荐的目录结构：

```text
vendor/android/platform-tools/darwin-arm64/adb
vendor/android/platform-tools/linux-x86_64/adb
vendor/android/platform-tools/windows-x86_64/adb.exe
vendor/android/adbkeyboard/ADBKeyboard.apk
```

运行时查找顺序：

1. `tools.phoneAgent.adbPath`
2. `tools.phoneAgent.platformToolsDir`
3. 内置 `vendor/android/platform-tools/<host>`
4. 系统 `PATH`

`ADBKeyboard.apk` 是本地安装包，不是 Python 依赖。
它需要通过 `adb install` 安装到目标手机上，并在手机上启用 `com.android.adbkeyboard/.AdbIME` 之后，`phone_type` 才能工作。

对于截图、主屏、启动、点击等基础测试，`ADBKeyboard.apk` 不是必需的。
