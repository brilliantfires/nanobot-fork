---
name: cron
description: 安排提醒和周期性任务。
---

# Cron

使用 `cron` 工具来安排提醒或周期性任务。

## 三种模式

1. **Reminder** - 直接向用户发送消息
2. **Task** - 消息作为任务描述，由 agent 执行并发送结果
3. **One-time** - 在指定时间只运行一次，然后自动删除

## 示例

固定提醒：
```
cron(action="add", message="Time to take a break!", every_seconds=1200)
```

动态任务（每次都由 agent 执行）：
```
cron(action="add", message="Check HKUDS/nanobot GitHub stars and report", every_seconds=600)
```

一次性定时任务（根据当前时间计算 ISO datetime）：
```
cron(action="add", message="Remind me about the meeting", at="<ISO datetime>")
```

带时区的 cron：
```
cron(action="add", message="Morning standup", cron_expr="0 9 * * 1-5", tz="America/Vancouver")
```

列出 / 移除：
```
cron(action="list")
cron(action="remove", job_id="abc123")
```

## 时间表达

| 用户说法 | 参数 |
|-----------|------------|
| every 20 minutes | every_seconds: 1200 |
| every hour | every_seconds: 3600 |
| every day at 8am | cron_expr: "0 8 * * *" |
| weekdays at 5pm | cron_expr: "0 17 * * 1-5" |
| 9am Vancouver time daily | cron_expr: "0 9 * * *", tz: "America/Vancouver" |
| at a specific time | at: ISO datetime string（根据当前时间计算） |

## 时区

使用 `tz` 配合 `cron_expr`，即可按指定 IANA 时区调度。若未提供 `tz`，则使用服务器本地时区。
