# 错误码参考

所有错误通过 stdout 输出 JSON，进程以非 0 退出。格式：`{"error": {"code": "...", "message": "..."}}`

## 通用错误

| 错误码 | 说明 | 处理方式 |
|--------|------|---------|
| `INVALID_PARAMS` | 参数校验失败 | 检查必填参数、取值范围、参数类型和中文/英文取值是否符合要求 |
| `APP_NOT_INSTALLED` | 客户端未安装 | 停止操作，给出安装指引 |
| `APP_OFFLINE` | 客户端未运行 | 提示用户先启动客户端 |
| `AUTH_REQUIRED` | 需要登录 | 提示用户在客户端中登录 |
| `BACKEND_ERROR` | 后端错误 | 稍后重试 |
| `TIMEOUT` | 请求超时 | 稍后重试 |

## 筛选相关错误与处理建议

筛选命令当前可能复用通用错误码，尤其是 `INVALID_PARAMS`。遇到 filter 失败时，优先按下面场景排查。

| 场景 | 可能错误码 | 处理建议 |
|------|-----------|---------|
| `filter-bmh-media` 传了英文值，如 `movie` / `action` | `INVALID_PARAMS` | 改成中文值，如 `电影` / `动作` |
| `filter-bmh-media` 把地区传进 `--genres` | `INVALID_PARAMS` 或结果为空 | 把 `日本` / `韩国` / `美国` 改传 `--country` |
| `filter-media-server` 缺少 `--source-id` 或 `--source-type` | `INVALID_PARAMS` | 先调用 `list-filter-sources` 获取正确的源信息 |
| `filter-media-server` 传了不存在的 `source-id` | `INVALID_PARAMS` 或后端错误 | 重新调用 `list-filter-sources`，确认 `source_id` 仍然有效 |
| `filter-media-server` 传了 `--country` | `INVALID_PARAMS` | 去掉 `--country`，改为只保留服务器支持的条件 |
| `filter-media-server` 传了英文分类或排序值 | `INVALID_PARAMS` | 改成中文枚举值，如 `电影`、`最新更新` |
| 筛选命令成功但结果为空 | 无错误码 | 保留用户原条件说明，并建议放宽条件或切换来源重试 |

## 播放错误

| 错误码 | 说明 | 处理方式 |
|--------|------|---------|
| `MEDIA_NOT_FOUND` | 媒体未找到 | 检查 tmdb-id 或 item-id 是否正确；若来源于 `filter-media-server`，确认 `media_type` 已从 `movie/series` 转成 `2/3` |
| `NO_PLAYABLE_FILE` | 无可播放文件 | 告知用户该媒体暂无可播放资源 |
| `PLAY_REQUEST_REJECTED` | 播放请求被拒绝 | 检查参数，确认客户端状态正常 |

## 刮削错误

| 错误码 | 说明 | 处理方式 |
|--------|------|---------|
| `SCRAPE_ALREADY_RUNNING` | 刮削任务已在进行中 | 调用 `scrape-status` 查看进度 |
| `SCRAPE_RATE_LIMITED` | 请求过于频繁（30秒冷却） | 等待 `retry_after_seconds` 秒后重试 |
| `SCRAPE_PROVIDER_AMBIGUOUS` | 指定类型存在多个网盘 | 展示 `candidates` 列表供用户选择，用 `--provider-id` 重试 |
| `SCRAPE_PROVIDER_NOT_FOUND` | 指定网盘未找到 | 调用 `list-providers` 查看可用网盘 |
| `SCRAPE_PATH_NOT_FOUND` | 刮削路径无效 | 路径必须是 App 中已配置的目录或其子目录 |
| `SCRAPE_NO_PROVIDERS` | 没有可用网盘 | 提示用户在 App 中绑定网盘 |

## 特殊错误响应示例

### SCRAPE_PROVIDER_AMBIGUOUS

```json
{
  "error": {"code": "SCRAPE_PROVIDER_AMBIGUOUS", "message": "Multiple providers found..."},
  "candidates": [
    {"provider_id": "abc-123", "provider_type": "aliyun", "name": "工作盘"},
    {"provider_id": "xyz-789", "provider_type": "aliyun", "name": "个人盘"}
  ]
}
```

### SCRAPE_RATE_LIMITED

```json
{
  "error": {"code": "SCRAPE_RATE_LIMITED", "message": "Rate limited..."},
  "retry_after_seconds": 25
}
```
