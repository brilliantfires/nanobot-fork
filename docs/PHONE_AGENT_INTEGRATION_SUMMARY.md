# nanobot 手机能力集成总结

## 1. 目标与结果

本轮工作的目标，是将原本独立于 `nanobot` 的手机自动化能力，重构为 `nanobot` 原生可管理的能力体系。

当前已经完成的结果：

- `nanobot` 已具备 Android 手机基础控制能力。
- 手机能力已经接入 `nanobot` 的工具体系、配置体系、CLI 和子 agent 体系。
- 主 agent 可以通过高层 `phone_agent` 工具，把真实手机任务委托给专用 phone subagent。
- 通用 subagent 仍然保留，手机子 agent 作为 `profile="phone"` 的专用 profile 存在。
- 当前整体方案以 `function calling` 为主，不依赖 `Open-AutoGLM` 的原始 agent loop 运行。

## 2. 当前实现的功能

### 2.1 手机基础工具

当前已经实现并接入的手机工具包括：

- `phone_screenshot`
- `phone_tap`
- `phone_double_tap`
- `phone_long_press`
- `phone_swipe`
- `phone_type`
- `phone_wait`
- `phone_launch`
- `phone_back`
- `phone_home`

这些工具当前主要服务 Android `adb` 设备。

### 2.2 手机运行时能力

当前已经具备：

- `adb` 路径自动解析
- 设备探测与可操作设备选择
- 真机截图
- 应用启动
- 点击、滑动、返回、回桌面
- ADB Keyboard 检测与输入
- `platform-tools` 本地内置路径支持

### 2.3 CLI 能力

当前新增并可用的 CLI 能力包括：

- `nanobot phone doctor`
- `nanobot phone packages`
- `nanobot phone smoke`

用途分别是：

- `phone doctor`
  - 检查 `adb`、设备连接状态、ADB Keyboard 状态
- `phone packages`
  - 查看设备上的安装包，辅助定位应用启动问题
- `phone smoke`
  - 做一条基础手机动作链路验证

### 2.4 子 Agent 能力

当前已经完成：

- `SubagentProfile` 抽象
- `default` 通用 subagent profile
- `phone` 专用 subagent profile
- 高层 `phone_agent` 工具
- 主 agent 到 phone subagent 的异步后台回传链路

也就是说，现在的手机任务不是主 agent 自己直接点屏幕，而是：

- 主 agent 识别手机任务
- 调用 `phone_agent`
- `phone_agent` 启动 `profile="phone"` 的子 agent
- phone subagent 使用专用 provider、专用 prompt、专用手机工具完成任务
- 结果再回传给主 agent

## 3. 核心实现方式

### 3.1 总体结构

当前采用的是：

- `nanobot` 负责 agent loop、tool registry、provider、session、subagent 生命周期
- 手机能力在 `nanobot` 内部实现为原生 tools
- phone-agent 实现为一个专用 subagent profile，而不是平行的新框架

主链路如下：

1. 用户向主 agent 提交任务
2. 主 agent 看到 `phone_agent` 工具和运行时手机能力说明
3. 如果是手机任务，主 agent 调用 `phone_agent`
4. `phone_agent` 内部调用 `SubagentManager.spawn(..., profile="phone")`
5. phone subagent 在后台运行
6. phone subagent 每轮自动截图，构造多模态输入，调用 VLM，再执行手机工具
7. 完成后通过 bus 回传结果
8. 主 agent 再把结果总结给用户

### 3.2 与 Open-AutoGLM 的关系

当前方案不是把 `Open-AutoGLM` 整体黑盒接入。

当前实际策略是：

- 架构、控制流、子 agent 生命周期，全部归 `nanobot`
- 手机能力主要在 `nanobot` 内部实现和管理
- Android 运行时、应用映射、prompt 思路等参考了 `Open-AutoGLM`
- 当前运行不再要求安装 `Open-AutoGLM` 作为项目依赖

### 3.3 Phone Profile 的关键特点

`phone` profile 与通用 `default` profile 的主要区别：

- 单独的 provider / model
- 单独的手机操作 prompt
- 单独的手机工具集
- 每轮自动截图
- 每轮重建上下文，而不是单纯累积长历史

当前 phone 子 agent 每轮都会强调：

- 原始任务
- 当前轮次
- 最近动作摘要
- 最新截图

这样可以让模型持续围绕同一个真实手机任务推进。

## 4. 主要改动模块

本轮改动主要集中在以下区域。

### 4.1 配置层

- `nanobot/nanobot/config/schema.py`

新增和扩展了 `PhoneAgentConfig`，包括：

- `enable`
- `provider`
- `base_url`
- `api_key`
- `model`
- `use_tool_calling`
- `device_type`
- `device_id`
- `adb_path`
- `platform_tools_dir`
- `adb_keyboard_apk_path`
- `auto_use_bundled_platform_tools`
- `require_adb_keyboard`

### 4.2 手机工具与运行时

- `nanobot/nanobot/agent/tools/phone/`

其中包括：

- `runtime.py`
- `common.py`
- `actions.py`
- `navigation.py`
- `screenshot.py`

### 4.3 子 agent 框架

- `nanobot/nanobot/agent/subagent.py`
- `nanobot/nanobot/agent/subagent_profiles.py`

实现了：

- profile 注册与分发
- `default` / `phone` profile
- 每轮重建上下文
- 子任务异步后台执行与结果回传

### 4.4 主 agent 接线

- `nanobot/nanobot/agent/loop.py`
- `nanobot/nanobot/agent/context.py`
- `nanobot/nanobot/agent/tools/phone_agent.py`
- `nanobot/nanobot/agent/tools/spawn.py`
- `nanobot/nanobot/agent/phone_prompt.py`

### 4.5 CLI

- `nanobot/nanobot/cli/commands.py`

### 4.6 测试

- `nanobot/tests/test_phone_tools.py`
- `nanobot/tests/test_phone_agent_profile.py`
- `nanobot/tests/test_commands.py`
- `nanobot/tests/test_task_cancel.py`

## 5. 配置方法

手机能力配置位于：

- `nanobot/nanobot/config/schema.py`
- 实际运行时配置文件中的 `tools.phoneAgent`

一个典型配置示意如下：

```toml
[tools.phoneAgent]
enable = true
provider = "custom"
baseUrl = "https://api.siliconflow.cn/v1"
apiKey = "..."
model = "Qwen/Qwen3.5-397B-A17B"
useToolCalling = true
deviceType = "adb"
autoUseBundledPlatformTools = true
maxSteps = 50
lang = "cn"
temperature = 0.0
```

### 5.1 Android 运行时资源位置

当前约定：

- `nanobot/vendor/android/platform-tools/`
- `nanobot/vendor/android/adbkeyboard/ADBKeyboard.apk`

`adb` 的解析顺序为：

1. `adbPath`
2. `platformToolsDir`
3. `vendor/android/platform-tools`
4. 系统 `PATH`

## 6. 使用方式

### 6.1 验证基础环境

先使用：

```bash
uv run --active nanobot phone doctor
```

确认以下项目正常：

- `adb` 可执行
- 已连接可操作设备
- ADB Keyboard 状态

### 6.2 验证基础动作链路

```bash
uv run --active nanobot phone smoke --app 微信
```

### 6.3 主 agent 使用手机能力

当 `phoneAgent.enable=true` 且设备可用时，主 agent 可通过高层 `phone_agent` 工具处理手机任务。

典型任务示例：

- 打开微信并给文件传输助手发送你好
- 打开美团并搜索芝士芭乐
- 打开设置并进入 WLAN 页面

### 6.4 通用 subagent 仍然可用

当前并没有因为 phone profile 的加入而关闭通用 subagent。

也就是说：

- `spawn` 仍然走默认 `default` profile
- `phone_agent` 走专用 `phone` profile

两者并存。

## 7. 当前约束与边界

当前边界如下：

- 当前正式跑通的是 Android `adb`
- `function calling` 是当前主路径
- `text_parsing` 模式仍未实现
- `hdc` / `ios` 当前未完成完整接线
- 支付确认、验证码、登录、权限授权等场景，仍应视为真实阻塞并显式暴露

同时，当前遵循以下工程原则：

- 不做静默降级
- 不假装成功
- 工具失败应明确暴露
- 图片失败时，phone profile 不自动切成无图模式

## 8. 当前项目状态

截至当前版本，`nanobot` 已经具备：

- 手机基础控制能力
- 手机 CLI 验证能力
- 专用 phone subagent
- 主 agent 到 phone-agent 的委托链路
- 通用 subagent 与 phone subagent 并存的 profile 化框架

这意味着当前项目已经从“手机能力外置于独立项目”演进为：

**手机能力成为 `nanobot` 原生架构的一部分。**
