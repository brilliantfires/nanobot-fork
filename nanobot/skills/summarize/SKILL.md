---
name: summarize
description: 对 URL、播客和本地文件进行总结，或提取文本 / 转录（也是“转写这个 YouTube/视频”场景下的优质兜底方案）。
homepage: https://summarize.sh
metadata: {"nanobot":{"emoji":"🧾","requires":{"bins":["summarize"]},"install":[{"id":"brew","kind":"brew","formula":"steipete/tap/summarize","bins":["summarize"],"label":"Install summarize (brew)"}]}}
---

# Summarize

一个快速的 CLI，可用于总结 URL、本地文件和 YouTube 链接。

## 何时使用（触发短语）

当用户提出以下任一请求时，立即使用此技能：
- “use summarize.sh”
- “what’s this link/video about?”
- “summarize this URL/article”
- “transcribe this YouTube/video” （尽力提取转录；不需要 `yt-dlp`）

## 快速开始

```bash
summarize "https://example.com" --model google/gemini-3-flash-preview
summarize "/path/to/file.pdf" --model google/gemini-3-flash-preview
summarize "https://youtu.be/dQw4w9WgXcQ" --youtube auto
```

## YouTube：摘要 vs 转录

尽力获取转录（仅 URL）：

```bash
summarize "https://youtu.be/dQw4w9WgXcQ" --youtube auto --extract-only
```

如果用户要的是转录，但内容太大，先返回一份紧凑摘要，然后询问对方想展开哪个章节或时间段。

## 模型与密钥

为所选提供商设置 API key：
- OpenAI: `OPENAI_API_KEY`
- Anthropic: `ANTHROPIC_API_KEY`
- xAI: `XAI_API_KEY`
- Google: `GEMINI_API_KEY`（别名：`GOOGLE_GENERATIVE_AI_API_KEY`、`GOOGLE_API_KEY`）

如果未设置，默认模型为 `google/gemini-3-flash-preview`。

## 常用参数

- `--length short|medium|long|xl|xxl|<chars>`
- `--max-output-tokens <count>`
- `--extract-only`（仅 URL）
- `--json`（机器可读）
- `--firecrawl auto|off|always`（兜底提取）
- `--youtube auto`（若设置了 `APIFY_API_TOKEN`，可用 Apify 兜底）

## 配置

可选配置文件：`~/.summarize/config.json`

```json
{ "model": "openai/gpt-5.2" }
```

可选服务：
- `FIRECRAWL_API_KEY` 用于被屏蔽站点
- `APIFY_API_TOKEN` 用于 YouTube 兜底
