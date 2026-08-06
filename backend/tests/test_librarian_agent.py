from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from src import librarian_agent


@pytest.mark.asyncio
async def test_librarian_passes_through_all_messages_emitted_by_upstream_graph():
    clarification = AIMessage(content="Which environments should I compare?")
    confirmation = AIMessage(content="I will begin the research.")
    upstream_result = {
        "messages": [
            HumanMessage(content="Research feline navigation."),
            clarification,
            confirmation,
        ]
    }
    config = {"configurable": {"thread_id": "librarian-smoke"}}

    with patch.object(
        librarian_agent.deep_researcher,
        "ainvoke",
        new=AsyncMock(return_value=upstream_result),
    ) as invoke:
        result = await librarian_agent.librarian_agent(
            {"messages": [{"role": "user", "content": "Research feline navigation."}]},
            config,
        )

    invoke.assert_awaited_once()
    assert invoke.await_args.kwargs["config"] is config
    assert invoke.await_args.args[0]["messages"] == [
        {"role": "user", "content": "Research feline navigation."}
    ]
    assert result == {"messages": [clarification, confirmation]}
