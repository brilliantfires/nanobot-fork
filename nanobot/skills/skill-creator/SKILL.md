---
name: skill-creator
description: 创建或更新 AgentSkills。在设计、组织或打包包含脚本、参考资料和资源文件的技能时使用。
---

# Skill Creator

这个技能提供创建高质量技能的指导。

## 关于技能

技能是模块化、自包含的包，通过提供专门知识、工作流和工具来扩展 agent 的能力。
可以把它们理解为面向特定领域或任务的“入门指南”。
它们会把一个通用 agent 转变为一个具备程序性知识的专用 agent，而这些知识不可能完全依赖模型本身掌握。

### 技能能提供什么

1. 专门工作流 - 面向特定领域的多步骤流程
2. 工具集成 - 处理特定文件格式或 API 的指引
3. 领域知识 - 公司内部知识、数据模式、业务逻辑
4. 打包资源 - 用于复杂或重复任务的脚本、参考资料和资源文件

## 核心原则

### 简洁最重要

上下文窗口是一种公共资源。技能与系统提示词、对话历史、其他技能的元数据，以及当前用户请求共享同一个上下文窗口。

**默认前提：agent 已经非常聪明。** 只添加 agent 原本不知道的内容。对每一段信息都提出质疑：“agent 真的需要这段解释吗？”以及“这段内容值得它占用的 token 成本吗？”

优先使用简洁示例，而不是冗长解释。

### 设定合适的自由度

让具体程度与任务的脆弱性和变化性匹配：

**高自由度（纯文本说明）**：适用于多种做法都合理、决策依赖上下文，或更适合用启发式规则来指导时。

**中等自由度（伪代码或带参数的脚本）**：适用于存在推荐模式、允许一定变化，或行为会受配置影响时。

**低自由度（具体脚本、参数很少）**：适用于操作脆弱且易错、一致性非常重要，或必须严格遵循特定顺序时。

把 agent 想象成在探索一条路径：如果是两边都是悬崖的窄桥，就需要明确护栏（低自由度）；如果是开阔平原，就可以允许多条路线（高自由度）。

### 技能的构成

每个技能都包含一个必需的 `SKILL.md` 文件，以及可选的打包资源：

```
skill-name/
├── SKILL.md (required)
│   ├── YAML frontmatter metadata (required)
│   │   ├── name: (required)
│   │   └── description: (required)
│   └── Markdown instructions (required)
└── Bundled Resources (optional)
    ├── scripts/          - Executable code (Python/Bash/etc.)
    ├── references/       - Documentation intended to be loaded into context as needed
    └── assets/           - Files used in output (templates, icons, fonts, etc.)
```

#### SKILL.md（必需）

每个 `SKILL.md` 包含：

- **Frontmatter**（YAML）：包含 `name` 和 `description` 字段。agent 只会读取这些字段来判断何时触发技能，因此必须清楚且完整地描述技能是什么，以及何时应该使用它。
- **Body**（Markdown）：关于如何使用该技能的说明与指导。只有在技能触发之后才会加载。

#### 打包资源（可选）

##### 脚本（`scripts/`）

可执行代码（Python/Bash 等），适用于需要确定性可靠性，或经常被重复重写的任务。

- **何时包含**：当同样的代码会被反复重写，或需要确定性的可靠性时
- **示例**：用于 PDF 旋转任务的 `scripts/rotate_pdf.py`
- **好处**：节省 token、结果确定，而且很多时候无需先读入上下文即可执行
- **注意**：agent 有时仍需要读取脚本内容，以便修补或做环境相关调整

##### 参考资料（`references/`）

文档与参考材料，按需加载到上下文中，用于指导 agent 的处理过程和思考。

- **何时包含**：当 agent 在工作时需要参考某些文档
- **示例**：`references/finance.md`（财务数据结构）、`references/mnda.md`（公司 NDA 模板）、`references/policies.md`（公司政策）、`references/api_docs.md`（API 规格）
- **用途**：数据库 schema、API 文档、领域知识、公司政策、详细工作流指南
- **好处**：让 `SKILL.md` 保持精简，仅在 agent 判断需要时才加载
- **最佳实践**：如果文件较大（>10k 词），请在 `SKILL.md` 中附上 grep 搜索模式
- **避免重复**：信息应该只存在于 `SKILL.md` 或 references 文件之一，而不是两边都写。详细信息优先放进 references 文件，除非它真的是技能核心内容。这样既能让 `SKILL.md` 保持精简，又能让信息在需要时被发现，而不会长期占用上下文窗口。把真正必要的流程说明和工作流指导放在 `SKILL.md` 中，把细节参考、schema 和示例迁移到 references。

##### 资源文件（`assets/`）

这类文件不用于加载到上下文，而是直接用于 agent 的产出结果。

- **何时包含**：当技能需要一些会被用于最终输出的文件时
- **示例**：`assets/logo.png`（品牌资源）、`assets/slides.pptx`（PPT 模板）、`assets/frontend-template/`（HTML/React 模板）、`assets/font.ttf`（字体）
- **用途**：模板、图片、图标、样板代码、字体、会被复制或修改的示例文档
- **好处**：把输出资源与文档分离，使 agent 能直接使用文件而无需把它们加载到上下文中

#### 不要往技能里放什么

技能只应包含直接支撑其功能的必要文件。**不要**创建额外的文档或辅助文件，包括：

- README.md
- INSTALLATION_GUIDE.md
- QUICK_REFERENCE.md
- CHANGELOG.md
- 等等

技能应只包含 AI agent 完成当前任务所需的信息。不要加入关于技能是如何创建出来的过程说明、安装和测试流程、面向用户的文档等辅助性内容。这些额外文档只会增加混乱和负担。

### 渐进披露设计原则

技能使用三级加载系统来高效管理上下文：

1. **Metadata（名称 + 描述）** - 始终在上下文中（约 100 词）
2. **SKILL.md 正文** - 技能触发时加载（<5k 词）
3. **打包资源** - agent 按需使用（理论上无限，因为脚本可以在不读入上下文的情况下执行）

#### 渐进披露模式

将 `SKILL.md` 正文控制在必要内容范围内，并尽量少于 500 行，以减少上下文膨胀。接近这个规模时就应拆分到其他文件中。拆分时，一定要在 `SKILL.md` 中明确引用这些文件，并说明何时需要读取它们，确保技能使用者知道它们存在以及在什么情况下应该查看。

**关键原则：** 当一个技能支持多种变体、框架或选项时，只在 `SKILL.md` 中保留核心工作流和选择指引。把变体特定的细节（模式、示例、配置）移到单独的参考文件中。

**模式 1：高层指南 + 参考文件**

```markdown
# PDF Processing

## Quick start

Extract text with pdfplumber:
[code example]

## Advanced features

- **Form filling**: See [FORMS.md](FORMS.md) for complete guide
- **API reference**: See [REFERENCE.md](REFERENCE.md) for all methods
- **Examples**: See [EXAMPLES.md](EXAMPLES.md) for common patterns
```

agent 仅在需要时才会加载 `FORMS.md`、`REFERENCE.md` 或 `EXAMPLES.md`。

**模式 2：按领域组织**

对于支持多个领域的技能，应按领域组织内容，避免加载无关上下文：

```
bigquery-skill/
├── SKILL.md (overview and navigation)
└── reference/
    ├── finance.md (revenue, billing metrics)
    ├── sales.md (opportunities, pipeline)
    ├── product.md (API usage, features)
    └── marketing.md (campaigns, attribution)
```

当用户问销售指标时，agent 只读取 `sales.md`。

同理，对于支持多个框架或变体的技能，也应按变体组织：

```
cloud-deploy/
├── SKILL.md (workflow + provider selection)
└── references/
    ├── aws.md (AWS deployment patterns)
    ├── gcp.md (GCP deployment patterns)
    └── azure.md (Azure deployment patterns)
```

当用户选择 AWS 时，agent 只读取 `aws.md`。

**模式 3：条件性细节**

展示基础内容，并链接到进阶内容：

```markdown
# DOCX Processing

## Creating documents

Use docx-js for new documents. See [DOCX-JS.md](DOCX-JS.md).

## Editing documents

For simple edits, modify the XML directly.

**For tracked changes**: See [REDLINING.md](REDLINING.md)
**For OOXML details**: See [OOXML.md](OOXML.md)
```

只有当用户需要这些能力时，agent 才会去读 `REDLINING.md` 或 `OOXML.md`。

**重要指南：**

- **避免深层嵌套引用** - references 最好与 `SKILL.md` 保持一层引用关系。所有 reference 文件都应直接从 `SKILL.md` 链接到。
- **为较长 reference 文件加结构** - 对于超过 100 行的文件，请在顶部加入目录，便于 agent 预览时把握整体范围。

## 技能创建流程

创建技能一般包括以下步骤：

1. 通过具体示例理解技能
2. 规划可复用的技能内容（脚本、参考资料、资源文件）
3. 初始化技能（运行 `init_skill.py`）
4. 编辑技能（实现资源并撰写 `SKILL.md`）
5. 打包技能（运行 `package_skill.py`）
6. 根据真实使用情况迭代

请按顺序执行这些步骤，除非有明确理由表明某一步不适用。

### 技能命名

- 仅使用小写字母、数字和连字符；将用户提供的标题规范化为短横线风格（例如 `"Plan Mode"` -> `plan-mode`）。
- 生成名称时，长度控制在 64 个字符以内（字母、数字、连字符）。
- 优先使用简短、动词驱动的短语，准确描述动作。
- 如果按工具命名能提升清晰度或触发准确率，可加上命名空间（例如 `gh-address-comments`、`linear-address-issue`）。
- 技能目录名必须与技能名完全一致。

### 步骤 1：通过具体示例理解技能

仅当技能的使用模式已经非常明确时，才可以跳过这一步。即便是已有技能，这一步通常依然有价值。

要创建一个有效的技能，首先必须明确它会如何被使用。这个理解既可以来自用户直接提供的示例，也可以来自你生成并经用户验证的示例。

例如，在构建一个 image-editor 技能时，可能需要问：

- “image-editor 技能需要支持哪些能力？编辑、旋转，还是别的？”
- “你能给几个这个技能会被怎样使用的例子吗？”
- “我能想到用户可能会说‘帮我去掉这张图的红眼’或‘帮我旋转这张图’。你还会怎么用它？”
- “用户说什么样的话时，应该触发这个技能？”

为避免让用户感到负担，不要在一条消息中提太多问题。先问最重要的问题，再视情况继续追问，以提高有效性。

当你已经清楚这个技能应当支持什么功能时，就可以结束这一步。

### 步骤 2：规划可复用的技能内容

要把具体示例变成高质量技能，需要逐个分析示例：

1. 思考如果从零开始，该如何完成这个示例
2. 识别在反复执行这些工作流时，哪些脚本、参考资料和资源文件会有帮助

示例：当构建一个处理“帮我旋转这个 PDF”这类请求的 `pdf-editor` 技能时，分析结果可能是：

1. 旋转 PDF 每次都要重复写相同的代码
2. 适合在技能中存一个 `scripts/rotate_pdf.py` 脚本

示例：当设计一个处理“帮我做一个待办应用”或“帮我做一个记录步数的仪表盘”的 `frontend-webapp-builder` 技能时，分析结果可能是：

1. 编写前端 Web 应用时，每次都要重复写相同的 HTML/React 样板
2. 适合在技能里存放一个 `assets/hello-world/` 模板目录，包含这些样板项目文件

示例：当构建一个处理“今天有多少用户登录了？”这类请求的 `big-query` 技能时，分析结果可能是：

1. 查询 BigQuery 时，每次都要重新摸清表结构和关系
2. 适合准备一个记录表结构的 `references/schema.md`

为了确定技能内容，请逐个分析具体示例，并生成一份应纳入技能的可复用资源清单：脚本、参考资料、资源文件。

### 步骤 3：初始化技能

到这里，就该真正开始创建技能了。

仅当目标技能已经存在，只需要继续迭代或打包时，才可以跳过这一步。否则继续下一步。

如果是从零开始创建新技能，始终应运行 `init_skill.py` 脚本。这个脚本会自动生成一个模板化的技能目录，包含技能所需的一切基础结构，让技能创建过程更高效、更可靠。

对于 `nanobot`，自定义技能应位于当前工作区的 `skills/` 目录下，以便运行时自动发现（例如 `<workspace>/skills/my-skill/SKILL.md`）。

用法：

```bash
scripts/init_skill.py <skill-name> --path <output-directory> [--resources scripts,references,assets] [--examples]
```

示例：

```bash
scripts/init_skill.py my-skill --path ./workspace/skills
scripts/init_skill.py my-skill --path ./workspace/skills --resources scripts,references
scripts/init_skill.py my-skill --path ./workspace/skills --resources scripts --examples
```

该脚本会：

- 在指定路径创建技能目录
- 生成包含正确 frontmatter 和 TODO 占位符的 `SKILL.md` 模板
- 根据 `--resources` 可选创建资源目录
- 在设置 `--examples` 时可选生成示例文件

初始化之后，再按需定制 `SKILL.md` 并添加资源。如果你使用了 `--examples`，请替换或删除占位文件。

### 步骤 4：编辑技能

在编辑技能（无论是新生成的还是已有的）时，请记住：这个技能是给另一个 agent 实例使用的。应加入那些对 agent 有帮助且不显而易见的信息。思考哪些程序性知识、领域细节或可复用资源，可以帮助另一个 agent 实例更高效地完成这些任务。

#### 学习已验证的设计模式

根据技能需求，参考这些有用的指南：

- **多步骤流程**：查看 `references/workflows.md`，学习顺序工作流与条件逻辑
- **特定输出格式或质量标准**：查看 `references/output-patterns.md`，学习模板与示例模式

这些文件包含了已验证过的技能设计最佳实践。

#### 先实现可复用内容

开始实现时，优先落实前面识别出的可复用资源：`scripts/`、`references/`、`assets/`。注意，这一步可能需要用户输入。例如实现一个 `brand-guidelines` 技能时，用户可能需要提供品牌资源或模板放进 `assets/`，或提供文档放进 `references/`。

新增脚本后，必须实际运行测试，确保没有 bug，且输出符合预期。如果有很多类似脚本，只需测试一部分具有代表性的样本，以在时间与信心之间取得平衡。

如果你使用了 `--examples`，请删除那些对技能无用的占位文件。只创建真正需要的资源目录。

#### 更新 SKILL.md

**写作准则：** 始终使用祈使式 / 不定式风格。

##### Frontmatter

编写包含 `name` 和 `description` 的 YAML frontmatter：

- `name`：技能名称
- `description`：这是技能最主要的触发机制，帮助 agent 理解何时该使用它。
  - 同时描述技能“做什么”以及“在什么触发场景下使用”
  - 所有“何时使用”的信息都应写在这里，而不是正文中。正文只有在技能触发后才会被加载，所以正文里的 “When to Use This Skill” 这类章节对 agent 没有帮助。
  - `docx` 技能的 description 示例：`"Comprehensive document creation, editing, and analysis with support for tracked changes, comments, formatting preservation, and text extraction. Use when the agent needs to work with professional documents (.docx files) for: (1) Creating new documents, (2) Modifying or editing content, (3) Working with tracked changes, (4) Adding comments, or any other document tasks"`

保持 frontmatter 极简。在 `nanobot` 中，必要时也支持 `metadata` 和 `always`，但除非确实需要，否则不要加入额外字段。

##### 正文

编写关于如何使用技能及其打包资源的说明。

### 步骤 5：打包技能

技能开发完成后，必须将其打包成可分发的 `.skill` 文件，供用户共享使用。打包过程会先自动验证技能，确保它满足所有要求：

```bash
scripts/package_skill.py <path/to/skill-folder>
```

可选输出目录：

```bash
scripts/package_skill.py <path/to/skill-folder> ./dist
```

打包脚本会：

1. **自动验证**技能，检查：
   - YAML frontmatter 格式与必填字段
   - 技能命名约定与目录结构
   - 描述的完整性与质量
   - 文件组织与资源引用

2. **在验证通过后打包**，生成一个以技能名命名的 `.skill` 文件（例如 `my-skill.skill`），包含所有文件，并保持正确目录结构以便分发。`.skill` 本质上是一个以 `.skill` 为扩展名的 zip 文件。

   安全限制：如果存在任何符号链接，打包会被拒绝并失败。

如果验证失败，脚本会报告错误并退出，不会创建打包文件。修复这些问题后再重新执行打包命令。

### 步骤 6：迭代

技能经过测试后，用户可能会提出改进请求。很多时候，这发生在刚刚实际使用完技能之后，此时对技能表现的上下文还很新鲜。

**迭代工作流：**

1. 在真实任务中使用该技能
2. 观察哪里卡顿、低效或不顺手
3. 识别 `SKILL.md` 或打包资源应如何更新
4. 实施修改并再次测试
