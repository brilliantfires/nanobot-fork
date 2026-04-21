"""Lightweight structured experience memory for phone subagents."""

from __future__ import annotations

import math
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import json_repair
from loguru import logger
from openai import AsyncOpenAI

from nanobot.agent.subagent_profiles import SubagentRoundState
from nanobot.config.schema import PhoneExperienceMemoryConfig
from nanobot.providers.base import LLMProvider
from nanobot.utils.helpers import ensure_dir


@dataclass
class PendingFeedback:
    """Track the latest unresolved experience waiting for user feedback."""

    experience_id: str
    created_at: datetime
    remaining_turns: int
    task_intent: str
    task_raw: str


class PhoneExperienceManager:
    """Manage phone-specific experience extraction, retrieval, and feedback."""

    _POSITIVE_MARKERS = ("好了", "可以了", "对的", "谢谢", "就这样", "行了", "没问题")
    _NEGATIVE_MARKERS = ("不是这个", "没成功", "点错了", "重新来", "还是不对", "不对", "失败")

    def __init__(
        self,
        workspace: Path,
        provider: LLMProvider,
        model: str,
        phone_api_key: str,
        phone_base_url: str | None,
        phone_extra_headers: dict[str, str] | None,
        config: PhoneExperienceMemoryConfig,
    ):
        self.workspace = workspace
        self.provider = provider
        self.model = model
        self.phone_api_key = phone_api_key or "no-key"
        self.phone_base_url = phone_base_url
        self.phone_extra_headers = phone_extra_headers or {}
        self.config = config

        self._collection: Any | None = None
        self._embedding_client: AsyncOpenAI | None = None
        self._pending_feedback: dict[str, PendingFeedback] = {}

    @property
    def enabled(self) -> bool:
        return self.config.enable

    async def prepare_task(
        self,
        state: SubagentRoundState,
        session_key: str | None,
    ) -> None:
        """Extract a task signature and retrieve similar experiences."""
        if not self.enabled:
            return

        signature = await self._extract_task_signature(state.original_task)
        state.task_signature = signature
        state.retrieved_experience_block = await self._retrieve_experience_block(
            signature=signature,
            task_raw=state.original_task,
        )

        if session_key:
            self._expire_pending_feedback(session_key, now=datetime.now())

    async def finalize_task(
        self,
        state: SubagentRoundState,
        final_result: str | None,
        status: str,
        session_key: str | None,
    ) -> None:
        """Summarize a phone run into reusable structured experience."""
        if not self.enabled:
            return

        signature = state.task_signature or await self._extract_task_signature(state.original_task)
        outcome_status = self._infer_outcome_status(status, final_result)
        summary_input = self._build_summary_input_text(state, final_result, outcome_status)
        summary = await self._summarize_experience(
            task_raw=state.original_task,
            task_signature=signature,
            summary_input=summary_input,
        )

        if outcome_status != "success" or not summary.get("reusable"):
            return

        retrieval_text = self._build_retrieval_text(
            task_intent=summary.get("task_intent") or signature.get("task_intent") or "",
            task_raw=state.original_task,
        )
        embedding = await self._embed_text(retrieval_text)

        experience_id = await self._upsert_experience(
            retrieval_text=retrieval_text,
            embedding=embedding,
            metadata=self._build_metadata(
                summary=summary,
                session_key=session_key,
                outcome_status=outcome_status,
            ),
        )
        if experience_id and session_key:
            self._pending_feedback[session_key] = PendingFeedback(
                experience_id=experience_id,
                created_at=datetime.now(),
                remaining_turns=max(1, self.config.feedback_window_turns),
                task_intent=summary.get("task_intent") or signature.get("task_intent") or "",
                task_raw=state.original_task,
            )

    def observe_feedback(self, session_key: str, user_message: str) -> None:
        """Infer whether a follow-up user message validates or rejects the last experience."""
        if not self.enabled or not session_key or not user_message.strip():
            return

        pending = self._pending_feedback.get(session_key)
        if pending is None:
            return

        now = datetime.now()
        if self._is_feedback_expired(pending, now):
            self._pending_feedback.pop(session_key, None)
            return

        verdict = self._classify_feedback(pending, user_message)
        if verdict is None:
            pending.remaining_turns -= 1
            if pending.remaining_turns <= 0:
                self._pending_feedback.pop(session_key, None)
            return

        try:
            self._apply_feedback_update(pending.experience_id, verdict)
        except Exception as exc:
            logger.warning("Failed to update phone experience feedback: {}", exc)
        finally:
            self._pending_feedback.pop(session_key, None)

    async def _extract_task_signature(self, task_raw: str) -> dict[str, str]:
        fallback = {
            "task_intent": self._clip(task_raw.replace("\n", " ").strip(), 48) or "手机任务",
            "app_name": "",
            "operation_mode": "navigate-act-verify",
        }
        response = await self.provider.chat_with_retry(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是一个手机任务签名抽取器。"
                        "请只返回 JSON，对任务抽取 3 个字段："
                        '`task_intent`（一句短语）、`app_name`（能确定时填写，否则空字符串）、'
                        '`operation_mode`（例如 search-select-send / navigate-act-verify）。'
                    ),
                },
                {
                    "role": "user",
                    "content": f"任务文本：\n{task_raw.strip()}",
                },
            ],
            tools=None,
            model=self.model,
            temperature=0.0,
            max_tokens=300,
        )
        parsed = self._parse_json_response(response.content, fallback=fallback)
        return {
            "task_intent": str(parsed.get("task_intent") or fallback["task_intent"]).strip(),
            "app_name": str(parsed.get("app_name") or "").strip(),
            "operation_mode": str(parsed.get("operation_mode") or fallback["operation_mode"]).strip(),
        }

    async def _summarize_experience(
        self,
        task_raw: str,
        task_signature: dict[str, str],
        summary_input: str,
    ) -> dict[str, Any]:
        fallback = {
            "task_intent": task_signature.get("task_intent", ""),
            "app_name": task_signature.get("app_name", ""),
            "operation_mode": task_signature.get("operation_mode", ""),
            "trace_summary": self._clip(summary_input, 240),
            "experience_summary": self._clip(summary_input, 180),
            "guidance_do": "先确认当前页面，再执行下一步最小动作。",
            "guidance_avoid": "不要在同一无效位置重复点击。",
            "reusable": True,
        }
        response = await self.provider.chat_with_retry(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是一个手机 agent 经验总结器。"
                        "请根据任务和执行轨迹，总结可复用经验。"
                        "只返回 JSON，字段为："
                        '`task_intent`、`app_name`、`operation_mode`、`trace_summary`、'
                        '`experience_summary`、`guidance_do`、`guidance_avoid`、`reusable`。'
                        "`guidance_do` 和 `guidance_avoid` 必须简短、可操作。"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"任务原文：\n{task_raw.strip()}\n\n"
                        f"任务签名：\n"
                        f"- task_intent: {task_signature.get('task_intent', '')}\n"
                        f"- app_name: {task_signature.get('app_name', '')}\n"
                        f"- operation_mode: {task_signature.get('operation_mode', '')}\n\n"
                        f"执行轨迹摘要：\n{summary_input}"
                    ),
                },
            ],
            tools=None,
            model=self.model,
            temperature=0.0,
            max_tokens=700,
        )
        parsed = self._parse_json_response(response.content, fallback=fallback)
        return {
            "task_intent": str(parsed.get("task_intent") or fallback["task_intent"]).strip(),
            "app_name": str(parsed.get("app_name") or fallback["app_name"]).strip(),
            "operation_mode": str(parsed.get("operation_mode") or fallback["operation_mode"]).strip(),
            "trace_summary": self._clip(str(parsed.get("trace_summary") or fallback["trace_summary"]), 260),
            "experience_summary": self._clip(
                str(parsed.get("experience_summary") or fallback["experience_summary"]),
                180,
            ),
            "guidance_do": self._clip(str(parsed.get("guidance_do") or fallback["guidance_do"]), 120),
            "guidance_avoid": self._clip(
                str(parsed.get("guidance_avoid") or fallback["guidance_avoid"]),
                120,
            ),
            "reusable": bool(parsed.get("reusable", fallback["reusable"])),
        }

    async def _retrieve_experience_block(
        self,
        signature: dict[str, str],
        task_raw: str,
    ) -> str | None:
        query_text = self._build_retrieval_text(signature.get("task_intent", ""), task_raw)
        embedding = await self._embed_text(query_text)
        records = self._query_experiences(signature=signature, embedding=embedding, query_text=query_text)
        if not records:
            return None
        return self._render_experience_block(records)

    async def _embed_text(self, text: str) -> list[float] | None:
        if not text.strip():
            return None
        try:
            client = self._get_embedding_client()
            response = await client.embeddings.create(
                model=self.config.embedding_model,
                input=text,
            )
            if response.data:
                return [float(x) for x in response.data[0].embedding]
        except Exception as exc:
            logger.warning("Phone experience embedding failed: {}", exc)
        return None

    def _get_embedding_client(self) -> AsyncOpenAI:
        if self._embedding_client is None:
            self._embedding_client = AsyncOpenAI(
                api_key=self.phone_api_key,
                base_url=self.phone_base_url,
                default_headers=self.phone_extra_headers,
            )
        return self._embedding_client

    def _get_collection(self) -> Any | None:
        if self._collection is not None:
            return self._collection
        try:
            import chromadb
        except ImportError:
            logger.warning("chromadb is not installed; phone experience memory is disabled.")
            return None

        storage_path = (
            Path(self.config.chroma_path).expanduser()
            if self.config.chroma_path
            else self.workspace / "memory" / "phone_agent" / "chroma"
        )
        client = chromadb.PersistentClient(path=str(ensure_dir(storage_path)))
        self._collection = client.get_or_create_collection(
            name="phone_experiences",
            metadata={"hnsw:space": "cosine"},
        )
        return self._collection

    async def _upsert_experience(
        self,
        retrieval_text: str,
        embedding: list[float] | None,
        metadata: dict[str, Any],
    ) -> str | None:
        collection = self._get_collection()
        if collection is None:
            return None

        experience_id = self._find_duplicate_id(
            collection=collection,
            retrieval_text=retrieval_text,
            embedding=embedding,
            metadata=metadata,
        ) or str(uuid.uuid4())
        existing = self._get_record(collection, experience_id)
        if existing is not None:
            merged_metadata = self._merge_metadata(existing["metadata"], metadata)
            document = retrieval_text
            embedding_to_write = embedding or existing.get("embedding")
            self._collection_update(
                collection,
                ids=[experience_id],
                documents=[document],
                metadatas=[merged_metadata],
                embeddings=[embedding_to_write] if embedding_to_write is not None else None,
            )
            return experience_id

        self._collection_add(
            collection,
            ids=[experience_id],
            documents=[retrieval_text],
            metadatas=[metadata],
            embeddings=[embedding] if embedding is not None else None,
        )
        return experience_id

    def _query_experiences(
        self,
        signature: dict[str, str],
        embedding: list[float] | None,
        query_text: str,
    ) -> list[dict[str, Any]]:
        collection = self._get_collection()
        if collection is None:
            return []

        if embedding is not None:
            payload = collection.query(
                query_embeddings=[embedding],
                n_results=max(self.config.top_k * 3, self.config.top_k),
                include=["documents", "metadatas", "distances"],
            )
            records = self._normalize_query_results(payload)
        else:
            payload = collection.get(include=["documents", "metadatas"])
            records = self._normalize_get_results(payload)

        if not records:
            return []

        reranked: list[dict[str, Any]] = []
        for record in records:
            metadata = record["metadata"]
            if metadata.get("outcome_status") != "success":
                continue
            if metadata.get("indexed") is False:
                continue

            similarity = record.get("similarity")
            if similarity is None:
                similarity = self._text_overlap_score(query_text, record.get("document", ""))
            score = similarity
            if signature.get("app_name") and metadata.get("app_name") == signature.get("app_name"):
                score += 0.08
            if signature.get("task_intent") and metadata.get("task_intent") == signature.get("task_intent"):
                score += 0.05
            if metadata.get("feedback_state") == "positive":
                score += 0.05
            score += float(metadata.get("quality_score", 0.0)) * 0.05
            if score < self.config.min_score:
                continue
            reranked.append({**record, "score": score})

        reranked.sort(key=lambda item: item["score"], reverse=True)
        return reranked[: self.config.top_k]

    def _render_experience_block(self, records: list[dict[str, Any]]) -> str | None:
        lines = ["【相似经验】"]
        total_length = len(lines[0])

        for idx, record in enumerate(records, start=1):
            metadata = record["metadata"]
            scene = " / ".join(
                part
                for part in (
                    metadata.get("app_name") or "",
                    metadata.get("task_intent") or "",
                    metadata.get("operation_mode") or "",
                )
                if part
            ) or "相似手机任务"
            item = (
                f"{idx}. 场景：{self._clip(scene, 42)}；"
                f"可参考：{self._clip(metadata.get('guidance_do', ''), 65)}；"
                f"避免：{self._clip(metadata.get('guidance_avoid', ''), 65)}"
            )
            if total_length + len(item) + 1 > 900:
                break
            lines.append(item)
            total_length += len(item) + 1

        return "\n".join(lines) if len(lines) > 1 else None

    def _build_summary_input_text(
        self,
        state: SubagentRoundState,
        final_result: str | None,
        outcome_status: str,
    ) -> str:
        sections = [
            f"原始任务: {self._clean_jsonish_text(state.original_task)}",
            f"任务意图: {self._clean_jsonish_text((state.task_signature or {}).get('task_intent', ''))}",
            f"结果状态: {outcome_status}",
        ]

        for event in state.tool_events[-8:]:
            args_text = self._flatten_value(event.arguments)
            result_text = self._flatten_value(event.result)
            sections.append(
                self._clip(
                    f"第 {event.iteration} 轮 动作 {event.tool_name} 参数 {args_text} 结果 {result_text}",
                    260,
                )
            )

        if state.latest_assistant_content:
            sections.append(
                f"模型最后输出: {self._clip(self._clean_jsonish_text(state.latest_assistant_content), 220)}"
            )
        if final_result:
            sections.append(f"最终输出: {self._clip(self._clean_jsonish_text(final_result), 220)}")
        return "\n".join(filter(None, sections))

    def _build_metadata(
        self,
        summary: dict[str, Any],
        session_key: str | None,
        outcome_status: str,
    ) -> dict[str, Any]:
        now = datetime.now().isoformat()
        return {
            "task_intent": summary.get("task_intent", ""),
            "app_name": summary.get("app_name", ""),
            "operation_mode": summary.get("operation_mode", ""),
            "outcome_status": outcome_status,
            "feedback_state": "unknown",
            "quality_score": 0.6,
            "experience_summary": summary.get("experience_summary", ""),
            "guidance_do": summary.get("guidance_do", ""),
            "guidance_avoid": summary.get("guidance_avoid", ""),
            "trace_summary": summary.get("trace_summary", ""),
            "session_key": session_key or "",
            "created_at": now,
            "updated_at": now,
            "indexed": True,
        }

    def _find_duplicate_id(
        self,
        collection: Any,
        retrieval_text: str,
        embedding: list[float] | None,
        metadata: dict[str, Any],
    ) -> str | None:
        if embedding is not None:
            payload = collection.query(
                query_embeddings=[embedding],
                n_results=5,
                include=["documents", "metadatas", "distances"],
            )
            for record in self._normalize_query_results(payload):
                current = record["metadata"]
                if (
                    current.get("app_name") == metadata.get("app_name")
                    and current.get("task_intent") == metadata.get("task_intent")
                    and current.get("operation_mode") == metadata.get("operation_mode")
                    and (record.get("similarity") or 0.0) >= 0.9
                ):
                    return record["id"]

        payload = collection.get(include=["documents", "metadatas"])
        for record in self._normalize_get_results(payload):
            current = record["metadata"]
            if (
                current.get("app_name") == metadata.get("app_name")
                and current.get("task_intent") == metadata.get("task_intent")
                and current.get("operation_mode") == metadata.get("operation_mode")
                and record.get("document") == retrieval_text
            ):
                return record["id"]
        return None

    def _get_record(self, collection: Any, experience_id: str) -> dict[str, Any] | None:
        payload = collection.get(
            ids=[experience_id],
            include=["documents", "metadatas", "embeddings"],
        )
        ids = payload.get("ids") or []
        if not ids:
            return None
        return {
            "id": ids[0],
            "document": (payload.get("documents") or [""])[0],
            "metadata": (payload.get("metadatas") or [{}])[0],
            "embedding": (payload.get("embeddings") or [None])[0],
        }

    def _merge_metadata(self, current: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
        merged = dict(current)
        merged.update(new)
        merged["quality_score"] = max(
            float(current.get("quality_score", 0.0)),
            float(new.get("quality_score", 0.0)),
        )
        merged["experience_summary"] = new.get("experience_summary") or current.get("experience_summary", "")
        merged["guidance_do"] = new.get("guidance_do") or current.get("guidance_do", "")
        merged["guidance_avoid"] = new.get("guidance_avoid") or current.get("guidance_avoid", "")
        merged["trace_summary"] = new.get("trace_summary") or current.get("trace_summary", "")
        merged["updated_at"] = datetime.now().isoformat()
        merged["indexed"] = bool(merged.get("indexed", True))
        return merged

    def _apply_feedback_update(self, experience_id: str, verdict: str) -> None:
        collection = self._get_collection()
        if collection is None:
            return
        record = self._get_record(collection, experience_id)
        if record is None:
            return

        metadata = dict(record["metadata"])
        metadata["updated_at"] = datetime.now().isoformat()
        if verdict == "positive":
            metadata["feedback_state"] = "positive"
            metadata["quality_score"] = min(1.0, float(metadata.get("quality_score", 0.0)) + 0.2)
        else:
            metadata["feedback_state"] = "negative"
            metadata["quality_score"] = 0.0
            metadata["indexed"] = False

        self._collection_update(
            collection,
            ids=[experience_id],
            documents=[record["document"]],
            metadatas=[metadata],
            embeddings=[record["embedding"]] if record.get("embedding") is not None else None,
        )

    def _classify_feedback(self, pending: PendingFeedback, user_message: str) -> str | None:
        text = user_message.strip()
        if not text:
            return None
        if any(marker in text for marker in self._NEGATIVE_MARKERS):
            return "negative"
        if any(marker in text for marker in self._POSITIVE_MARKERS):
            return "positive"

        normalized = text.replace(" ", "")
        if pending.task_intent and pending.task_intent.replace(" ", "")[:8] in normalized:
            if any(marker in normalized for marker in ("重新", "改成", "还是", "再来")):
                return "negative"
        if pending.task_raw and self._text_overlap_score(pending.task_raw, text) >= 0.45:
            if any(marker in normalized for marker in ("重新", "改成", "重试")):
                return "negative"
        return None

    def _expire_pending_feedback(self, session_key: str, now: datetime) -> None:
        pending = self._pending_feedback.get(session_key)
        if pending and self._is_feedback_expired(pending, now):
            self._pending_feedback.pop(session_key, None)

    def _is_feedback_expired(self, pending: PendingFeedback, now: datetime) -> bool:
        return now - pending.created_at > timedelta(minutes=self.config.feedback_window_minutes)

    def _infer_outcome_status(self, status: str, final_result: str | None) -> str:
        text = (final_result or "").lower()
        if status != "ok" or text.startswith("error:"):
            return "error"
        blockers = ("登录", "验证码", "权限", "验证", "blocked", "无法继续", "cannot continue")
        if any(marker in (final_result or "") for marker in blockers):
            return "blocked"
        return "success"

    def _build_retrieval_text(self, task_intent: str, task_raw: str) -> str:
        return f"任务意图: {task_intent.strip()}\n原始任务: {task_raw.strip()}"

    def _normalize_query_results(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        ids = (payload.get("ids") or [[]])[0]
        documents = (payload.get("documents") or [[]])[0]
        metadatas = (payload.get("metadatas") or [[]])[0]
        distances = (payload.get("distances") or [[]])[0]

        records: list[dict[str, Any]] = []
        for idx, experience_id in enumerate(ids):
            distance = distances[idx] if idx < len(distances) else None
            similarity = self._distance_to_similarity(distance) if distance is not None else None
            records.append(
                {
                    "id": experience_id,
                    "document": documents[idx] if idx < len(documents) else "",
                    "metadata": metadatas[idx] if idx < len(metadatas) else {},
                    "distance": distance,
                    "similarity": similarity,
                }
            )
        return records

    def _normalize_get_results(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        ids = payload.get("ids") or []
        documents = payload.get("documents") or []
        metadatas = payload.get("metadatas") or []
        return [
            {
                "id": experience_id,
                "document": documents[idx] if idx < len(documents) else "",
                "metadata": metadatas[idx] if idx < len(metadatas) else {},
                "similarity": None,
            }
            for idx, experience_id in enumerate(ids)
        ]

    @staticmethod
    def _distance_to_similarity(distance: float | None) -> float:
        if distance is None:
            return 0.0
        return max(0.0, 1.0 - float(distance))

    def _text_overlap_score(self, left: str, right: str) -> float:
        left_tokens = {token for token in re.split(r"[\s,，。；;:/\n]+", left) if token}
        right_tokens = {token for token in re.split(r"[\s,，。；;:/\n]+", right) if token}
        if not left_tokens or not right_tokens:
            return 0.0
        intersection = len(left_tokens & right_tokens)
        denominator = math.sqrt(len(left_tokens) * len(right_tokens))
        return min(1.0, intersection / denominator) if denominator else 0.0

    def _flatten_value(self, value: Any) -> str:
        parts: list[str] = []

        def _visit(node: Any) -> None:
            if node is None:
                return
            if isinstance(node, dict):
                for key, inner in node.items():
                    key_text = self._clean_jsonish_text(str(key))
                    inner_text_before = len(parts)
                    _visit(inner)
                    if len(parts) == inner_text_before and key_text:
                        parts.append(key_text)
                return
            if isinstance(node, (list, tuple, set)):
                for inner in node:
                    _visit(inner)
                return
            text = self._clean_jsonish_text(str(node))
            if text:
                parts.append(text)

        _visit(value)
        compact = " | ".join(part for part in parts if part)
        return self._clip(compact, 220)

    def _clean_jsonish_text(self, text: str) -> str:
        cleaned = re.sub(r'[\{\}\[\]"]+', " ", text)
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned.strip()

    def _parse_json_response(
        self,
        content: str | None,
        *,
        fallback: dict[str, Any],
    ) -> dict[str, Any]:
        if not content:
            return fallback
        try:
            parsed = json_repair.loads(content)
            return parsed if isinstance(parsed, dict) else fallback
        except Exception:
            return fallback

    @staticmethod
    def _collection_add(collection: Any, **kwargs: Any) -> None:
        payload = {key: value for key, value in kwargs.items() if value is not None}
        collection.add(**payload)

    @staticmethod
    def _collection_update(collection: Any, **kwargs: Any) -> None:
        payload = {key: value for key, value in kwargs.items() if value is not None}
        collection.update(**payload)

    @staticmethod
    def _clip(text: str, limit: int) -> str:
        compact = " ".join(str(text).split())
        return compact[:limit] + ("..." if len(compact) > limit else "")
