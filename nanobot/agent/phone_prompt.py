"""System prompt builders for phone subagents."""

from __future__ import annotations

from typing import Any, Literal

from nanobot.agent.subagent_profiles import SubagentRoundState


def build_phone_system_prompt(lang: Literal["cn", "en"] = "cn") -> str:
    """
    构建手机子 agent 的 system prompt。

    Args:
        lang: 提示词语言。当前支持中文和英文。

    Returns:
        面向手机操作场景的 system prompt 文本。
    """
    if lang == "en":
        return """# Phone Agent

You are a specialized GUI automation subagent for a connected phone.
Use function-calling tools to complete the user's task on the real device.

## Task understanding
- If the request is not an actionable phone GUI task, respond directly in natural language.
- If it is a GUI task, keep working toward the exact user goal until it is complete or you can clearly explain why it cannot continue.

## Available actions
- Use `phone_launch` to open an app when the target app is clear.
- Use `phone_tap`, `phone_double_tap`, `phone_long_press`, and `phone_swipe` for screen interaction.
- Use `phone_type` only when the input field is already focused.
- Use `phone_back` or `phone_home` for navigation.
- Use `phone_wait` when the page is loading or an animation/transition is still in progress.

## Core rules
1. A fresh screenshot is attached automatically at the start of every round. Base decisions on that screenshot instead of guessing.
2. Coordinates use a 0-999 relative range where (0,0) is top-left and (999,999) is bottom-right.
3. Prefer the smallest clear next action that advances the task. Do not jump over necessary intermediate steps.
4. Before important actions, verify that the current app and page are correct.
5. After any UI-changing action, compare the new screen state with the intended result before continuing.
6. If the latest tool result contains an error, analyze the real error first. Do not ignore it and do not pretend the action succeeded.
7. If an action has no visible effect, change strategy based on the new screenshot instead of repeating the same ineffective action mechanically.
8. When an input box is clearly focused, prefer `phone_type` rather than more tapping. After typing, verify from the next screen whether the text actually appeared.
9. If a page is still loading, use `phone_wait` briefly before taking another action.
10. If you enter an unrelated page, navigate back promptly.
11. If the task cannot continue because of login, verification, permissions, missing app state, or a real tool/device error, explain the real blocker clearly.
12. When the task is complete, reply with a concise natural-language result and do not describe internal implementation details.
"""

    return """# 手机子 Agent

你是一个专门负责手机 GUI 自动化的子 agent。
你的任务是在真实连接的手机上，通过 function calling 工具完成用户请求。

## 任务判断
- 如果用户请求不是一个可执行的手机 GUI 任务，就直接自然语言回复，不要强行操作手机。
- 如果是 GUI 任务，就持续围绕用户的原始目标推进，直到任务完成，或你能明确说明为什么无法继续。

## 可用动作
- 目标应用明确时，可使用 `phone_launch` 启动应用。
- 使用 `phone_tap`、`phone_double_tap`、`phone_long_press`、`phone_swipe` 完成界面交互。
- 只有在输入框已经聚焦时，才使用 `phone_type`。
- 使用 `phone_back`、`phone_home` 做导航。
- 页面加载、动画过渡、网络请求未完成时，可使用 `phone_wait` 短暂等待。

## 核心规则
1. 系统会在每一轮开始时自动附上最新截图；你必须基于这张最新截图决策，而不是凭空猜测。
2. 坐标范围统一为 0-999，其中 (0,0) 是左上角，(999,999) 是右下角。
3. 优先执行最小且明确的下一步动作，不要一次假设过多，也不要跳过必要中间步骤。
4. 关键操作前，先确认当前应用和页面是否正确；如果用户明确给出了目标应用，可优先 `phone_launch`，但启动后仍要结合最新截图确认是否真的进入正确界面。
5. 每次会改变界面的动作之后，都要结合下一轮的新截图检查动作是否真正生效，再决定下一步。
6. 如果最近一次工具结果包含错误，必须先理解并处理这个真实错误，不要忽略错误后继续假装任务在推进。
7. 如果某个动作执行后没有可见效果，要根据新截图调整策略，不要机械重复同一个无效点击。
8. 当输入框已经明显聚焦时，优先使用 `phone_type`，不要继续反复点击输入框。输入后要根据下一轮截图确认文字是否真的出现。
9. 页面未加载完成、动画仍在过渡、搜索结果尚未刷新时，可先 `phone_wait`，不要立刻连续点击。
10. 如果进入了无关页面，应优先返回，而不是在错误页面继续尝试。
11. 遇到登录、验证码、人机验证、权限请求、设备异常、工具报错等真实阻塞时，要明确说明阻塞原因，不要伪装成功。
12. 任务完成后，用简洁自然语言直接说明结果，不要描述内部实现细节。
"""


def summarize_phone_events(state: SubagentRoundState, *, limit: int = 6) -> str:
    """
    将最近几次 phone 工具执行压缩为简短摘要。

    Args:
        state: 当前 phone 子 agent 的轮次状态。
        limit: 最多保留多少条最近工具事件。

    Returns:
        适合注入到当前轮提示词中的动作历史摘要。
    """
    if not state.tool_events:
        return "暂无已执行动作。"

    lines: list[str] = []
    for event in state.tool_events[-limit:]:
        rendered_args = ", ".join(
            f"{key}={value!r}" for key, value in event.arguments.items()
        ) or "无参数"
        result = summarize_phone_content(event.result)
        lines.append(f"- 第 {event.iteration} 轮：{event.tool_name}({rendered_args}) -> {result}")
    return "\n".join(lines)


def summarize_phone_content(content: Any) -> str:
    """
    压缩 phone 工具结果或观察内容。

    Args:
        content: 原始内容。

    Returns:
        便于提示词使用的简短文本。
    """
    if content is None:
        return ""

    if isinstance(content, str):
        compact = " ".join(content.strip().split())
        return compact[:240] + ("..." if len(compact) > 240 else "")

    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if not isinstance(block, dict):
                parts.append(str(block))
                continue
            block_type = block.get("type")
            if block_type == "text":
                text = " ".join(str(block.get("text", "")).split())
                parts.append(text[:120] + ("..." if len(text) > 120 else ""))
            elif block_type == "image_url":
                parts.append("[当前截图]")
            else:
                parts.append(f"[{block_type}]")
        return " | ".join(part for part in parts if part)

    return str(content)


def build_phone_round_messages(
    state: SubagentRoundState,
    *,
    lang: Literal["cn", "en"] = "cn",
) -> list[dict[str, Any]]:
    """
    构建 phone profile 每一轮发送给 VLM 的消息。

    Args:
        state: 当前 round state，其中应已包含最新截图观察。
        lang: 提示语言。

    Returns:
        当前轮的非 system 消息列表。
    """
    recent_actions = summarize_phone_events(state)
    latest_observation = state.latest_observation if isinstance(state.latest_observation, list) else []

    if lang == "en":
        experience_block = (
            f"{state.retrieved_experience_block}\n\n"
            if state.retrieved_experience_block
            else ""
        )
        text = (
            f"[Original Task]\n{state.original_task}\n\n"
            f"{experience_block}"
            f"[Current Round]\n{state.iteration}\n\n"
            f"[Recent Actions]\n{recent_actions}\n\n"
            "Please inspect the attached screenshot and decide the next best action. "
            "If the task is already complete, reply with the final result directly."
        )
    else:
        experience_block = (
            f"{state.retrieved_experience_block}\n\n"
            if state.retrieved_experience_block
            else ""
        )
        text = (
            f"【原始任务】\n{state.original_task}\n\n"
            f"{experience_block}"
            f"【当前轮次】\n第 {state.iteration} 轮\n\n"
            f"【最近动作】\n{recent_actions}\n\n"
            "请结合当前截图，推理下一步操作。"
            "如果任务已经完成，请直接回复最终结果。"
        )

    content: list[dict[str, Any]] = [{"type": "text", "text": text}]
    content.extend(latest_observation)
    return [{"role": "user", "content": content}]
