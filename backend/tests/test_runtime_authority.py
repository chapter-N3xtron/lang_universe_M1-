from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException

from src import coding_agent, web_server
from src.runtime_authority import RuntimeIdentityError, authoritative_thread_id


def test_runtime_thread_identity_is_authoritative():
    config = {"configurable": {"thread_id": "agent-server-thread"}}

    assert (
        authoritative_thread_id("agent-server-thread", config, operation="test")
        == "agent-server-thread"
    )
    assert (
        authoritative_thread_id(None, config, operation="test") == "agent-server-thread"
    )


@pytest.mark.parametrize("declared", ["different-thread", "x" * 200])
def test_conflicting_runtime_thread_identity_fails_closed(declared):
    with pytest.raises(RuntimeIdentityError, match="conflicts"):
        authoritative_thread_id(
            declared,
            {"configurable": {"thread_id": "agent-server-thread"}},
            operation="test",
        )


def test_missing_thread_identity_fails_closed():
    with pytest.raises(RuntimeIdentityError, match="required"):
        authoritative_thread_id(None, None, operation="test")


def test_authoritative_thread_identity_is_not_truncated():
    thread_id = "thread-" + ("x" * 200)

    assert (
        authoritative_thread_id(
            thread_id,
            {"configurable": {"thread_id": thread_id}},
            operation="test",
        )
        == thread_id
    )


@pytest.mark.asyncio
async def test_standalone_coder_rejects_identity_conflict_before_agent_construction(
    monkeypatch, tmp_path
):
    called = False

    async def session_agent(*_args):
        nonlocal called
        called = True
        raise AssertionError("must not construct inner agent")

    monkeypatch.setattr(coding_agent, "_session_agent", session_agent)

    with pytest.raises(RuntimeIdentityError):
        await coding_agent.deep_agents_coding_node(
            {
                "messages": [{"role": "user", "content": "Do the work"}],
                "workspace": str(tmp_path),
                "thread_identity": "declared-thread",
            },
            {"configurable": {"thread_id": "agent-server-thread"}},
        )

    assert called is False


def test_legacy_manager_is_inert_in_production_paths():
    source_dir = Path(coding_agent.__file__).parent
    coding_source = (source_dir / "coding_agent.py").read_text()
    temporal_source = (source_dir / "coder_agent_server_activity.py").read_text()

    assert "coding_persistence" not in coding_source
    assert "coding_persistence" not in temporal_source
    assert "export_coding_session_state" not in coding_source


@pytest.mark.asyncio
async def test_legacy_reset_and_export_endpoints_are_gone():
    scope = web_server.CodingSessionScope(
        thread_id="thread", workspace="/tmp", user_id="user"
    )
    with pytest.raises(HTTPException) as reset:
        await web_server.reset_coding_session_api(scope)
    with pytest.raises(HTTPException) as export:
        await web_server.export_coding_session_api("thread", "/tmp", "user")

    assert reset.value.status_code == 410
    assert export.value.status_code == 410


def test_legacy_assets_remain_for_phase_nine_cleanup():
    assert Path(coding_agent.__file__).with_name("coding_persistence.py").exists()
