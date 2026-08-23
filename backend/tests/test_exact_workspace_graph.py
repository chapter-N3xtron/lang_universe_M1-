"""Graph-level exact-workspace preservation tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from langgraph.checkpoint.memory import InMemorySaver


@pytest.mark.asyncio
async def test_host_only_workspace_is_forwarded_without_container_substitution(
    tmp_path,
):
    missing = tmp_path / "missing-selected-repository"
    jasper_result = {
        "messages": [{"role": "assistant", "content": "inspected by Custodian"}],
        "visual_artifacts": [],
    }

    with (
        patch(
            "src.chat_ui.call_jasper", new=AsyncMock(return_value=jasper_result)
        ) as call_jasper,
        patch(
            "src.chat_ui.record_session_projection", new=AsyncMock()
        ) as record_projection,
    ):
        from src.chat_ui import create_chat_ui

        app = create_chat_ui().compile(checkpointer=InMemorySaver())
        result = await app.ainvoke(
            {
                "messages": [{"role": "user", "content": "Inspect the repository"}],
                "workspace": str(missing),
                "target_agent": "jasper",
                "execution_mode": "read_only",
            },
            config={"configurable": {"thread_id": "missing-workspace"}},
        )

    call_jasper.assert_awaited_once()
    assert call_jasper.await_args.args[0]["workspace"] == str(missing)
    record_projection.assert_awaited_once()
    assert result["workspace"] == str(missing)
    assert result["messages"][-1]["content"] == "inspected by Custodian"
