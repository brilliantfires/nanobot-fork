# nanobot 技能

这个目录包含用于扩展 nanobot 能力的内建技能。

## 技能格式

每个技能都是一个目录，内部包含一个 `SKILL.md` 文件，内容包括：
- YAML frontmatter（名称、描述、元数据）
- 面向 agent 的 Markdown 指令

## 来源说明

这些技能改编自 [OpenClaw](https://github.com/openclaw/openclaw) 的技能系统。
技能格式和元数据结构遵循 OpenClaw 的约定，以保持兼容性。

## 可用技能

| 技能 | 描述 |
|-------|-------------|
| `github` | 使用 `gh` CLI 与 GitHub 交互 |
| `weather` | 使用 wttr.in 和 Open-Meteo 获取天气信息 |
| `summarize` | 总结 URL、文件和 YouTube 视频 |
| `tmux` | 远程控制 tmux 会话 |
| `clawhub` | 从 ClawHub 注册表搜索并安装技能 |
| `skill-creator` | 创建新技能 |
