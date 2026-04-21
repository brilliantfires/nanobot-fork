# Plan: 将 Open-AutoGLM 拆解为 nanobot 原生工具，重构 phone-agent 为专用子 Agent

## Context

当前 Open-AutoGLM 是一个独立的 phone-agent 项目，有自己的 agent loop、LLM 客户端、设备控制层。作为 Claude Code skill 调用时，它是一个黑盒——nanobot 对其内部运行一无所知。

用户提出了更深层的问题：**与其把 PhoneAgent 整体包装为黑盒 runner，不如把它拆散成 nanobot 标准工具**。这样 phone-agent 本质上就是"nanobot agent loop + 手机工具集 + 多模态 LLM + 专用 system prompt"。

## 为什么要拆？—— 对比分析

### phone-agent 与通用 subagent 的核心差异

| 维度                    | 通用 subagent                 | phone-agent                    |
| ----------------------- | ----------------------------- | ------------------------------ |
| **LLM 模型**      | 与主 agent 相同（纯文本即可） | 需要多模态模型（理解 UI 截图） |
| **工具集**        | 文件/搜索/执行                | 截图/点击/输入/滑动/启动应用   |
| **上下文**        | 文本对话历史                  | 截图序列 + 操作历史            |
| **system prompt** | 通用任务完成                  | 手机 UI 操作专用指令集         |

### 拆解的收益

1. **复用 nanobot 基础设施**：agent loop、tool 执行、重试、历史管理、会话持久化——这些 PhoneAgent 自己实现了一遍，拆解后全部复用 nanobot 的
2. **工具可组合**：`phone_screenshot` 不仅 phone-agent 能用，任何需要看手机屏幕的场景都能用（测试、监控）
3. **消除重复代码**：PhoneAgent 的 ModelClient → nanobot Provider；MessageBuilder → nanobot ContextBuilder；action parsing → nanobot tool calling
4. **模型灵活性**：phone subagent 可配置不同 provider/model（多模态），主 agent 用纯文本模型

### 拆解后 Open-AutoGLM 哪些代码还有用，哪些被替代

| 保留（作为 tool 底层）                                      | 被 nanobot 替代                                               |
| ----------------------------------------------------------- | ------------------------------------------------------------- |
| `phone_agent/adb/` — ADB 设备控制                        | `PhoneAgent` 类及其 agent loop                              |
| `phone_agent/hdc/` — HDC 设备控制                        | `ModelClient` — 用 nanobot LLMProvider                     |
| `phone_agent/xctest/` — iOS 控制                         | `MessageBuilder` — 用 nanobot ContextBuilder               |
| `phone_agent/device_factory.py` — 设备抽象               | `ActionHandler.parse_action()` — 不需要了，LLM 直接调 tool |
| `phone_agent/config/apps.py` — 应用映射表                | `_execute_step()` 循环 — 用 nanobot agent loop             |
| `phone_agent/config/prompts_*.py` — 系统提示词（需适配） | loop monitor — 用 nanobot max_iterations                     |

## Architecture: 工具化 + 专用子 Agent

```
用户: "帮我在美团上点一份外卖"
  ↓
nanobot 主 Agent Loop (纯文本 LLM)
  ├─ 识别手机任务 → 调用 phone_agent tool (高层 tool)
  │     └─ SubagentManager.spawn(profile="phone")
  │         ├─ 立即返回（非阻塞）
  │         └─ 后台: _run_subagent(profile="phone")
  │              ├─ 创建独立的 ToolRegistry，注册手机工具:
  │              │   phone_screenshot, phone_tap, phone_type,
  │              │   phone_swipe, phone_launch, phone_back, ...
  │              ├─ 使用单独配置的多模态 LLM Provider
  │              ├─ 加载手机专用 system prompt
  │              ├─ 运行 nanobot 标准 agent loop:
  │              │   LLM 看截图 → 决定调 phone_tap(500,600) → 执行 → 再截图 → ...
  │              └─ 完成后 announce_result → MessageBus
  ├─ 主 Agent 收到结果，回复用户
  └─ "已帮您在美团下单了黄焖鸡，共 25 元"
```

**关键区别**：phone subagent 内部用的是 **nanobot 的 agent loop**（tool calling 模式），不是 PhoneAgent 自己的 `_execute_step()` 循环。手机操作变成了 LLM 可调用的 tools。

## 具体 Changes

### Phase 1: 手机设备工具集

#### 1.1 New: `nanobot/nanobot/agent/tools/phone/` — 手机工具包

所有工具继承 `Tool` 基类，通过 `run_in_executor` 桥接同步设备调用。

**`phone_screenshot`** — 感知工具（最核心）

```python
name = "phone_screenshot"
description = "截取手机当前屏幕并返回截图和当前应用信息"
parameters = {}  # 无参数
execute():
    factory = get_device_factory()
    screenshot = await loop.run_in_executor(None, factory.get_screenshot, device_id)
    current_app = await loop.run_in_executor(None, factory.get_current_app, device_id)
    # 返回多模态内容 (nanobot 已支持 build_image_content_blocks)
    return [
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{screenshot.base64_data}"}},
        {"type": "text", "text": f"当前应用: {current_app}, 屏幕尺寸: {screenshot.width}x{screenshot.height}"}
    ]
```

**`phone_tap`** — 点击

```python
name = "phone_tap"
description = "点击手机屏幕指定位置（坐标范围 0-999）"
parameters = {x: int (0-999), y: int (0-999)}
execute(x, y):
    # 坐标转换 (沿用 ActionHandler._convert_relative_to_absolute)
    abs_x = x * screen_width // 1000
    abs_y = y * screen_height // 1000
    await loop.run_in_executor(None, factory.tap, abs_x, abs_y, device_id)
    return f"已点击 ({x}, {y})"
```

**`phone_type`** — 文字输入

```python
name = "phone_type"
description = "在当前输入框中输入文字（自动处理键盘切换）"
parameters = {text: str}
execute(text):
    # 沿用 adb keyboard 切换逻辑
    await loop.run_in_executor(None, factory.type_text, text, device_id)
    return f"已输入: {text}"
```

**`phone_swipe`** — 滑动

```python
name = "phone_swipe"
description = "在手机屏幕上滑动（坐标范围 0-999）"
parameters = {start_x, start_y, end_x, end_y: int}
```

**`phone_launch`** — 启动应用

```python
name = "phone_launch"
description = "启动手机应用"
parameters = {app_name: str}
# 内部使用 APP_PACKAGES 映射表
```

**`phone_back`** / **`phone_home`** — 导航

```python
# 简单操作，无参数
```

**`phone_long_press`** / **`phone_double_tap`** — 手势

**`phone_wait`** — 等待页面加载

所有工具共享设备配置（device_id, device_type），通过构造函数注入。屏幕尺寸在 screenshot 时获取并缓存，供坐标转换使用。

### Phase 2: Profile 化的子 Agent 框架

Phase 1 已完成，当前手机设备工具已经能够在 `nanobot` 中独立运行并通过真机验证。下一步不再新建一套平行的 agent 框架，而是将现有 `SubagentManager` 从“写死的通用子任务执行器”升级为“支持 profile 的专用子 agent 容器”。

核心判断：

- `subagent` 的生命周期管理能力（spawn / cancel / announce）已经足够复用。
- 当前不足的地方不是“没有新的 agent 类型”，而是 `SubagentManager` 里把工具集、prompt、provider/model、循环方式都写死了。
- phone-agent 只是一个 **专用 subagent profile**，不是第二套独立框架。

#### 2.1 New: `nanobot/nanobot/agent/subagent_profiles.py`

新增 `SubagentProfile`，用一个轻量 dataclass 描述“一类子 agent 的全部配置”。

```python
@dataclass
class SubagentProfile:
    """定义一类子 agent 的全部配置。"""

    name: str
    build_tools: Callable[[], list[Tool]]
    system_prompt: str | Callable[[], str]
    provider: LLMProvider | None = None
    model: str | None = None
    max_iterations: int = 15
    loop_mode: Literal["tool_calling", "text_parsing"] = "tool_calling"
```

字段约定：

- `build_tools`
  - 每次 `spawn` 都重新创建一组 tool 实例，避免共享运行时状态。
- `system_prompt`
  - 可传静态字符串，也可传动态构建函数。
- `provider`
  - `None` 表示复用主 agent 的 provider。
- `model`
  - `None` 表示使用 provider 默认模型。
- `loop_mode`
  - 默认为 `tool_calling`。
  - 未来如果确实需要兼容 `do()/finish()` 文本动作模型，再走 `text_parsing` 分支。

#### 2.2 Modify: `nanobot/nanobot/agent/subagent.py`

`SubagentManager` 继续只管子任务生命周期，不承担 phone 专有逻辑。新增 profile 注册和分发：

```python
self._profiles: dict[str, SubagentProfile] = {}

def register_profile(self, profile: SubagentProfile) -> None: ...

async def spawn(..., profile: str = “default”) -> str: ...
```

`_run_subagent()` 内部改为从 profile 获取工具/prompt/provider/迭代次数，不再硬编码：

```python
async def _run_subagent(self, task_id, task, label, origin, profile_name):
    profile = self._profiles[profile_name]
    tools = ToolRegistry()
    for tool in profile.build_tools():
        tools.register(tool)
    system_prompt = profile.system_prompt if isinstance(profile.system_prompt, str) \
                    else profile.system_prompt()
    provider = profile.provider or self.provider
    model = profile.model or provider.get_default_model()
    max_iterations = profile.max_iterations
    # ... 后续循环逻辑不变
```

原有 `_build_subagent_prompt()` 保留作为 default profile 的 prompt 构建器。

内部职责保持清晰：

- `SubagentManager`
  - 管 `spawn`
  - 管 `task_id`
  - 管 session 取消
  - 管结果回传主 agent
- `SubagentProfile`
  - 定义”这个子 agent 用什么工具、什么 prompt、什么模型、跑多少轮”

当前默认需要两个 profile：

| profile | tools | prompt | provider | max_iterations |
| ------- | ----- | ------ | -------- | -------------- |
| `default` | 文件 / shell / web | 通用 subagent prompt | 复用主 agent | 15 |
| `phone` | `phone_screenshot` / `phone_tap` / `phone_type` / ... | 手机操作专用 prompt | 独立多模态 provider | 50 |

#### 2.3 关于文本解析模式的放置

当前最优路径仍然是 **tool calling 优先**。  
如果后续确实要兼容不支持 function calling 的模型，再通过 `loop_mode` 在 `SubagentManager._run_subagent()` 内部增加分支。

这里采用 `loop_mode` 而不是让 profile 完全接管 `run()`，原因是：

- 文本解析模式和 tool calling 模式，本质上都还是同一个子任务生命周期。
- `spawn / cancel / announce / session` 不应该被不同运行器打散。
- 当前已知模式只有两类，`if/else` 分支比过早引入完整 runner 协议更稳。

也就是说：

- 当前阶段：`profile-first`
- 未来必要时：在 profile 内增加 `loop_mode="text_parsing"`
- 暂不需要为了一个潜在分支就再造一层平行 runner 框架

#### 2.4 New: `nanobot/nanobot/agent/tools/phone_agent.py` — 高层 PhoneAgentTool

主 agent 不直接看到 profile 细节，只暴露一个高层工具：

```python
class PhoneAgentTool(Tool):
    name = "phone_agent"
    description = "在连接的手机上执行多步操作任务。适用于打开应用、发消息、浏览内容、点按界面等场景。"
    parameters = {task: str, context: str (optional)}
    execute() -> self._manager.spawn(..., profile="phone")
```

这样主 agent 的认知负担最小：

- 它只知道“把手机任务交给 phone_agent”
- 不需要知道 phone tools 列表
- 不需要知道多模态 provider 配置
- 不需要知道 profile 注册细节

### Phase 3: 配置与接线

#### 3.1 `nanobot/nanobot/config/schema.py` — 已完成

`PhoneAgentConfig` 已存在，字段完备（provider、base_url、api_key、model、device 配置等）。
Phase 2 不需要改动 schema。

#### 3.2 Modify: `nanobot/nanobot/agent/loop.py`

核心改动：

1. **移除 phone tools 的直接注册**：当前 `_register_default_tools()` 在 `phone_config.enable` 时把 phone tools 直接注册到主 agent。这与 phone subagent 方案冲突——主 agent 不应直接持有 phone tools，否则 LLM 会同时看到底层 phone 工具和高层 PhoneAgentTool。

   ```python
   # 删除这段：
   if self.phone_config.enable:
       from nanobot.agent.tools.phone import build_phone_toolset
       for tool in build_phone_toolset(self.phone_config):
           self.tools.register(tool)
   ```

2. **为 phone profile 创建独立的多模态 Provider**：从 `PhoneAgentConfig` 构建 `CustomProvider` 实例，配置独立的 `GenerationSettings`：

   ```python
   if self.phone_config.enable:
       from nanobot.providers.custom_provider import CustomProvider
       from nanobot.providers.base import GenerationSettings

       phone_provider = CustomProvider(
           api_key=self.phone_config.api_key,
           api_base=self.phone_config.base_url,
           default_model=self.phone_config.model,
           extra_headers=self.phone_config.extra_headers,
       )
       phone_provider.generation = GenerationSettings(
           temperature=self.phone_config.temperature,
           max_tokens=self.phone_config.max_tokens,
           reasoning_effort=self.phone_config.reasoning_effort,
       )
   ```

3. **注册两个 profile**：

   ```python
   from nanobot.agent.subagent_profiles import SubagentProfile

   # default profile: 复用现有逻辑
   self.subagents.register_profile(SubagentProfile(
       name="default",
       build_tools=self._build_default_subagent_tools,
       system_prompt=self.subagents._build_subagent_prompt,
   ))

   # phone profile: 独立 provider + phone tools + 专用 prompt
   if self.phone_config.enable:
       phone_cfg = self.phone_config  # 闭包捕获

       self.subagents.register_profile(SubagentProfile(
           name="phone",
           build_tools=lambda: build_phone_toolset(phone_cfg),
           system_prompt=PHONE_SYSTEM_PROMPT,  # 静态字符串
           provider=phone_provider,
           model=phone_cfg.model,
           max_iterations=phone_cfg.max_steps,
       ))
   ```

4. **条件注册 `PhoneAgentTool`**（取代直接注册 phone tools）：

   ```python
   if self.phone_config.enable:
       from nanobot.agent.tools.phone_agent import PhoneAgentTool
       self.tools.register(PhoneAgentTool(manager=self.subagents))
   ```

5. **`_set_tool_context` 添加 `"phone_agent"`**：

   ```python
   for name in ("message", "spawn", "cron", "phone_agent"):
   ```

#### 3.3 `nanobot/nanobot/cli/commands.py` — 无需改动

`phone_config` 已经传入 AgentLoop（两处）。phone smoke / doctor 等 CLI 命令直接使用底层 phone tools，不经过 subagent，无需修改。

### Phase 4: System Prompt 适配

`phone` profile 使用手机专用 system prompt。当前优先支持 `tool_calling` 模式，对应 prompt 需要强调：

```
你是一个手机操作助手。通过调用工具来完成用户的手机操作任务。
每次操作前，先调用 phone_screenshot 查看当前屏幕状态。
根据截图内容决定下一步操作，调用对应的工具（phone_tap, phone_type 等）。
坐标范围 0-999，(0,0) 是左上角，(999,999) 是右下角。
任务完成后，直接用文字回复最终结果。
[+ 保留手机操作场景需要的核心约束]
```

如果未来需要 `text_parsing` 模式，再补一版文本动作格式的 prompt，并在 `loop_mode="text_parsing"` 分支中执行：

- 先截图
- 将截图作为上下文发送给模型
- 解析文本动作
- 映射到 `phone_*` tools
- 继续下一轮

这里保留扩展口，但不让它主导当前实现复杂度。

## File Summary

| 文件 | 操作 | 说明 |
| ---- | ---- | ---- |
| `nanobot/agent/tools/phone/__init__.py` | **已完成** | 手机工具包 |
| `nanobot/agent/tools/phone/screenshot.py` | **已完成** | `PhoneScreenshotTool` |
| `nanobot/agent/tools/phone/actions.py` | **已完成** | `PhoneTapTool`、`PhoneTypeTool`、`PhoneSwipeTool` 等 |
| `nanobot/agent/tools/phone/navigation.py` | **已完成** | `PhoneLaunchTool`、`PhoneBackTool`、`PhoneHomeTool` |
| `nanobot/agent/tools/phone_agent.py` | **新建** | 主 agent 的高层手机任务入口（PhoneAgentTool） |
| `nanobot/agent/subagent_profiles.py` | **新建** | `SubagentProfile` dataclass 定义 |
| `nanobot/agent/subagent.py` | **修改** | profile 注册、分发；`_run_subagent` 从 profile 获取配置 |
| `nanobot/agent/loop.py` | **修改** | 移除 phone tools 直接注册 → 改为 PhoneAgentTool；创建 phone provider；注册 default/phone profile |
| `nanobot/config/schema.py` | **无需修改** | PhoneAgentConfig 已完备 |
| `nanobot/cli/commands.py` | **无需修改** | phone_config 已传入 AgentLoop；CLI smoke/doctor 直接使用底层 tools |

## Implementation Order

1. **手机工具集**（Phase 1，已完成）— 底层设备工具和真机验证
2. **SubagentProfile 定义**（Phase 2.1）— 建立轻量 profile dataclass
3. **SubagentManager 扩展**（Phase 2.2）— profile 注册/分发，`_run_subagent` 改为 profile 驱动
4. **PhoneAgentTool**（Phase 2.4）— 主 agent 的高层入口，调用 `spawn(profile="phone")`
5. **loop.py 接线**（Phase 3.2）— 移除 phone tools 直接注册、创建 phone provider、注册 profiles、注册 PhoneAgentTool
6. **phone system prompt**（Phase 4）— 手机操作专用 prompt
7. **text_parsing 预留**（Phase 2.3）— 仅在确实需要时启用 `loop_mode="text_parsing"`

## Verification

1. **Phase 1 回归**：保留现有 phone tools 的单元测试和真机 smoke 测试（CLI `phone smoke` 直接使用底层 tools，不受 subagent 重构影响）
2. **Profile 单元测试**：验证 `default` / `phone` profile 的工具构建、provider 选择、prompt 构建是否正确
3. **SubagentManager 集成测试**：验证 `spawn(..., profile=”phone”)` 能正确分发到 phone profile，使用 phone provider 而非主 agent provider
4. **phone_agent 端到端测试**：配置 `phone_agent.enable=true`，发送”打开微信”，验证主 agent 调用 PhoneAgentTool → spawn phone subagent → phone tools 执行 → 结果回传的完整链路
5. **主 agent 工具隔离验证**：确认主 agent 的 tools 中不再包含底层 phone_* tools，仅包含高层 `phone_agent` tool
6. **文本解析预留测试**：仅在启用 `loop_mode=”text_parsing”` 时补对应测试，不提前实现假分支
