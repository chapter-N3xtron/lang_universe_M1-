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
    assert invoke.await_args.kwargs["config"] == config
    assert [message.content for message in result["messages"]] == [
        clarification.content,
        confirmation.content,
    ]


@pytest.mark.asyncio
async def test_librarian_uses_handoff_task_as_research_input():
    report = AIMessage(content="A sourced report.")
    config = {"configurable": {"thread_id": "librarian-handoff"}}

    with patch.object(
        librarian_agent.deep_researcher,
        "ainvoke",
        new=AsyncMock(
            return_value={
                "messages": [
                    HumanMessage(content="Research feline navigation."),
                    report,
                ]
            }
        ),
    ) as invoke:
        result = await librarian_agent.librarian_agent(
            {
                "messages": [{"role": "user", "content": "Unrelated old context."}],
                "librarian_task": "Research feline navigation.",
            },
            config,
        )

    research_input = invoke.await_args.args[0]["messages"]
    assert len(research_input) == 1
    assert research_input[0].content == "Research feline navigation."
    assert result["messages"] == [report]
