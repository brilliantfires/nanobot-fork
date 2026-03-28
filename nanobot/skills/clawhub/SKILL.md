---
name: clawhub
description: 从公开技能注册表 ClawHub 搜索并安装 agent 技能。
homepage: https://clawhub.ai
metadata: {"nanobot":{"emoji":"🦞"}}
---

# ClawHub

面向 AI agent 的公开技能注册表。支持自然语言搜索（向量检索）。

## 何时使用

当用户提出以下任一请求时，使用此技能：
- “find a skill for …”
- “search for skills”
- “install a skill”
- “what skills are available?”
- “update my skills”

## 搜索

```bash
npx --yes clawhub@latest search "web scraping" --limit 5
```

## 安装

```bash
npx --yes clawhub@latest install <slug> --workdir ~/.nanobot/workspace
```

将 `<slug>` 替换为搜索结果中的技能名。该命令会把技能安装到 `~/.nanobot/workspace/skills/`，这是 nanobot 加载工作区技能的位置。始终要包含 `--workdir`。

## 更新

```bash
npx --yes clawhub@latest update --all --workdir ~/.nanobot/workspace
```

## 查看已安装技能

```bash
npx --yes clawhub@latest list --workdir ~/.nanobot/workspace
```

## 注意事项

- 需要 Node.js（`npx` 随之提供）。
- 搜索和安装不需要 API key。
- 登录（`npx --yes clawhub@latest login`）只在发布技能时需要。
- `--workdir ~/.nanobot/workspace` 非常关键；如果没有它，技能会安装到当前目录，而不是 nanobot 的工作区。
- 安装完成后，提醒用户开启一个新会话来加载该技能。
