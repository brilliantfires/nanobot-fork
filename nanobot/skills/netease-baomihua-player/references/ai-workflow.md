# AI 执行流程

先做 `check-install`，再进入具体分支。不要跳过状态检查。

## 1. 搜索流程

```
check-install → installed=false → 停止，安装指引
             → is_running=false → 停止，APP_OFFLINE
             → 运行中 ↓

用户指定了来源？
├── 是（如”在 Emby 里搜”）
│   └── 先 list-filter-sources 获取 source_id
│   └── search --keyword ... --source-type emby --source-id <id>
└── 否
    └── 先 list-filter-sources 获取所有来源
    └── 对每个来源分别执行 search --keyword ... --source-type <type> [--source-id <id>]
    └── 最后按来源合并展示

响应解析：
├── 单次 search 响应为单源结果
├── 逐源读取 items / count / total_count / has_more
├── 某个源搜索失败 → 单独标注该源失败，继续展示其他源
└── 保留每条结果的 source / credentials_id / item_id / tmdb_id / media_type 供后续播放
```

补充规则：

- CLI 搜索要求显式传入来源；用户未指定时，要自己遍历所有已配置来源
- 某个源没有结果时（items 为空），也要展示该源并说明无结果
- 用户说”推荐”但没有指定标题时，按搜索或筛选流程执行，不要脱离 CLI 自行编片单

## 2. 播放流程

```
check-install → 确认运行中 ↓

有搜索结果？
├── 否 → 先执行搜索
└── 是 ↓

读取条目来源：
├── source == nil / source_type == bmh
│   └── 使用媒体库参数：--tmdb-id <tmdb_id> --media-type <media_type>
│
└── source == emby/jellyfin/fnos
    ├── credentials_id + item_id 均存在
    │   └── 使用媒体服务器参数：--credentials-id <credentials_id> --item-id <item_id> --media-type <media_type>
    └── 缺失 → 无法播放，告知用户

注意: media-type 必须用搜索结果字段值，禁止猜测
注意: Emby 的 tmdb_id 是内部 ID，绝不能传给 --tmdb-id
注意: 如果候选项来自任一 filter 命令，需先把 media_type 从 movie/series 映射为 2/3 再传给 play
```

补充规则：

- 如果上下文里的候选项缺少播放必要字段，先重新搜索或重新展示候选项
- 剧集只有在用户明确指定季/集，或候选项已唯一定位到单集时才补 `--season` / `--episode`

## 3. 筛选流程

```
check-install → 确认运行中 ↓

用户意图：
├── 明确媒体库（"媒体库里有什么…"）
│   └── filter-bmh-media
│       ├── 地区词 → --country
│       ├── 题材词 → --genres
│       ├── 类型词 → --media-type
│       └── 排序词 → --sort-type
│
├── 明确 Emby/Jellyfin（"Emby 里有什么…"）
│   └── filter-media-server（需 --source-id + --source-type）
│       ├── 分类词 → --category
│       ├── 年份 → --release-year
│       ├── 排序词 → --sort-type
│       ├── 题材词 → --genres
│       └── 不支持 --country
│
└── 未指定来源
    └── filter-bmh-media + 所有 filter-media-server 都执行，合并展示

多源筛选：串行对每个非 bmh-media 源调用 filter-media-server，按来源分组展示
```

补充规则：

- “地区”只在媒体库有效，媒体服务器不支持时要明确告诉用户
- 当用户只说“看看有什么”这类模糊浏览请求，优先走筛选而不是搜索

## 4. 刮削流程

```
check-install → 确认运行中 ↓

用户意图：
├── "有哪些网盘" → list-providers
├── "开始刮削" → scrape-start
│   ├── 默认 --scope all
│   ├── 指定网盘类型 → --scope provider --provider-type <type>
│   ├── 指定路径 → --scope path --provider-id <id> --path <path>
│   └── 遇到 AMBIGUOUS → 展示 candidates 供选择
├── "刮削进度" → scrape-status
└── "刮削某个目录" → 先 list-providers 获取 id，再 scrape-start --scope path
```

补充规则：

- 遇到 `SCRAPE_PROVIDER_AMBIGUOUS` 时，不要替用户猜；直接展示 candidates 让用户选
- 遇到 `SCRAPE_ALREADY_RUNNING` 或 `SCRAPE_RATE_LIMITED` 时，优先补 `scrape-status` 或等待建议，而不是盲目重试

## 5. 回复模板要点

| 命令 | 回复应包含 |
|------|-----------|
| check-install | 仅在异常或排障时向用户说明 installed/running |
| search | keyword、各源结果分组、count/total/has_more |
| play | 动作结果、必要时补充来源名、accepted 状态 |
| filter | 筛选条件、结果分组、分页信息 |
| list-providers | 数量、每个网盘的 id/type/name |
| scrape-start | scope、accepted 状态、特殊错误处理 |
| scrape-status | is_active、进度数据、状态描述 |

总规则：

- 不只贴 JSON，先用一句话总结执行结果
- 多源结果按来源分组
- 对后续可操作项保留关键字段，方便继续播放或二次筛选
- 对用户提到 `bmh` 结果时统一称“媒体库”；对 `emby/jellyfin/fnos` 优先使用来源名称，如“Geek”
