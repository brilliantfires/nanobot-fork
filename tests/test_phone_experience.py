"""Tests for the PhoneAgent structured experience memory."""

from __future__ import annotations

from pathlib import Path

import pytest

from nanobot.agent.phone_experience import PhoneExperienceManager
from nanobot.agent.phone_prompt import build_phone_round_messages
from nanobot.agent.subagent_profiles import SubagentRoundState, SubagentToolEvent
from nanobot.config.schema import PhoneExperienceMemoryConfig
from nanobot.providers.base import LLMProvider, LLMResponse


class _FakeProvider(LLMProvider):
    async def chat(
        self,
        messages,
        tools=None,
        model=None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        reasoning_effort=None,
        tool_choice=None,
    ) -> LLMResponse:
        del tools, model, max_tokens, temperature, reasoning_effort, tool_choice
        system = messages[0]["content"]
        if "签名抽取器" in system:
            return LLMResponse(
                content=(
                    '{"task_intent":"发送微信消息",'
                    '"app_name":"微信","operation_mode":"search-select-send"}'
                )
            )
        return LLMResponse(
            content=(
                '{"task_intent":"发送微信消息","app_name":"微信",'
                '"operation_mode":"search-select-send",'
                '"trace_summary":"先定位输入框，再输入文本并发送。",'
                '"experience_summary":"发送前先确认聊天对象和输入框已聚焦。",'
                '"guidance_do":"确认聊天对象正确后再输入并发送。",'
                '"guidance_avoid":"不要在未聚焦时反复点击发送。",'
                '"reusable":true}'
            )
        )

    def get_default_model(self) -> str:
        return "test/model"


class _FakeCollection:
    def __init__(self) -> None:
        self.records: dict[str, dict] = {}

    def add(self, ids, documents, metadatas, embeddings=None):
        for idx, record_id in enumerate(ids):
            self.records[record_id] = {
                "id": record_id,
                "document": documents[idx],
                "metadata": metadatas[idx],
                "embedding": embeddings[idx] if embeddings is not None else None,
            }

    def update(self, ids, documents, metadatas, embeddings=None):
        for idx, record_id in enumerate(ids):
            record = self.records[record_id]
            record["document"] = documents[idx]
            record["metadata"] = metadatas[idx]
            if embeddings is not None:
                record["embedding"] = embeddings[idx]

    def get(self, ids=None, include=None):
        del include
        if ids is None:
            rows = list(self.records.values())
        else:
            rows = [self.records[record_id] for record_id in ids if record_id in self.records]
        return {
            "ids": [row["id"] for row in rows],
            "documents": [row["document"] for row in rows],
            "metadatas": [row["metadata"] for row in rows],
            "embeddings": [row["embedding"] for row in rows],
        }

    def query(self, query_embeddings, n_results, include=None):
        del include
        query = query_embeddings[0]
        rows = []
        for row in self.records.values():
            distance = _distance(query, row["embedding"] or [0.0, 0.0])
            rows.append((distance, row))
        rows.sort(key=lambda item: item[0])
        picked = rows[:n_results]
        return {
            "ids": [[row["id"] for _, row in picked]],
            "documents": [[row["document"] for _, row in picked]],
            "metadatas": [[row["metadata"] for _, row in picked]],
            "distances": [[distance for distance, _ in picked]],
        }


def _distance(left: list[float], right: list[float]) -> float:
    return sum(abs(a - b) for a, b in zip(left, right, strict=False))


@pytest.fixture
def experience_manager(tmp_path: Path, monkeypatch) -> tuple[PhoneExperienceManager, _FakeCollection]:
    manager = PhoneExperienceManager(
        workspace=tmp_path,
        provider=_FakeProvider(),
        model="test/model",
        phone_api_key="EMPTY",
        phone_base_url="http://localhost:8000/v1",
        phone_extra_headers=None,
        config=PhoneExperienceMemoryConfig(enable=True, min_score=0.1),
    )
    collection = _FakeCollection()
    monkeypatch.setattr(manager, "_get_collection", lambda: collection)

    async def _fake_embed(text: str) -> list[float]:
        if "微信" in text or "发送微信消息" in text:
            return [1.0, 0.0]
        return [0.0, 1.0]

    monkeypatch.setattr(manager, "_embed_text", _fake_embed)
    return manager, collection


@pytest.mark.asyncio
async def test_prepare_task_injects_similar_experience(
    experience_manager: tuple[PhoneExperienceManager, _FakeCollection],
) -> None:
    manager, collection = experience_manager
    collection.add(
        ids=["exp-1"],
        documents=["任务意图: 发送微信消息\n原始任务: 给张三发消息"],
        metadatas=[
            {
                "task_intent": "发送微信消息",
                "app_name": "微信",
                "operation_mode": "search-select-send",
                "outcome_status": "success",
                "feedback_state": "positive",
                "quality_score": 0.8,
                "experience_summary": "先确认聊天对象再发送。",
                "guidance_do": "先检查顶部聊天对象，再输入内容。",
                "guidance_avoid": "不要在未进入聊天页时点击发送。",
                "trace_summary": "进入聊天页并完成发送。",
                "session_key": "cli:other",
                "created_at": "2026-01-01T00:00:00",
                "updated_at": "2026-01-01T00:00:00",
                "indexed": True,
            }
        ],
        embeddings=[[1.0, 0.0]],
    )

    state = SubagentRoundState(original_task="用微信给张三发消息，说我马上到。")
    await manager.prepare_task(state, session_key="cli:test")

    assert state.task_signature == {
        "task_intent": "发送微信消息",
        "app_name": "微信",
        "operation_mode": "search-select-send",
    }
    assert state.retrieved_experience_block is not None
    assert "【相似经验】" in state.retrieved_experience_block
    assert "可参考" in state.retrieved_experience_block
    assert "避免" in state.retrieved_experience_block


@pytest.mark.asyncio
async def test_finalize_task_flattens_trace_and_writes_experience(
    experience_manager: tuple[PhoneExperienceManager, _FakeCollection],
) -> None:
    manager, collection = experience_manager
    state = SubagentRoundState(
        original_task='用微信给张三发消息 {"text":"今晚到"}',
        task_signature={
            "task_intent": "发送微信消息",
            "app_name": "微信",
            "operation_mode": "search-select-send",
        },
        latest_assistant_content='{"thought":"准备发送"}',
    )
    state.tool_events.append(
        SubagentToolEvent(
            iteration=1,
            tool_name="phone_tap",
            arguments={"target": {"label": "发送", "x": 880, "y": 930}},
            result={"status": "ok", "message": '已点击 {"id":"send"}'},
        )
    )

    trace_input = manager._build_summary_input_text(state, "已发送成功", "success")
    assert "{" not in trace_input
    assert "}" not in trace_input
    assert '"' not in trace_input

    await manager.finalize_task(state, final_result="已发送成功", status="ok", session_key="cli:test")

    records = list(collection.records.values())
    assert len(records) == 1
    record = records[0]
    assert "任务意图: 发送微信消息" in record["document"]
    assert record["metadata"]["task_intent"] == "发送微信消息"
    assert record["metadata"]["indexed"] is True
    assert record["metadata"]["guidance_do"] == "确认聊天对象正确后再输入并发送。"


@pytest.mark.asyncio
async def test_observe_feedback_deindexes_negative_experience(
    experience_manager: tuple[PhoneExperienceManager, _FakeCollection],
) -> None:
    manager, collection = experience_manager
    state = SubagentRoundState(
        original_task="用微信给张三发消息",
        task_signature={
            "task_intent": "发送微信消息",
            "app_name": "微信",
            "operation_mode": "search-select-send",
        },
    )

    await manager.finalize_task(state, final_result="已发送成功", status="ok", session_key="cli:test")
    record_id = next(iter(collection.records))

    manager.observe_feedback("cli:test", "不是这个，重新来")

    metadata = collection.records[record_id]["metadata"]
    assert metadata["feedback_state"] == "negative"
    assert metadata["quality_score"] == 0.0
    assert metadata["indexed"] is False


def test_build_phone_round_messages_includes_experience_block() -> None:
    state = SubagentRoundState(
        original_task="打开微信",
        iteration=1,
        retrieved_experience_block=(
            "【相似经验】\n"
            "1. 场景：微信 / 发送微信消息；可参考：先确认聊天对象。；避免：不要误触发送。"
        ),
    )
    messages = build_phone_round_messages(state, lang="cn")
    text = messages[0]["content"][0]["text"]

    assert "【原始任务】" in text
    assert "【相似经验】" in text
