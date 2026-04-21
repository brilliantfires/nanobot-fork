# nanobot 全局优化调研报告

日期：2026-04-17

## 1. 结论摘要

这次审计的核心结论有 3 个。

第一，`SubagentProfile` 本身是一个正确但并不新颖的抽象。它解决了“不同子 agent 不该共用同一套 system prompt 和工具集”的问题，但当前实现仍然是静态 profile 注册和静态路由，创新空间并不在“再加几个 profile”，而在“让主 agent 能基于任务类型、风险等级、上下文负载和预期输出，选择合适的 delegation contract”。真正有价值的方向不是更多 prompt，而是更强的任务路由、能力裁剪、输入输出约束和观测闭环。

第二，“让主 agent 在创建子 agent 时决定工具集/能力包”是有用的，但不能直接等同于“把原始工具列表交给模型自由组合”。对 nanobot 来说，更合理的是混合模式：

- 高风险、强约束、强副作用领域保留显式 specialist tool，例如 `phone_agent`
- 通用后台任务引入受限的 `capability_bundle` 或 `task_type`
- 不建议第一阶段把 `allowed_tools=["read_file", "exec", ...]` 这种原始接口直接暴露给模型

第三，当前 `MEMORY.md + HISTORY.md` 方案的主要瓶颈不是“文件会变大”，而是“记忆读写都过于粗粒度”。`MEMORY.md` 每轮整份注入 prompt，consolidation 时又要求模型返回完整 `memory_update` 重写长期记忆；`HISTORY.md` 只支持 grep 式回忆；整个系统没有命名空间、类型、检索层、冲突处理和写入策略。这个方案在早期够用，但长期一定先卡在 recall 精度、更新成本和 prompt 膨胀，而不是磁盘容量。

综合“创新性 + 工程收益 + 实现成本”的平衡，最值得优先投入的 3 个方向是：

1. 记忆系统分层：把“存储后端 / 检索器 / prompt 投影”拆开
2. 子 agent 路由升级：从静态 profile 走向能力包和结构化 delegation
3. 并发模型升级：去掉全局串行锁，改为 session 级或 actor-like 并发

## 2. 现状诊断

### 2.1 Agent Specialization：已经有 profile，但还停留在静态配置层

当前仓库已经具备 `SubagentProfile` 抽象，包含：

- `build_tools`
- `system_prompt`
- `provider`
- `model`
- `max_iterations`
- `loop_mode`
- `prepare_round_state`
- `build_round_messages`

代码证据：

- `nanobot/agent/subagent_profiles.py:55`
- `nanobot/agent/subagent_profiles.py:78`

但当前 specialization 仍然是静态的：

- `SubagentManager` 初始化时只注册 `default` profile，`AgentLoop` 再额外注册 `phone` profile
- `spawn()` 接口虽然内部支持 `profile` 参数，但对主 agent 暴露的 `SpawnTool` 只接受 `task` 和 `label`
- `phone_agent` 是单独的高层工具，并在内部硬编码 `profile="phone"`

代码证据：

- `nanobot/agent/subagent.py:51`
- `nanobot/agent/subagent.py:66`
- `nanobot/agent/subagent.py:235`
- `nanobot/agent/tools/phone_agent.py:101`
- `nanobot/agent/tools/phone_agent.py:107`

这意味着当前系统的 specialization 逻辑是：

- 架构层知道有哪些 specialist
- 主 agent 只能在“通用 spawn”与“显式 specialist tool”之间选
- 主 agent 还不能对 generic subagent 指定能力边界、预期输出格式、风险级别或输入裁剪策略

因此，当前的 `SubagentProfile` 更接近“静态运行模板”，还不是“动态 delegation policy”。

### 2.2 phone profile 的价值不在“prompt 不一样”，而在“专用执行回路”

`phone` profile 之所以明显优于默认 subagent，不是单纯因为它有一段手机版 prompt，而是它同时具备下面几种专用机制：

- 独立 provider / model
- 独立工具集
- 每轮自动截图
- 每轮重建消息，而不是无约束累积历史
- 多模态 observation 注入

代码证据：

- `nanobot/agent/loop.py:175`
- `nanobot/agent/phone_prompt.py:10`
- `nanobot/agent/phone_prompt.py:144`

这说明 nanobot 已经验证了一件重要的事：真正有用的 specialist，不只是“更换 system prompt”，而是“为一个任务域设计专门的 observation loop、状态压缩方式和动作约束”。

换句话说，phone profile 的可迁移价值在于：

- 任务域专属上下文模板
- 任务域专属工具面
- 任务域专属状态准备器
- 任务域专属完成条件

这比“再多加几个 prompt”更值得抽象。

### 2.3 Tool Routing：当前 generic spawn 工具面过宽，且缺少结构化路由信息

默认 subagent 工具集固定包含：

- `read_file`
- `write_file`
- `edit_file`
- `list_dir`
- `exec`
- `web_search`
- `web_fetch`

代码证据：

- `nanobot/agent/subagent.py:207`

当前问题不在于这套工具不能用，而在于它对各种 generic task 都一视同仁：

- 研究型任务只需要 `web_*`
- 文件改写型任务未必需要 `web_*`
- 安全敏感型任务可能不该默认带 `exec`
- 大量工具同时暴露会增加动作熵和 prompt 负担

而 `SpawnTool` 又没有传递结构化意图：

- 没有 `task_type`
- 没有 `capability_bundle`
- 没有 `expected_output`
- 没有 `needs_approval`
- 没有 `risk_level`

当前接口实际上是“单 dispatch tool + 自然语言任务描述”，但没有把 dispatch policy 产品化。

### 2.4 Memory：当前方案的问题是读写粒度，而不是文件形式本身

当前记忆系统由两层组成：

- `MEMORY.md`：长期事实，始终加载到上下文
- `HISTORY.md`：事件日志，不进入 prompt，只供 grep

代码证据：

- `nanobot/agent/memory.py:82`
- `nanobot/agent/memory.py:83`
- `nanobot/agent/memory.py:98`
- `nanobot/skills/memory/SKILL.md:4`
- `nanobot/skills/memory/SKILL.md:11`

Consolidation 机制是：

- 当 prompt token 估算超过阈值时，归档旧消息
- 归档调用同一个 LLM，让它通过 `save_memory` 返回 `history_entry` 和 `memory_update`
- `history_entry` 追加到 `HISTORY.md`
- `memory_update` 用于整份重写 `MEMORY.md`

代码证据：

- `nanobot/agent/memory.py:25`
- `nanobot/agent/memory.py:125`
- `nanobot/agent/memory.py:139`
- `nanobot/agent/memory.py:189`
- `nanobot/agent/memory.py:192`
- `nanobot/agent/memory.py:302`

这个设计的根本问题有 5 个。

1. `MEMORY.md` 是全文注入。随着长期记忆变长，每轮都会带入更多无关事实。
2. `memory_update` 是整份重写。记忆越长，单次 consolidation 越像“全量重建数据库”。
3. `HISTORY.md` 只有 grep，没有结构化 retrieval。
4. 没有 namespace。用户偏好、项目事实、会话事件和系统状态都混在一起。
5. 没有 memory typing。事实、偏好、procedural memory、episodic memory 没有区分，导致后续无法做差异化检索或写入策略。

所以当前 memory 模型的问题不是 Markdown 本身，而是它既承担了“人类可读投影”，又承担了“唯一事实源”和“唯一检索入口”。

### 2.5 Context：当前 system prompt 叠加层次偏多，长期会放大 prompt 膨胀

`ContextBuilder` 每轮会叠加：

- 身份与环境说明
- `AGENTS.md` / `SOUL.md` / `USER.md` / `TOOLS.md`
- `MEMORY.md`
- always skills 正文
- skills summary
- runtime context

代码证据：

- `nanobot/agent/context.py:19`
- `nanobot/agent/context.py:35`
- `nanobot/agent/context.py:43`
- `nanobot/agent/context.py:47`
- `nanobot/agent/context.py:53`
- `nanobot/agent/context.py:154`

其中一个容易被忽视的点是：memory skill 本身是 `always: true`。

代码证据：

- `nanobot/skills/memory/SKILL.md:4`

这意味着除了 `MEMORY.md` 内容本身进入 prompt，关于“如何使用 memory”的说明文本也会稳定进入 prompt。单看不大，但这类常驻说明叠加起来，会让系统越来越依赖 prompt budget，而不是能力分层。

### 2.6 Concurrency：当前主 AgentLoop 是全局串行

`AgentLoop._dispatch()` 在全局 `_processing_lock` 下处理所有入站消息。

代码证据：

- `nanobot/agent/loop.py:118`
- `nanobot/agent/loop.py:548`

这会带来几个直接后果：

- 多 channel、多 chat 之间互相阻塞
- 一个长工具回合会拖慢所有会话
- subagent 完成后的 system 回注仍然需要进入同一个全局锁
- memory consolidation 虽然部分后台化，但主链路仍然是全局串行

对当前轻量形态来说，这种设计实现简单、行为稳定；但对后续“更多通道 + 更多后台 agent + 更复杂 specialist”会很快成为吞吐瓶颈。

### 2.7 Observability：当前日志足够开发，不足以支持复杂调度优化

当前系统有日志，但没有统一的结构化 tracing 抽象：

- subagent 的结果会被重新包装成自然语言 system message
- 主 agent 再次总结后发给用户
- 中间的任务路由、工具裁剪、子 agent 中间状态没有稳定的结构化事件模型

这对当前简单系统是可以接受的，但如果未来要做：

- 动态 capability bundle
- delegation 成功率评估
- prompt 策略 AB
- memory write policy 评估

那么日志就不够了，需要可归档、可统计、可重放的事件流。

### 2.8 配置与安全卫生：当前存在一个高优先级问题

`PhoneAgentConfig` 在 schema 默认值里带了一个看起来像真实 secret 的 `api_key`。

代码证据：

- `nanobot/config/schema.py:139`

无论它是否仍有效，这都属于需要立即清理的安全卫生问题。它不属于“研究创新”，但属于“当前仓库必须先修”的高优先级工程项。

## 3. 外部对标摘要

这部分只对照少量官方文档，用来帮助判断 nanobot 的演进方向，不做框架综述。

### 3.1 OpenAI Agents SDK

官方文档显示，OpenAI Agents SDK 在多 agent 编排上重点强调 4 件事：

- handoff 本质上是工具
- agents 也可以作为工具，不必总是 handoff
- tool-agent 支持结构化输入、审批、输出提取和条件启用
- session memory 与 model input merge 是可配置的

官方资料：

- Handoffs: <https://openai.github.io/openai-agents-python/handoffs/>
- Tools: <https://openai.github.io/openai-agents-python/tools/>
- Sessions: <https://openai.github.io/openai-agents-python/sessions/>
- Handoff prompt helper: <https://openai.github.io/openai-agents-python/ref/extensions/handoff_prompt/>

对 nanobot 最有启发的点有 4 个。

1. Handoff / specialist routing 不只是“换 agent”，还包括对 handoff 描述、输入 schema、输入过滤和运行时启用策略的设计。
2. `agent.as_tool()` 允许把 specialist 暴露成工具，而不是只能走 conversation ownership transfer。
3. tool-agent 支持 `parameters`、`custom_output_extractor`、`needs_approval`、`is_enabled`。这说明“主 agent 选择 specialist”这件事，成熟做法往往不是把原始工具表裸露给模型，而是把 specialist 封成高层能力。
4. sessions 支持自定义存储、检索限制和输入 merge callback，说明 memory 不应该被写死成单一全文投影。

特别相关的官方表述：

- OpenAI 将 handoff 定义为“represented as tools to the LLM”
- OpenAI 将 agents-as-tools 定义为“without a full handoff”
- OpenAI session 支持 `session_input_callback` 以自定义 history merge
- OpenAI 还提供推荐的 handoff prompt prefix，而不是只靠用户自己发明 prompt 约定

### 3.2 LangChain / LangGraph

官方文档最有价值的不是 API，而是它明确把 subagent routing 和 long-term memory 都做成了“模式选择题”。

官方资料：

- Subagents: <https://docs.langchain.com/oss/python/langchain/multi-agent/subagents>
- Long-term memory: <https://docs.langchain.com/oss/python/langchain/long-term-memory>

对 nanobot 最重要的两个启发：

1. LangChain 明确区分 `tool per agent` 和 `single dispatch tool`
2. LangGraph 的 long-term memory 不是一份大文本，而是 namespace/key 组织的文档存储，并通过 store 做检索

这跟 nanobot 当前状态形成了非常直接的映射：

- nanobot 现在的 `phone_agent` 更像 tool-per-agent
- nanobot 现在的 `spawn` 更像 single dispatch tool
- 但 nanobot 还没有把这两种模式统一成清晰的产品层策略

LangChain 文档还指出，single dispatch tool 适合：

- agent 数量多
- 团队分布式开发
- 希望增加新 agent 时不改 coordinator
- 重视上下文隔离

这说明“让主 agent 决定工具包/能力包”确实有现实价值，但前提是：

- registry 清晰
- 调度信息显式
- specialist 描述足够好

### 3.3 AutoGen

AutoGen 官方文档给 nanobot 的启发主要在并发和可观测性，而不在 prompt。

官方资料：

- Agents: <https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/tutorial/agents.html>
- Core: <https://microsoft.github.io/autogen/stable/user-guide/core-user-guide/index.html>

最相关的点：

- `AgentTool` 明确支持 agent-as-tool
- 使用 `AgentTool` / `TeamTool` 时必须关闭 parallel tool calls，避免状态冲突
- AutoGen Core 把“异步消息、可扩展、可观测、可调试”作为基础能力

这说明多 agent 系统一旦变复杂，问题会很快从“prompt 怎么写”转移到：

- 并发边界
- 生命周期
- tracing
- 状态隔离

nanobot 当前在这些方面仍然明显更轻，也因此更容易理解，但要继续向上扩展，就不能一直停留在“全局锁 + 文本回注 + logs”这一层。

## 4. 对三个核心问题的直接回答

### 问题 1：现在的 `SubagentProfile` 只是静态 profile，创新空间到底在哪里？

创新空间不在“再抽象一层 profile”，而在下面 4 个方向。

1. 路由策略从静态配置升级为运行时 policy
2. specialist 的输入输出从自然语言升级为结构化 contract
3. specialist 的工具面从固定全集升级为 capability bundle
4. specialist 的执行回路从统一 loop 升级为域专属 observation / completion loop

更直白地说：

- “不同 agent 用不同 prompt”不是创新点
- “不同任务类型触发不同上下文裁剪、工具裁剪、结果抽取和审批策略”才有更高价值

所以当前 `SubagentProfile` 不是没用，而是只完成了第一步。

### 问题 2：让主 agent 在创建子 agent 时决定工具集/能力包，是否真的有用？

有用，但要区分任务类型。

适合的任务：

- 通用研究任务
- 文件/Web/exec 混合任务
- 需要隔离上下文但风险中等的后台任务
- specialist 数量较多、无法为每个 specialist 都单独暴露一个工具的场景

不适合直接放开原始工具决策的任务：

- 手机 GUI 操作
- 付款、登录、设备控制
- 高副作用 shell 操作
- 强审批约束任务

推荐方案是混合式：

- 保留显式 specialist tool：`phone_agent`
- 为 generic subagent 增加 `capability_bundle`
- capability bundle 由代码维护，模型只选 bundle，不直接选底层工具

推荐的最小接口不是：

```text
spawn(task, allowed_tools=[...])
```

而是：

```text
spawn(
  task,
  capability_bundle="research" | "workspace_ops" | "web_only",
  expected_output="brief" | "json" | "patch_summary"
)
```

这样做的好处是：

- 降低模型动作熵
- 保留系统可控性
- 便于统计不同 bundle 的成功率
- 后续能平滑扩展到审批、输出提取和 tracing

### 问题 3：当前 `MEMORY.md + HISTORY.md` 为什么长期会失效，升级路径是什么？

它会失效，不是因为 Markdown 不行，而是因为它把 3 个不同职责揉到了一起：

- 人类可读摘要
- 模型输入上下文
- 机器检索底座

长期失效的具体表现会按这个顺序出现：

1. `MEMORY.md` 越来越长，系统 prompt 噪声上升
2. consolidation 时模型需要全量重写长期记忆，更新成本上升
3. `HISTORY.md` 只能 grep，跨主题 recall 质量下降
4. 缺少 typed memory，无法做按类别检索和冲突管理
5. 会话、用户、项目、环境状态混杂，后续无法做 namespace-aware recall

推荐升级路径分 3 阶段。

阶段 1：

- 引入 `MemoryBackend` 和 `MemoryRetriever` 抽象
- 保留 `MEMORY.md` / `HISTORY.md`，但把它们降级为 projection
- 新的真实存储先用本地 JSONL / SQLite 都可以

阶段 2：

- memory entry typed 化
- 增加 namespace：`user/`, `workspace/`, `project/`, `session/`, `procedural/`
- prompt 只注入检索命中的小片段，不再全文注入 `MEMORY.md`

阶段 3：

- 增加更强 retrieval：关键词 + 元数据 + 可选语义检索
- 增加 memory write policy、过期/合并策略、冲突修复

简言之，最合理的终态不是“没有 Markdown”，而是“Markdown 只是人类视图，不是唯一事实源”。

## 5. 优化候选优先级表

| 排名 | 候选项 | 创新性 | 工程收益 | 实现成本 | 综合判断 |
| --- | --- | --- | --- | --- | --- |
| 1 | 记忆系统分层：`MemoryBackend + Retriever + Projection` | 高 | 很高 | 中高 | 最值得做 |
| 2 | 子 agent 路由升级：`capability_bundle + structured delegation` | 中高 | 很高 | 中 | 最值得做 |
| 3 | 并发模型升级：从全局锁到 session 级并发 | 中 | 很高 | 中高 | 很值得做 |
| 4 | Prompt 分层：delegation prompt / execution prompt / task template | 中 | 高 | 中 | 应尽快跟进 |
| 5 | 结构化 tracing 与 subagent 事件模型 | 中 | 高 | 中 | 值得原型验证 |
| 6 | 配置与安全卫生清理 | 低 | 高 | 低 | 立即修 |
| 7 | generic spawn 的状态查询 / 输出提取 / 审批接口 | 中 | 中高 | 中 | 值得原型验证 |
| 8 | 完整 swarm / 多 agent 群聊拓扑 | 中高 | 中 | 高 | 暂不优先 |

## 6. Top 3 详细建议

### 6.1 排名 1：记忆系统分层

**问题定义**

当前记忆系统把“存储、检索、投影”揉在一起，导致长期记忆越大，prompt 越臃肿，更新越昂贵，检索越粗糙。

**为什么现状会卡住**

- `MEMORY.md` 全量进入 prompt
- consolidation 输出 `memory_update` 时要求整份长期记忆重写
- `HISTORY.md` 只能靠 grep
- 没有 namespace 和类型

**预期收益**

- prompt 明显变短
- recall 更精准
- 记忆可扩展到多会话、多项目
- 后续更容易加语义检索或 UI

**创新性判断**

这不是学术创新，但对 nanobot 来说是“从 demo memory 到可扩展 memory”的关键跃迁，研究价值和工程价值都高。

**实现风险**

- 迁移时要保持已有 `MEMORY.md` / `HISTORY.md` 兼容
- retrieval 质量如果不稳定，体验可能先变差
- 写入策略过于激进会污染 memory store

**下一步最小验证方案**

- 第一步不引入向量库
- 先做本地 `MemoryEntry` 存储层，支持 `type / namespace / key / content / updated_at`
- prompt 侧只检索少量命中项
- 继续同步产出 `MEMORY.md` / `HISTORY.md` 作为人类可读视图

### 6.2 排名 2：子 agent 路由升级

**问题定义**

当前只有两种路径：通用 `spawn` 和显式 specialist tool。generic spawn 工具面固定过宽，specialist 又是硬编码工具。

**为什么现状会卡住**

- `SpawnTool` 没有结构化路由字段
- generic subagent 无法按任务裁剪工具集
- 主 agent 不能表达“我要一个 research specialist，但不需要写文件和 exec”

**预期收益**

- 降低 tool confusion
- 减少无关工具进入 prompt
- 更容易扩展多个 specialist
- 后续能统计不同 bundle 的路由成功率

**创新性判断**

单纯“让模型自己选工具”不新；但“主 agent 选择 capability bundle，系统再生成受控 specialist 运行环境”对 nanobot 很有价值，也更符合当前轻量架构。

**实现风险**

- bundle 设计太细会增加维护成本
- bundle 设计太粗又没有收益
- 如果直接暴露原始 `allowed_tools`，安全和稳定性会变差

**下一步最小验证方案**

- 保持 `phone_agent` 不动
- 给 `spawn` 新增一个可选 `capability_bundle`
- 先只定义 3 个 bundle：`research`、`web_only`、`workspace_ops`
- 让 generic subagent prompt 感知当前 bundle 与完成标准

### 6.3 排名 3：并发模型升级

**问题定义**

当前主 loop 的 `_processing_lock` 会把所有会话串行化，这会限制多通道和多后台任务扩展。

**为什么现状会卡住**

- 一个长会话卡住全部会话
- background subagent 结果回注仍要排队
- 后续 specialist 增多后，吞吐问题会更明显

**预期收益**

- 多 chat 响应性提升
- 后台任务与前台对话干扰减少
- 更贴近 agent runtime / actor model 方向

**创新性判断**

工程收益很高，但创新性弱于 memory 和 routing。它更像“必要基础设施升级”。

**实现风险**

- 需要避免同一 session 并发写 session/history
- 需要重新审视 `/stop`、subagent 回注、streaming 顺序
- 某些 channel 可能隐含顺序依赖

**下一步最小验证方案**

- 先把全局锁改为 `session_key -> asyncio.Lock`
- 保证单 session 串行，多 session 并发
- 保持 memory consolidator 仍按 session 加锁
- 不要一步跳到完全 actor runtime

## 7. `should do now / worth prototyping / not worth now`

### should do now

- 清理 `PhoneAgentConfig` 中的默认 API key，补一轮 secret hygiene 检查
- 为 generic subagent 引入 `capability_bundle`，不要直接暴露原始 `allowed_tools`
- 为 memory 增加后端与检索抽象，停止把 `MEMORY.md` 当唯一事实源
- 把全局 `_processing_lock` 收窄到 session 级
- 把 prompt 分成 delegation prompt、execution prompt、profile task template 三层

### worth prototyping

- generic subagent 的结构化输出与 `custom output extractor` 风格接口
- subagent 的 `start/status/result` 三段式异步任务模型
- structured tracing：记录 delegation 决策、tool bundle、tool events、final outcome
- memory typed schema：`fact / preference / procedure / episode`

### not worth now

- 让主 agent 直接自由选择底层 raw tool 列表
- 在当前阶段引入完整 swarm / group chat 架构
- 先上向量数据库再考虑 memory typing 和 namespace
- 为每个领域都立刻造一个 specialist profile

## 8. 推荐的最小接口方向

### 8.1 子 agent 路由

不建议直接把公开接口变成：

```text
spawn(task, allowed_tools=[...])
```

更建议：

```text
spawn(
  task,
  capability_bundle: str | None = None,
  expected_output: str | None = None,
  label: str | None = None
)
```

默认语义：

- `capability_bundle=None`：继续走当前 default profile
- `capability_bundle="research"`：受限工具面 + research prompt 约束
- `capability_bundle="workspace_ops"`：允许文件和 shell，但默认不带 web

### 8.2 Prompt 分层

推荐分成 3 层：

- 主 agent delegation prompt：何时委派、委派给谁、期望什么结果
- specialist execution prompt：该 specialist 的领域规则和约束
- task template：本次任务的目标、边界、完成条件、输出格式

这比把所有规则都揉进一段 system prompt 更稳，也更便于后续评估。

### 8.3 Memory

推荐抽象为：

- `MemoryBackend`：真实存储
- `MemoryRetriever`：按 session/user/project 检索
- `MemoryProjector`：把命中记忆投影为 prompt context
- `MemoryExport`：把当前 memory 产出为 `MEMORY.md` / `HISTORY.md`

这样 Markdown 仍然保留，但退居为可读投影，而不是唯一真相。

## 9. 建议的实施顺序

如果只按平衡优先级推进，我建议顺序如下：

1. 立即修安全卫生：去掉硬编码 secret
2. 做 `capability_bundle` 的最小 generic spawn 升级
3. 把全局锁收窄到 session 级
4. 引入 memory backend/retriever 抽象
5. 最后再考虑 tracing 和更复杂 specialist 生态

这个顺序的原因是：

- 先控制风险
- 再提升 routing 质量
- 再解决吞吐瓶颈
- 最后做 memory 深改，避免在旧并发模型和旧路由接口上重复返工

## 10. 说明

本报告基于当前仓库源码、现有测试文件和少量官方文档对标完成。由于本地环境中缺少 `pytest` 可执行命令，本次没有跑通测试套件，判断主要来自静态代码审计与现有测试设计本身。
