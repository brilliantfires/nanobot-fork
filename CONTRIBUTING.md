# 参与贡献 nanobot

感谢你来到这里。

nanobot 的构建基于一个简单的信念：好的工具应当让人感到平静、清晰，并且有人味。
我们非常重视有用的功能，但也相信应该以更少的东西做成更多的事：
解决方案应当足够强大，但不要因此变得臃肿；应当有野心，但不要变得
不必要地复杂。

这份指南不仅仅是在说明如何提交 PR。它也表达了我们希望如何一起构建
软件：带着审慎、清晰，以及对下一个阅读代码之人的尊重。

## 维护者

| 维护者 | 负责方向 |
|------------|-------|
| [@re-bin](https://github.com/re-bin) | 项目负责人，`main` 分支 |
| [@chengyongru](https://github.com/chengyongru) | `nightly` 分支，实验性功能 |

## 分支策略

我们采用双分支模型，在稳定性与探索之间取得平衡：

| 分支 | 用途 | 稳定性 |
|--------|---------|-----------|
| `main` | 稳定发布 | 可用于生产 |
| `nightly` | 实验性功能 | 可能存在 bug 或破坏性变更 |

### 我应该向哪个分支提交？

**如果你的 PR 包含以下内容，请目标为 `nightly`：**

- 新功能或新增能力
- 可能影响现有行为的重构
- API 或配置项变更

**如果你的 PR 包含以下内容，请目标为 `main`：**

- 不改变行为的 bug 修复
- 文档改进
- 不影响功能的小调整

**如果不确定，就提交到 `nightly`。** 将一个稳定的想法从 `nightly`
迁移到 `main`，总比在稳定分支合入后再撤销一个高风险变更要容易。

### `nightly` 如何合并到 `main`？

我们不会整体合并 `nightly` 分支。相反，稳定的功能会从 `nightly`
中 **cherry-pick** 出来，单独提交 PR 到 `main`：

```
nightly  ──┬── feature A (stable) ──► PR ──► main
           ├── feature B (testing)
           └── feature C (stable) ──► PR ──► main
```

这个过程大约 **每周一次**，但具体时间取决于功能何时足够稳定。

### 快速总结

| 你的变更 | 目标分支 |
|-------------|---------------|
| 新功能 | `nightly` |
| Bug 修复 | `main` |
| 文档 | `main` |
| 重构 | `nightly` |
| 不确定 | `nightly` |

## 开发环境准备

保持准备过程平淡、可靠。目标是让你尽快进入代码：

```bash
# 克隆仓库
git clone https://github.com/HKUDS/nanobot.git
cd nanobot

# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
pytest

# 代码检查
ruff check nanobot/

# 代码格式化
ruff format nanobot/
```

## 代码风格

我们关注的不仅仅是通过 lint。我们希望 nanobot 始终保持小巧、平静、易读。

参与贡献时，请尽量让代码具备以下特质：

- 简单：优先选择能真正解决问题的最小改动
- 清晰：为下一个阅读者优化，而不是为了炫技
- 解耦：保持边界清楚，避免不必要的新抽象
- 诚实：不要掩盖复杂性，但也不要人为制造复杂性
- 持久：选择容易维护、测试和扩展的方案

在实践中：

- 行宽：100 个字符（`ruff`）
- 目标版本：Python 3.11+
- Lint：`ruff`，启用 E、F、I、N、W（忽略 E501）
- 异步：全程使用 `asyncio`；pytest 配置 `asyncio_mode = "auto"`
- 优先可读代码，而不是“魔法代码”
- 优先聚焦型补丁，而不是大范围重写
- 如果引入新抽象，它应当明确降低复杂度，而不是把复杂度挪到别处

## 有问题？

如果你有问题、想法，或还不够成熟的灵感，这里都欢迎你。

欢迎直接提 [issue](https://github.com/HKUDS/nanobot/issues)，加入社区，或直接联系：

- [Discord](https://discord.gg/MnCvHqpUGB)
- [飞书/微信](./COMMUNICATION.md)
- Email: Xubin Ren (@Re-bin) — <xubinrencs@gmail.com>

感谢你把时间和心力投入到 nanobot。我们真诚希望有更多人参与这个社区，也欢迎任何规模的贡献。
