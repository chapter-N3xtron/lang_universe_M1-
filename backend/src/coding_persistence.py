"""Durable, repository-scoped persistence for nested Deep Agents runs."""

from __future__ import annotations

import asyncio
import hashlib
import os
from contextlib import AbstractAsyncContextManager
from pathlib import Path
from typing import Any

from langchain_core.messages import BaseMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

DEFAULT_CHECKPOINT_FILE = (
    Path(__file__).resolve().parent.parent / "data" / "deep_agents_checkpoints.sqlite3"
)


def coding_session_id(
    *, thread_identity: str, workspace: Path, user_identity: str = "anonymous"
) -> str:
    """Return an opaque session ID isolated by user, UI thread, and repository."""
    if not thread_identity:
        raise ValueError("thread identity is required")
    thread_key = str(thread_identity)
    user_key = str(user_identity or "anonymous")
    resolved = workspace.resolve(strict=True)
    material = "\0".join(
        ("coding-session-v1", user_key, thread_key, str(resolved))
    )
    digest = hashlib.sha256(material.encode()).hexdigest()
    return f"coding-v1-{digest}"


def _message_export(message: Any) -> dict[str, Any]:
    if isinstance(message, BaseMessage):
        return {
            "type": message.type,
            "content": message.content,
            "tool_calls": getattr(message, "tool_calls", []),
        }
    if isinstance(message, dict):
        return {
            "type": message.get("type") or message.get("role") or "unknown",
            "content": message.get("content", ""),
            "tool_calls": message.get("tool_calls", []),
        }
    return {"type": type(message).__name__, "content": str(message)}


class CodingCheckpointerManager:
    """Lazily owns one async LangGraph checkpointer for the process."""

    def __init__(
        self,
        database_uri: str | None = None,
        checkpoint_file: Path | None = None,
    ):
        self.database_uri = database_uri
        self.checkpoint_file = checkpoint_file
        self._context: AbstractAsyncContextManager | None = None
        self._checkpointer: BaseCheckpointSaver | None = None
        self._lock = asyncio.Lock()

    async def get(self) -> BaseCheckpointSaver:
        if self._checkpointer is not None:
            return self._checkpointer
        async with self._lock:
            if self._checkpointer is not None:
                return self._checkpointer
            database_uri = self.database_uri or os.getenv(
                "CODING_CHECKPOINT_DB_URI", ""
            )
            if database_uri:
                context = AsyncPostgresSaver.from_conn_string(database_uri)
            else:
                checkpoint_file = (
                    self.checkpoint_file
                    or Path(
                        os.getenv(
                            "CODING_CHECKPOINT_FILE", str(DEFAULT_CHECKPOINT_FILE)
                        )
                    )
                ).resolve()
                checkpoint_file.parent.mkdir(parents=True, exist_ok=True)
                context = AsyncSqliteSaver.from_conn_string(str(checkpoint_file))
            checkpointer = await context.__aenter__()
            await checkpointer.setup()
            self._context = context
            self._checkpointer = checkpointer
            return checkpointer

    async def reset(self, session_id: str) -> bool:
        checkpointer = await self.get()
        existed = await checkpointer.aget_tuple(
            {"configurable": {"thread_id": session_id}}
        )
        await checkpointer.adelete_thread(session_id)
        return existed is not None

    async def export(self, session_id: str) -> dict[str, Any]:
        checkpointer = await self.get()
        config = {"configurable": {"thread_id": session_id}}
        checkpoint_tuple = await checkpointer.aget_tuple(config)
        if checkpoint_tuple is None:
            return {"session_id": session_id, "exists": False, "messages": []}
        checkpoint = checkpoint_tuple.checkpoint
        values = checkpoint.get("channel_values", {})
        if not values.get("messages"):
            async for candidate in checkpointer.alist(config, limit=50):
                candidate_values = candidate.checkpoint.get("channel_values", {})
                if candidate_values.get("messages"):
                    checkpoint = candidate.checkpoint
                    values = candidate_values
                    break
        messages = [_message_export(message) for message in values.get("messages", [])]
        return {
            "session_id": session_id,
            "exists": True,
            "checkpoint_id": checkpoint.get("id", ""),
            "created_at": checkpoint.get("ts", ""),
            "messages": messages,
        }

    async def close(self) -> None:
        async with self._lock:
            if self._context is not None:
                await self._context.__aexit__(None, None, None)
            self._context = None
            self._checkpointer = None


_MANAGER = CodingCheckpointerManager()


async def get_coding_checkpointer() -> BaseCheckpointSaver:
    return await _MANAGER.get()


async def reset_coding_session(session_id: str) -> bool:
    return await _MANAGER.reset(session_id)


async def export_coding_session(session_id: str) -> dict[str, Any]:
    return await _MANAGER.export(session_id)


async def reset_coding_session_for_scope(
    *, thread_identity: str, workspace: Path, user_identity: str = "anonymous"
) -> bool:
    session_id = coding_session_id(
        thread_identity=thread_identity,
        workspace=workspace,
        user_identity=user_identity,
    )
    return await reset_coding_session(session_id)


async def export_coding_session_for_scope(
    *, thread_identity: str, workspace: Path, user_identity: str = "anonymous"
) -> dict[str, Any]:
    session_id = coding_session_id(
        thread_identity=thread_identity,
        workspace=workspace,
        user_identity=user_identity,
    )
    return await export_coding_session(session_id)
