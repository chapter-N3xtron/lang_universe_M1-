"""Durability and isolation tests for nested Deep Agents sessions."""

import asyncio
import uuid

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.types import Command
from pydantic import PrivateAttr


class PersistentToolModel(BaseChatModel):
    _responses: list[AIMessage] = PrivateAttr()
    _seen_messages: list = PrivateAttr(default_factory=list)

    def __init__(self, responses):
        super().__init__()
        self._responses = list(responses)
        self._seen_messages = []

    @property
    def _llm_type(self):
        return "persistence-test"

    def bind_tools(self, _tools, **_kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **_kwargs):
        self._seen_messages.append(list(messages))
        return ChatResult(
            generations=[ChatGeneration(message=self._responses.pop(0))]
        )


def _write_request():
    return AIMessage(
        content="",
        tool_calls=[
            {
                "name": "approved_write_file",
                "args": {"file_path": "/durable.txt", "content": "persisted"},
                "id": "durable-write",
            }
        ],
    )


def test_session_id_is_deterministic_and_isolated(tmp_path):
    from src.coding_persistence import coding_session_id

    other = tmp_path / "other"
    other.mkdir()
    first = coding_session_id(
        thread_identity="thread-1", workspace=tmp_path, user_identity="user-a"
    )
    assert first == coding_session_id(
        thread_identity="thread-1", workspace=tmp_path, user_identity="user-a"
    )
    assert first != coding_session_id(
        thread_identity="thread-1", workspace=other, user_identity="user-a"
    )
    assert first != coding_session_id(
        thread_identity="thread-1", workspace=tmp_path, user_identity="user-b"
    )
    assert str(tmp_path) not in first
    assert "user-a" not in first


def test_session_id_accepts_runtime_uuid_identifiers(tmp_path):
    from src.coding_persistence import coding_session_id

    session_id = coding_session_id(
        thread_identity=uuid.uuid4(),
        workspace=tmp_path,
        user_identity=uuid.uuid4(),
    )

    assert session_id.startswith("coding-v1-")


def test_pending_approval_resumes_after_checkpointer_restart(monkeypatch, tmp_path):
    from src import coding_agent
    from src.coding_persistence import CodingCheckpointerManager

    database = tmp_path / "checkpoints.sqlite3"
    session_id = "coding-v1-restart-test"
    config = {"configurable": {"thread_id": session_id}}

    async def scenario():
        first_manager = CodingCheckpointerManager(checkpoint_file=database)
        first_saver = await first_manager.get()
        first_model = PersistentToolModel([_write_request()])
        monkeypatch.setattr(coding_agent, "get_coding_llm", lambda _name: first_model)
        first_app = coding_agent._build_deep_agent(
            tmp_path,
            None,
            execution_mode="approval",
            checkpointer=first_saver,
        )
        first = await first_app.ainvoke(
            {"messages": [{"role": "user", "content": "write it"}]},
            config=config,
        )
        assert len(first["__interrupt__"]) == 1
        await first_manager.close()

        second_manager = CodingCheckpointerManager(checkpoint_file=database)
        second_saver = await second_manager.get()
        second_model = PersistentToolModel([AIMessage(content="finished")])
        monkeypatch.setattr(coding_agent, "get_coding_llm", lambda _name: second_model)
        second_app = coding_agent._build_deep_agent(
            tmp_path,
            None,
            execution_mode="approval",
            checkpointer=second_saver,
        )
        snapshot = await second_app.aget_state(config)
        assert any(task.interrupts for task in snapshot.tasks)
        result = await second_app.ainvoke(
            Command(resume={"decisions": [{"type": "approve"}]}),
            config=config,
        )
        assert result["messages"][-1].content == "finished"
        await second_manager.close()

    asyncio.run(scenario())
    assert (tmp_path / "durable.txt").read_text() == "persisted"


def test_conversation_history_survives_restart(monkeypatch, tmp_path):
    from src import coding_agent
    from src.coding_persistence import CodingCheckpointerManager

    database = tmp_path / "history.sqlite3"
    config = {"configurable": {"thread_id": "coding-v1-history"}}

    async def scenario():
        first_manager = CodingCheckpointerManager(checkpoint_file=database)
        first_model = PersistentToolModel([AIMessage(content="answer one")])
        monkeypatch.setattr(coding_agent, "get_coding_llm", lambda _name: first_model)
        first_app = coding_agent._build_deep_agent(
            tmp_path, None, checkpointer=await first_manager.get()
        )
        await first_app.ainvoke(
            {"messages": [{"role": "user", "content": "question one"}]},
            config=config,
        )
        await first_manager.close()

        second_manager = CodingCheckpointerManager(checkpoint_file=database)
        second_model = PersistentToolModel([AIMessage(content="answer two")])
        monkeypatch.setattr(coding_agent, "get_coding_llm", lambda _name: second_model)
        second_app = coding_agent._build_deep_agent(
            tmp_path, None, checkpointer=await second_manager.get()
        )
        await second_app.ainvoke(
            {"messages": [{"role": "user", "content": "question two"}]},
            config=config,
        )
        contents = [message.content for message in second_model._seen_messages[0]]
        assert "question one" in contents
        assert "answer one" in contents
        assert "question two" in contents
        await second_manager.close()

    asyncio.run(scenario())


def test_export_and_reset_affect_only_selected_session(monkeypatch, tmp_path):
    from src import coding_agent
    from src.coding_persistence import CodingCheckpointerManager

    async def scenario():
        manager = CodingCheckpointerManager(
            checkpoint_file=tmp_path / "lifecycle.sqlite3"
        )
        saver = await manager.get()
        model_a = PersistentToolModel([AIMessage(content="session a")])
        monkeypatch.setattr(coding_agent, "get_coding_llm", lambda _name: model_a)
        app_a = coding_agent._build_deep_agent(tmp_path, None, checkpointer=saver)
        await app_a.ainvoke(
            {"messages": [{"role": "user", "content": "alpha"}]},
            config={"configurable": {"thread_id": "session-a"}},
        )

        model_b = PersistentToolModel([AIMessage(content="session b")])
        monkeypatch.setattr(coding_agent, "get_coding_llm", lambda _name: model_b)
        app_b = coding_agent._build_deep_agent(tmp_path, None, checkpointer=saver)
        await app_b.ainvoke(
            {"messages": [{"role": "user", "content": "beta"}]},
            config={"configurable": {"thread_id": "session-b"}},
        )

        exported = await manager.export("session-a")
        assert exported["exists"] is True
        assert await manager.reset("session-a") is True
        assert (await manager.export("session-a"))["exists"] is False
        assert (await manager.export("session-b"))["exists"] is True
        await manager.close()

    asyncio.run(scenario())


def test_scoped_export_reads_reconstructed_agent_state(monkeypatch, tmp_path):
    from src import coding_agent

    class App:
        async def aget_state(self, _config):
            return type(
                "Snapshot",
                (),
                {
                    "values": {
                        "messages": [
                            AIMessage(content="exported coding conversation")
                        ]
                    },
                    "created_at": "2026-07-30T00:00:00Z",
                },
            )()

    async def session_agent(*_args):
        return App()

    monkeypatch.setattr(coding_agent, "_session_agent", session_agent)
    result = asyncio.run(
        coding_agent.export_coding_session_state(
            thread_identity="export-thread",
            workspace=tmp_path,
            user_identity="export-user",
        )
    )
    assert result["exists"] is True
    assert result["messages"][0]["content"] == "exported coding conversation"
