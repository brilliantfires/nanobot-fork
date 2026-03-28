---
name: memory
description: 基于 grep 召回的双层记忆系统。
always: true
---

# 记忆

## 结构

- `memory/MEMORY.md` — 长期事实（偏好、项目上下文、关系）。始终加载到上下文中。
- `memory/HISTORY.md` — 只追加的事件日志。**不会**被加载到上下文中。请用 grep 类工具或内存过滤器搜索。每条记录以 `[YYYY-MM-DD HH:MM]` 开头。

## 搜索过去的事件

根据文件大小选择搜索方式：

- 小型 `memory/HISTORY.md`：使用 `read_file`，然后在内存中搜索
- 大型或长期积累的 `memory/HISTORY.md`：使用 `exec` 工具做定向搜索

示例：
- **Linux/macOS:** `grep -i "keyword" memory/HISTORY.md`
- **Windows:** `findstr /i "keyword" memory\HISTORY.md`
- **跨平台 Python:** `python -c "from pathlib import Path; text = Path('memory/HISTORY.md').read_text(encoding='utf-8'); print('\n'.join([l for l in text.splitlines() if 'keyword' in l.lower()][-20:]))"`

对于较大的历史文件，优先使用有针对性的命令行搜索。

## 何时更新 MEMORY.md

使用 `edit_file` 或 `write_file` 立即写入重要事实：
- 用户偏好（“我更喜欢深色模式”）
- 项目上下文（“这个 API 使用 OAuth2”）
- 关系信息（“Alice 是项目负责人”）

## 自动整合

当会话变得很大时，旧对话会被自动总结并追加到 `HISTORY.md`。长期事实会被提取到 `MEMORY.md`。你不需要手动管理这些。
