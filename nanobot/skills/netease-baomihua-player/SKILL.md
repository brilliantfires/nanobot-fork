---
name: netease-baomihua-player
description: 通过 bmh 命令行工具操作网易爆米花 macOS 客户端。只要用户要在网易爆米花里搜索、查找、推荐、识别、播放、筛选、刮削，或提到 Emby/Jellyfin/FnOS/WebDAV/SMB/媒体库/网盘，就必须使用此 skill。它适用于 CLI 和 OpenClaw 一类 AI 外部调用场景，重点是先校验客户端状态，再按来源选择正确命令和参数，避免误把服务器内部 ID 当成 TMDB ID。
---

# 网易爆米花

## 适用边界

这个 skill 只解决“通过 `bmh` 控制网易爆米花客户端”。

- 用户要执行媒体操作：使用这个 skill
- 用户只是在问实现原理、接口设计、Swift/CLI 开发：优先做常规代码分析，不要硬套本 skill
- 用户既要操作客户端又要解释 CLI 行为：先按本 skill 完成操作，再补说明

## 默认工作方式

除非用户明确限制，否则始终按下面顺序执行：

1. 解析意图：搜索 / 播放 / 筛选 / 刮削 / 查看来源
2. 初始化路径变量
3. 执行 `check-install`
4. 根据意图补充 `list-filter-sources` 或 `list-providers`
5. 只使用真实 CLI 输出组织回复，不脑补结果

如果某一步缺少必要信息，优先通过 CLI 获取；只有 CLI 也无法消除歧义时才向用户确认。

## 快速启动

执行任何命令前，先初始化路径变量：

```bash
BMH_CLI="/Applications/网易爆米花.app/Contents/MacOS/bmh"
```

每次操作前必须先确认客户端状态：

```bash
$BMH_CLI check-install
```

返回 `installed`、`is_running`。

- 未安装：停止并给出安装指引
- 未运行：提示用户先启动客户端
- 已运行：再进入搜索 / 播放 / 筛选 / 刮削分支

这些状态字段用于内部判断。默认只在未安装、未启动或用户明确要求排障时对用户展示。

## 来源与字段判定

所有后续命令都依赖来源判定，先按这个规则理解返回值：

- 媒体库：`source` 为空 / `nil` / `bmh`，或来源列表中的 `source_type=bmh`
- 媒体服务器：`source_type` 或归一化后的来源属于 `emby`、`jellyfin`、`fnos`
- 媒体库播放参数：`--tmdb-id` + `--media-type`
- 媒体服务器播放参数：`--credentials-id` + `--item-id` + `--media-type`

关键约束：

- Emby/Jellyfin/FnOS 条目的 `tmdb_id` 可能是服务器内部 ID，不能直接当作 `--tmdb-id`
- 来源不明时，先查来源列表，不要先拍脑袋选一个源

### media_type 映射（play 前必查）

`play --media-type` 只接受整数 `2`（电影）或 `3`（剧集），不同来源命令的字段类型不同：

| 结果来源 | 原始 media_type | 传给 play 的值 |
|---------|----------------|---------------|
| `search` | `2`（int） | 直接用 `2` |
| `search` | `3`（int） | 直接用 `3` |
| `filter-bmh-media` | `"movie"`（string） | 必须转成 `2` |
| `filter-bmh-media` | `"series"`（string） | 必须转成 `3` |
| `filter-media-server` | `"movie"`（string） | 必须转成 `2` |
| `filter-media-server` | `"series"`（string） | 必须转成 `3` |

禁止：直接把字符串 `"movie"` / `"series"` 传给 `play --media-type`，CLI 会报错。

### source 值与播放参数映射

| source（int） | 对应 source_type | 必需参数 |
|--------------|-----------------|---------|
| `nil` | `bmh` | `--tmdb-id` + `--media-type` |
| `1` | `emby` | `--credentials-id` + `--item-id` + `--media-type` |
| `2` | `jellyfin` | `--credentials-id` + `--item-id` + `--media-type` |
| `3` | `fnos` | `--credentials-id` + `--item-id` + `--media-type` |

### 播放前检查清单

执行 `play` 前逐条确认：

- [ ] `media_type` 是整数 `2` 或 `3`？（来自 filter 时已完成 `movie→2` / `series→3` 转换？）
- [ ] 来源已判定？（`source=nil` 或 `source_type=bmh` 用媒体库参数，其余用媒体服务器参数）
- [ ] 媒体库条目：`tmdb_id` 确实来自媒体库？（服务器结果的 `tmdb_id` 不可信）
- [ ] 媒体服务器条目：`credentials_id` 和 `item_id` 都有值？
- [ ] 剧集且用户指定了季集：`--season` 和 `--episode` 已填？

## 意图路由

把用户请求先归到下面五类之一：

- 搜索/识别/找片/推荐某类内容：`search`
- 播放具体条目：`play`
- 按条件浏览内容：`filter-bmh-media` 或 `filter-media-server`
- 查看媒体源、网盘、媒体库：`list-filter-sources` / `list-providers`
- 开始刮削、查看进度、刮某个目录：`scrape-start` / `scrape-status`

用户说“推荐”时，不要凭常识直接给片单；优先用搜索或筛选拿真实结果，再基于结果做简短推荐。

## 命令速查

### search - 搜索媒体

```bash
# 媒体库
$BMH_CLI search --keyword "关键词" --source-type bmh --page 1 --page-size 20

# 单个媒体服务器
$BMH_CLI search --keyword "关键词" --source-type emby --source-id "uuid"
```

- `--source-type` 必填：`bmh | emby | jellyfin | fnos`
- `--source-id`：emby/jellyfin/fnos 时传 credentialsID，可先通过 `list-filter-sources` 获取
- 返回单源结果；如果要做“全源搜索”，需要先 `list-filter-sources`，再对每个来源分别调用 `search`，最后按来源合并展示

用户未指定来源时，先执行 `list-filter-sources` 获取所有来源，再逐个来源执行搜索。某个源报错或无结果不影响其他源。

### list-filter-sources - 获取可用源

```bash
$BMH_CLI list-filter-sources
```

返回 `sources[]`（含 `source_id`, `source_type`, `name`）。搜索和媒体服务器筛选前优先调用。

### play - 播放媒体

根据来源选择对应的播放参数：

| 来源 | 必填参数 |
|------|---------|
| 媒体库 | `--tmdb-id` + `--media-type` |
| Emby/Jellyfin/FnOS | `--credentials-id` + `--item-id` + `--media-type` |

```bash
# 媒体库
$BMH_CLI play --media-type 2 --tmdb-id "550"

# 媒体服务器
$BMH_CLI play --media-type 2 --credentials-id "uuid" --item-id "12345"

# 剧集指定季集（两类来源均可追加）
--season 1 --episode 1
```

关键陷阱：

- Emby/Jellyfin/FnOS 条目的 `tmdb_id` 绝不能传给 `--tmdb-id`
- `search` 结果里的 `media_type` 直接复用；任一 `filter` 结果若返回 `movie/series`，必须先转成 `2/3`
- 如果当前上下文里没有可靠的 `credentials_id` / `item_id` / `tmdb_id`，先重新搜索或先展示候选项，不要直接播放

### filter-bmh-media - 筛选媒体库

```bash
$BMH_CLI filter-bmh-media --media-type "电影" --genres "科幻" --country "日本" --sort-type "高分好评"
```

所有参数中文传值。支持 `--media-type`、`--genres`、`--country`、`--sort-type`、`--release-year`、`--page`、`--page-size`。

### filter-media-server - 筛选 Emby/Jellyfin（单源）

```bash
$BMH_CLI filter-media-server --source-id "uuid" --source-type emby --category "电影" --genres "恐怖" --sort-type "最新更新"
```

- `--source-id` 和 `--source-type` 必填
- 支持 `--category`（全部/电影/电视剧/收藏）、`--genres`、`--sort-type`（最新更新/最新上映/影片评分）、`--release-year`
- 不支持 `--country`
- 所有参数传中文，禁止传英文或 Emby 原生字段名

### list-providers - 获取网盘列表

```bash
$BMH_CLI list-providers
```

返回 `providers[]`（含 `provider_id`, `provider_type`, `name`）。

### scrape-start - 启动刮削

```bash
$BMH_CLI scrape-start --scope all
$BMH_CLI scrape-start --scope provider --provider-id "uuid"
$BMH_CLI scrape-start --scope path --provider-id "uuid" --path "/Movies"
```

### scrape-status - 查询刮削状态

```bash
$BMH_CLI scrape-status
```

返回 `is_active`、`scan_progress`、`match_progress`。

## 参数映射原则

把自然语言映射到 CLI 参数时，优先遵循下面规则：

- 地区词：`日本`、`韩国`、`美国` -> `--country`，仅媒体库支持
- 类型词：`电影`、`电视剧`、`综艺`、`动漫` -> 媒体库用 `--media-type`，媒体服务器用 `--category`
- 题材词：`科幻`、`动作`、`喜剧`、`恐怖` -> `--genres`
- 排序词：按命令支持范围映射到 `--sort-type`
- 年份：`2024`、`2023` -> `--release-year`

如果用户条件跨命令不兼容，例如“在 Emby 里按国家筛选”，要明确说明该命令不支持 `--country`，并给出最接近的可执行方案。

## 筛选命令选择

| 场景 | 命令 | 是否支持 country |
|------|------|------------------|
| 媒体库 | `filter-bmh-media` | 支持 |
| Emby/Jellyfin | `filter-media-server` | 不支持 |
| 来源不明 | 两边都执行，按来源合并展示 | 部分支持 |

关键点：地区词一定映射到 `--country`，绝不能误塞进 `--genres`。

## 回复规范

回复目标是“让用户知道你做了什么、拿到了什么、下一步能做什么”，不要只贴原始 JSON。

- 先说执行了哪个命令以及作用对象
- 再按来源分组给结果
- 有分页时说明 `count`、`total_count`、`has_more`
- 有可播放候选项时，在内部保留后续播放所需的关键字段：`media_type`、`tmdb_id`、`credentials_id`、`item_id`
- 出错时给出错误码、原因、下一步建议

当结果包含 `poster_url` 时，可以用 Markdown 图片增强展示，但文字字段优先，海报放在最右或单独附上，避免影响可读性。

## 用户可见话术

对用户回复时，不要暴露“模式 A / 模式 B”“模式切换”“内部路由”这类实现细节，除非用户明确在问技术原理或排障。

- 根据 `media_type` 调整称呼：`2` 优先称“电影”，`3` 优先称“电视剧”或“剧集”
- 默认不要强调来源类型，优先使用自然表达，例如“已开始播放《<标题>》”
- 默认不要强调来源类型，优先使用自然表达，例如“已为你播放《<标题>》”
- 需要强调类型时，电影可说“已开始播放电影《<标题>》”，电视剧可说“已开始播放电视剧《<标题>》”
- 如果用户明确说“播放电影《<标题>》”或“播放电视剧《<标题>》”，回复时优先沿用用户的类型表述
- 只有在用户明确询问来源、需要排障、或存在多来源歧义时，才补充来源信息
- `source_type=bmh` 时，对用户统一称“媒体库”，不要说“本地媒体库”或“本地”
- `emby`、`jellyfin`、`fnos` 时，优先使用来源名称，例如“Geek”，而不是笼统说“Emby 来源”
- 可以说明来源和动作，但不要描述内部参数选择过程
- 除非用户明确要求解释实现机制，否则禁止在最终回复中出现“模式 A”“模式 B”字样

避免使用：

- “使用模式 A 播放”
- “切换到模式 B”
- “命中播放模式 A/B”
- “已从本地媒体库找到并开始播放《<标题>》”
- “已从本地开始播放《<标题>》”
- “已从 Emby 来源 Geek 找到并开始播放《<标题>》”
- 在 `media_type=3` 时说成“已开始播放电影《<标题>》”
- 在 `media_type=2` 时说成“已开始播放电视剧《<标题>》”

优先使用：

- “已开始播放《<标题>》”
- “已从媒体库开始播放《<标题>》”
- “已从 Geek 开始播放《<标题>》”

## 详细参考

- 命令完整参数和响应格式：见 [references/commands.md](references/commands.md)
- 错误码和处理方式：见 [references/error-codes.md](references/error-codes.md)
- AI 执行流程决策树：见 [references/ai-workflow.md](references/ai-workflow.md)

只有在需要补充参数细节、错误恢复或复杂分支时再读取这些 reference，不要每次都把全部参考文档塞进上下文。

## 约束

- 不得伪造 CLI 输出
- 不得假设客户端正在运行，必须先 `check-install` 验证
- 不得把媒体服务器条目的内部 ID 当成 TMDB ID 使用
- 不得在来源不明时只搜单一来源并冒充“全局结果”
- 不得把不支持的自然语言条件强行映射成 CLI 参数
- 未经用户明确要求，不修改用户配置文件
