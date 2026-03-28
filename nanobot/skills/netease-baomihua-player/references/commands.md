# 命令参考

## 目录

- [读取顺序](#读取顺序)
- [字段归一化](#字段归一化)
- [状态与控制](#状态与控制)
- [播放](#播放)
- [刮削](#刮削)
- [搜索与筛选](#搜索与筛选)

## 读取顺序

建议按下面顺序读取这份文档：

1. 先看“字段归一化”，理解 `source`、`media_type`、`tmdb_id`、`credentials_id`、`item_id`
2. 再看具体命令的“前置 / 命令 / 参数 / 响应 / 常见误用”
3. 遇到错误时跳转到 `error-codes.md`

这份文档负责“命令事实和字段定义”。复杂决策分支见 `ai-workflow.md`。

## 字段归一化

### 来源判定

| 场景 | 可依赖字段 | 后续动作 |
|------|-----------|---------|
| 媒体库 | `source=nil/bmh` 或 `source_type=bmh` | 播放走 `--tmdb-id` |
| Emby/Jellyfin/FnOS | `source_type` 或归一化来源为 `emby/jellyfin/fnos` | 播放走 `--credentials-id` + `--item-id` |

如果不同字段看起来有冲突，以“是否有 `credentials_id` + `item_id` 且来源属于媒体服务器”为准；拿不准时先重新查询来源，不要直接播放。

### media_type 归一化

`play --media-type` 只能接受整数：

| 来源命令 | 原始值 | 播放参数值 |
|---------|-------|-----------|
| `search` | `2` | `2` |
| `search` | `3` | `3` |
| `filter-bmh-media` / `filter-media-server` | `movie` | `2` |
| `filter-bmh-media` / `filter-media-server` | `series` | `3` |

规则：

- 如果结果来自 `search`，直接复用原始整数值
- 如果结果来自任一 `filter` 命令，播放前必须先把 `movie -> 2`、`series -> 3`
- 不能从标题猜 `media_type`

### 搜索/筛选结果展示规范

当响应中包含 `poster_url` 字段时，可用 Markdown 图片（`![](url)`）增强展示。文字字段优先，海报放在表格最右侧或单独附上，避免影响阅读。

## 状态与控制

### check-install

用途：检查客户端安装和运行状态。

前置：无。

```bash
bmh check-install
```

**响应**：

```json
{
  "installed": true,
  "is_running": true
}
```

常见误用：

- 不要跳过这一步直接执行其他命令
- `installed=true` 不代表 `is_running=true`

---

### list-filter-sources

用途：获取所有可用的搜索/筛选源列表。

前置：通常在 `check-install` 之后调用。

```bash
bmh list-filter-sources
```

**响应**：

```json
{
  "sources": [
    {"source_id": "bmh", "source_type": "bmh", "name": "媒体库"},
    {"source_id": "abc-uuid", "source_type": "emby", "name": "家庭 Emby"}
  ]
}
```

常见误用：

- 不要把 `source_id` 和 `source_type` 混用
- `emby/jellyfin/fnos` 的搜索和筛选都需要对应的 `source_id`

---

### list-providers

用途：获取已绑定的网盘列表。

前置：通常在 `check-install` 之后调用。

```bash
bmh list-providers
```

**响应**：

```json
{
  "providers": [
    {"provider_id": "abc-123", "provider_type": "aliyun", "name": "我的阿里云盘"}
  ]
}
```

常见误用：

- 多个同类型网盘并存时，不要只凭 `provider_type` 猜具体账号

## 播放

### play

用途：播放指定媒体。

前置：

- 已执行 `check-install`
- 已有可靠候选项，且包含播放所需字段

```bash
# 媒体库（source=nil 或 bmh）
bmh play --tmdb-id <id> --media-type <2|3> [--season N] [--episode N]

# 媒体服务器（Emby / Jellyfin / FnOS）
bmh play --credentials-id <id> --item-id <id> --media-type <2|3> [--season N] [--episode N]
```

**参数选择**：

| 搜索结果来源 | 必填参数 |
|-------------|---------|
| `nil` / `bmh` / `source_type=bmh` | `--tmdb-id` |
| `emby` / `jellyfin` / `fnos` | `--credentials-id` + `--item-id` |

**media_type 处理**：

- `search` 结果里的 `media_type` 可直接传给 `play`
- 任一 `filter` 结果里的 `media_type` 如果是 `movie`，传 `2`
- 任一 `filter` 结果里的 `media_type` 如果是 `series`，传 `3`

**响应**：

```json
{"accepted": true, "request": {...}}
```

常见误用：

- Emby/Jellyfin/FnOS 返回的 `tmdb_id` 可能是服务器内部 ID，不能传给 `--tmdb-id`
- 只要存在 `credentials_id` 和 `item_id`，优先按媒体服务器参数播放
- 如果当前上下文里没有可靠的 `credentials_id` / `item_id` / `tmdb_id`，先重新搜索或重新展示候选项

**播放前检查清单**：

- [ ] `media_type` 是整数 `2` 或 `3`？（来自 filter 时已完成 `movie→2` / `series→3` 转换？）
- [ ] 来源已判定？（`source=nil` 或 `source_type=bmh` 用媒体库参数，其余用媒体服务器参数）
- [ ] 媒体库条目：`tmdb_id` 确实来自媒体库？（服务器结果的 `tmdb_id` 不可信）
- [ ] 媒体服务器条目：`credentials_id` 和 `item_id` 都有值？
- [ ] 剧集且用户指定了季集：`--season` 和 `--episode` 已填？

## 刮削

### scrape-start

用途：启动网盘刮削任务。

前置：

- 已执行 `check-install`
- 涉及指定网盘或路径时，通常先执行 `list-providers`

```bash
bmh scrape-start [--scope all|provider|path]
                 [--provider-id <id>]
                 [--provider-type <type>]
                 [--path <path>]
```

| 参数 | 必填 | 默认 | 说明 |
|------|------|------|------|
| `--scope` | 否 | `all` | 刮削范围：`all` / `provider` / `path` |
| `--provider-id` | 条件 | - | `scope=provider` 或 `scope=path` 时使用 |
| `--provider-type` | 条件 | - | 网盘类型；多账号时需改用 `--provider-id` |
| `--path` | 条件 | - | `scope=path` 时必填，支持精确路径/目录名/前缀匹配 |

**响应**：

```json
{"accepted": true}
```

常见误用：

- 多账号场景优先传 `--provider-id`，不要只传 `--provider-type`
- 指定路径刮削时，路径必须属于已配置目录或其子目录

---

### scrape-status

用途：查询当前刮削任务进度。

前置：通常在 `check-install` 之后调用。

```bash
bmh scrape-status
```

**响应**：

```json
{
  "is_active": true,
  "scan_progress": {
    "total_files": 100,
    "scanned_files": 80,
    "status": "scanning"
  },
  "match_progress": {
    "total_file_count": 100,
    "fetched": 60,
    "finished": 65,
    "pending": 35,
    "server_status": "matching"
  }
}
```

常见误用：

- `is_active=false` 不等于一定成功完成，要结合 `scan_progress.status` / `match_progress.server_status` 看

## 搜索与筛选

以下三个命令的响应均包含分页字段，items 中有 `poster_url` 时遵循展示规范。

### search

用途：搜索单个来源下的媒体。用户未指定来源时，需要先拿来源列表，再逐源搜索并合并结果。

前置：

- 已执行 `check-install`
- 已明确本次搜索要查哪个来源
- 如果指定非媒体库源，通常先执行 `list-filter-sources` 获取 `source_id`

```bash
# 媒体库
bmh search --keyword <词> --source-type bmh
           [--page 1] [--page-size 20] [--types 2,3]

# 单个媒体服务器
bmh search --keyword <词> --source-type <类型> [--source-id <id>]
           [--page 1] [--page-size 20] [--types 2,3]
```

| 参数 | 必填 | 默认 | 说明 |
|------|------|------|------|
| `--keyword` | 是 | - | 搜索关键词，不能为空 |
| `--source-type` | 是 | - | `bmh` / `emby` / `jellyfin` / `fnos` |
| `--source-id` | 条件 | - | emby/jellyfin/fnos 时必填（credentialsID）；bmh 时不传 |
| `--page` | 否 | `1` | >= 1 |
| `--page-size` | 否 | `20` | 1-50 |
| `--types` | 否 | `2,3` | `2`=电影，`3`=剧集 |

**响应**：

响应始终为按源分组的结构，无论单源还是全源搜索：

```json
{
  "sources": [
    {
      "source_id": "bmh",
      "source_type": "bmh",
      "name": "媒体库",
      "items": [...],
      "total_count": 12,
      "has_more": true,
      "error": null
    },
    {
      "source_id": "abc-uuid",
      "source_type": "emby",
      "name": "家庭 Emby",
      "items": [...],
      "total_count": 5,
      "has_more": false,
      "error": null
    }
  ],
  "total_count": 17
}
```

| 顶层字段 | 类型 | 说明 |
|---------|------|------|
| `sources` | array | 按源分组的搜索结果列表 |
| `total_count` | int | 所有源的结果总数 |

#### sources[] 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `source_id` | string | 源唯一标识：媒体库为 `"bmh"`，服务器为 credentialsID |
| `source_type` | string | `bmh` / `emby` / `jellyfin` / `fnos` |
| `name` | string | 源显示名称 |
| `items` | array | 该源的搜索结果列表 |
| `total_count` | int | 该源的匹配总数（-1 表示不支持/未知） |
| `has_more` | bool | 该源是否还有更多数据可翻页 |
| `error` | string? | 搜索该源时的错误信息（null 表示成功） |

#### items[] 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `tmdb_id` | string | 本地库是真实 TMDB ID；媒体服务器里可能是内部 ID |
| `name` | string | 标题 |
| `media_type` | int | `2`=电影，`3`=剧集。可直接传给 `play --media-type` |
| `release_year` | string? | 发行年份 |
| `poster_url` | string? | 海报 URL |
| `vote` | string? | 评分 |
| `source` | int? | 来源编号：`nil`=媒体库，`1`=emby，`2`=jellyfin，`3`=fnos |
| `credentials_id` | string? | 媒体服务器账号 ID（媒体服务器播放必需） |
| `item_id` | string? | 媒体服务器内部 ID（媒体服务器播放必需） |
| `media_id` | string? | 媒体库内部 ID（可选） |

#### source 值与播放参数映射

| source 值 | 对应 source_type | 必需参数 |
|-----------|-----------------|---------|
| `nil` | `bmh` | `--tmdb-id` + `--media-type` |
| `1` | `emby` | `--credentials-id` + `--item-id` + `--media-type` |
| `2` | `jellyfin` | `--credentials-id` + `--item-id` + `--media-type` |
| `3` | `fnos` | `--credentials-id` + `--item-id` + `--media-type` |

常见误用：

- 不要省略 `--source-type`；用户未指定来源时，先 `list-filter-sources` 再逐源调用
- 单次 search 可以是单源结果，但后续处理前应按来源聚合成统一的 `sources[]` 结构
- 只在媒体库结果里（`source=nil`）把 `tmdb_id` 传给 `play --tmdb-id`
- `media_type` 是播放时的权威字段，不要从标题猜是电影还是剧集
- `source` 字段判断来源时用数字，不要用字符串比较
- 多源搜索时，某个源失败不代表其他源失败，照常展示其他源的结果

---

### filter-bmh-media

用途：筛选媒体库中已刮削的内容。所有参数值必须传中文。

前置：

- 已执行 `check-install`

```bash
bmh filter-bmh-media [--media-type 电影|电视剧|综艺|动漫]
                     [--genres 科幻,动作]
                     [--country 日本]
                     [--sort-type 最新更新|高分好评|最新上映]
                     [--release-year 2024]
                     [--page 1] [--page-size 20]
```

| 参数 | 必填 | 默认 | 说明 |
|------|------|------|------|
| `--media-type` | 否 | - | `电影` / `电视剧` / `综艺` / `动漫` |
| `--genres` | 否 | - | 中文逗号分隔，如 `科幻,动作` |
| `--country` | 否 | - | `日本` / `美国` / `中国大陆` |
| `--sort-type` | 否 | - | `最新更新` / `高分好评` / `最新上映` |
| `--release-year` | 否 | - | 年份字符串，如 `2024` |
| `--page` | 否 | `1` | >= 1 |
| `--page-size` | 否 | `20` | 1-50 |

**响应**：

```json
{
  "items": [...],
  "count": 20,
  "total_count": 100,
  "has_more": true,
  "next_page": 2
}
```

#### items 字段

筛选结果使用统一的 filter item 结构，`media_type` 是字符串而不是整数。

| 字段 | 类型 | 说明 |
|------|------|------|
| `tmdb_id` | string? | 媒体库时通常是真实 TMDB ID |
| `title` | string | 标题 |
| `release_year` | int? | 发行年份 |
| `genres` | string[]? | 题材列表 |
| `rating` | float? | 评分 |
| `media_type` | string? | 常见值为 `movie` / `series` |
| `poster_url` | string? | 海报 URL |
| `credentials_id` | string? | 一般本地库为空，媒体服务器结果会有 |
| `item_id` | string? | 一般本地库为空，媒体服务器结果会有 |

常见误用：

- 地区词用 `--country`，不能用 `--genres`
- 参数值必须传中文，不要传英文枚举或后端字段名
- 不能把这里返回的字符串 `media_type` 原样传给 `play`

---

### filter-media-server

用途：筛选单个 Emby 或 Jellyfin 服务器内容。所有参数值必须传中文，不支持 `--country`。如需筛 FnOS，先确认当前 CLI 版本是否支持同名参数后再执行。

前置：

- 已执行 `check-install`
- 已执行 `list-filter-sources`
- 已拿到对应服务器的 `source-id`

```bash
bmh filter-media-server --source-id <id> --source-type emby|jellyfin
                        [--category 全部|电影|电视剧|收藏]
                        [--genres 恐怖,动作]
                        [--sort-type 最新更新|最新上映|影片评分]
                        [--release-year 2024]
                        [--page 1] [--page-size 20]
```

| 参数 | 必填 | 默认 | 说明 |
|------|------|------|------|
| `--source-id` | 是 | - | credentialsID |
| `--source-type` | 是 | - | `emby` / `jellyfin` |
| `--category` | 否 | `全部` | `全部` / `电影` / `电视剧` / `收藏` |
| `--genres` | 否 | - | 中文题材，如 `恐怖` / `动作` |
| `--sort-type` | 否 | `最新更新` | `最新更新` / `最新上映` / `影片评分` |
| `--release-year` | 否 | - | 年份字符串 |
| `--page` | 否 | `1` | >= 1 |
| `--page-size` | 否 | `20` | 1-50 |

**参数语义映射**：

| 用户描述 | 对应参数 |
|---------|---------|
| 全部 / 电影 / 电视剧 / 收藏 | `--category` |
| 2024 / 2023 等年份 | `--release-year` |
| 最新更新 / 最新上映 / 影片评分 | `--sort-type` |
| 恐怖 / 动作 / 科幻 / 喜剧 | `--genres` |

**响应**：

```json
{
  "items": [...],
  "count": 20,
  "total_count": 100,
  "has_more": true,
  "next_page": 2
}
```

#### items 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `title` | string | 标题 |
| `media_type` | string | `movie` / `series` |
| `item_id` | string | 服务器内部 ID，播放时必需 |
| `credentials_id` | string | 账号 ID，播放时必需 |
| `poster_url` | string? | 海报 URL |
| `rating` | float? | 评分 |
| `release_year` | int? | 发行年份 |

**播放前转换说明**：

- `media_type=movie` 时，后续 `play --media-type` 必须传 `2`
- `media_type=series` 时，后续 `play --media-type` 必须传 `3`
- 这个结果里的 `item_id` 和 `credentials_id` 要原样保留给 `play`

常见误用：

- 不支持 `--country`；用户提地区时要明确说明限制
- 参数值必须传中文，不要传 Emby/Jellyfin 的英文原生字段值
- 不能把这里返回的字符串 `media_type` 原样传给 `play`
## 用户可见称呼

- `source_type=bmh` 或 `source=nil` 时，对用户统一称“媒体库”，不要说“本地”或“本地媒体库”
- `emby`、`jellyfin`、`fnos` 时，优先使用返回的来源名称，例如“Geek”
- 默认回复“已开始播放《<标题>》”；只有在需要区分来源时，再说“已从媒体库开始播放《<标题>》”或“已从 Geek 开始播放《<标题>》”
- `tmdb_id`、`credentials_id`、`item_id`、参数映射规则仅用于内部执行，默认不要在用户回复里展开
